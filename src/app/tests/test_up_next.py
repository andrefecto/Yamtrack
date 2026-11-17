import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from app import up_next
from app.models import TV, Episode, Item, MediaTypes, Season, Sources, Status


def _episodes(*air_dates):
    """Build TMDB-style episode metadata with the given air dates."""
    return [
        {
            "episode_number": number,
            "name": f"Episode {number}",
            "air_date": air_date,
            "still_path": f"/still{number}.jpg",
        }
        for number, air_date in enumerate(air_dates, start=1)
    ]


class UpNextTests(TestCase):
    """Tests for the Up Next list and its watch action."""

    def setUp(self):
        """Create a user with one show in progress and mock its metadata."""
        self.credentials = {"username": "test", "password": "12345"}
        self.user = get_user_model().objects.create_user(**self.credentials)
        self.client.login(**self.credentials)

        tomorrow = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()
        self.metadata = {
            "100": _episodes("2020-01-01", "2020-01-08", "2020-01-15"),
            "200": _episodes("2020-01-01", tomorrow),
        }
        patcher = patch(
            "app.providers.services.get_media_metadata",
            side_effect=self._fake_metadata,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        self.season = self._create_season("100", "Show A")

    def _fake_metadata(self, media_type, media_id, _source, *_args, **_kwargs):
        episodes = self.metadata[media_id]
        if media_type == MediaTypes.SEASON.value:
            return {"episodes": episodes}
        if media_type == "tv_with_seasons":
            return {"season/1": {"episodes": episodes}}
        return {"related": {"seasons": []}}

    def _create_season(
        self,
        media_id,
        title,
        watched=0,
        status=Status.IN_PROGRESS.value,
        tv_status=Status.IN_PROGRESS.value,
    ):
        tv_item = Item.objects.create(
            media_id=media_id,
            source=Sources.TMDB.value,
            media_type=MediaTypes.TV.value,
            title=title,
            image="http://example.com/tv.jpg",
        )
        tv = TV.objects.bulk_create(
            [TV(item=tv_item, user=self.user, status=tv_status)],
        )[0]
        season_item = Item.objects.create(
            media_id=media_id,
            source=Sources.TMDB.value,
            media_type=MediaTypes.SEASON.value,
            title=title,
            image="http://example.com/season.jpg",
            season_number=1,
        )
        season = Season.objects.bulk_create(
            [
                Season(
                    item=season_item,
                    user=self.user,
                    related_tv=tv,
                    status=status,
                ),
            ],
        )[0]
        for number in range(1, watched + 1):
            episode_item = Item.objects.create(
                media_id=media_id,
                source=Sources.TMDB.value,
                media_type=MediaTypes.EPISODE.value,
                title=title,
                season_number=1,
                episode_number=number,
            )
            Episode.save_base(
                Episode(
                    item=episode_item,
                    related_season=season,
                    end_date=datetime.datetime(2023, 6, number, tzinfo=datetime.UTC),
                ),
            )
        return season

    def test_next_episode(self):
        """Test next_episode follows the latest watched episode."""
        self.assertEqual(self.season.next_episode()["episode_number"], 1)

        season = self._create_season("101", "Show B", watched=1)
        self.metadata["101"] = self.metadata["100"]
        self.assertEqual(season.next_episode()["episode_number"], 2)

        finished = self._create_season("102", "Show C", watched=3)
        self.metadata["102"] = self.metadata["100"]
        self.assertIsNone(finished.next_episode())

    def test_get_up_next_skips_unaired_episodes(self):
        """Test shows whose next episode has not aired are left out."""
        self._create_season("200", "Show Unaired", watched=1)

        entries = up_next.get_up_next(self.user)

        self.assertEqual([entry["season"] for entry in entries], [self.season])
        self.assertEqual(entries[0]["episode_number"], 1)
        self.assertEqual(entries[0]["remaining_episodes"], 3)
        self.assertEqual(
            entries[0]["image"],
            "https://image.tmdb.org/t/p/w500/still1.jpg",
        )

    def test_get_up_next_orders_recently_watched_first(self):
        """Test started shows come first, most recently watched on top."""
        self.metadata["300"] = self.metadata["100"]
        self.metadata["301"] = self.metadata["100"]
        older = self._create_season("300", "Show Older", watched=1)
        newer = self._create_season("301", "Show Newer", watched=2)

        entries = up_next.get_up_next(self.user)

        self.assertEqual(
            [entry["season"] for entry in entries],
            [newer, older, self.season],
        )

    def test_get_up_next_includes_announced_seasons(self):
        """Test planning seasons of in-progress shows are included.

        Those are created when a new season is announced for a caught-up show.
        """
        self.metadata["500"] = self.metadata["100"]
        self.metadata["501"] = self.metadata["100"]
        announced = self._create_season(
            "500",
            "Show Announced",
            status=Status.PLANNING.value,
        )
        self._create_season(
            "501",
            "Show Planned",
            status=Status.PLANNING.value,
            tv_status=Status.PLANNING.value,
        )

        entries = up_next.get_up_next(self.user)

        self.assertEqual(
            [entry["season"] for entry in entries],
            [self.season, announced],
        )

    def test_get_up_next_one_entry_per_show(self):
        """Test a show with several open seasons gets one entry."""
        season_item = Item.objects.create(
            media_id="100",
            source=Sources.TMDB.value,
            media_type=MediaTypes.SEASON.value,
            title="Show A",
            season_number=2,
        )
        Season.objects.bulk_create(
            [
                Season(
                    item=season_item,
                    user=self.user,
                    related_tv=self.season.related_tv,
                    status=Status.PLANNING.value,
                ),
            ],
        )

        entries = up_next.get_up_next(self.user)

        self.assertEqual([entry["season"] for entry in entries], [self.season])

    def test_get_up_next_new_episode_moves_to_top(self):
        """Test a recently aired episode outranks an older watch."""
        yesterday = (timezone.localdate() - datetime.timedelta(days=1)).isoformat()
        self.metadata["600"] = _episodes("2020-01-01", yesterday)
        self.metadata["601"] = self.metadata["100"]
        new_episode = self._create_season("600", "Show New Episode", watched=1)
        recently_watched = self._create_season("601", "Show Recent", watched=2)

        entries = up_next.get_up_next(self.user)

        self.assertEqual(
            [entry["season"] for entry in entries],
            [new_episode, recently_watched, self.season],
        )
        self.assertEqual(
            [entry["is_new"] for entry in entries],
            [True, False, False],
        )

    def test_up_next_page(self):
        """Test the Up Next page lists the next episode."""
        response = self.client.get(reverse("up_next"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Show A")
        self.assertContains(response, "S01 | E01")
        self.assertContains(
            response,
            "/details/tmdb/tv/100/show-a?season=1&amp;episode=1#season-slice-1",
        )

    def test_up_next_watch(self):
        """Test watching from Up Next records the episode and shows the next."""
        response = self.client.post(
            reverse("up_next_watch", kwargs={"instance_id": self.season.id}),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Episode.objects.filter(
                related_season=self.season,
                item__episode_number=1,
            ).exists(),
        )
        self.assertContains(response, "S01 | E02")

    def test_up_next_watch_finale_removes_row(self):
        """Test watching the last episode leaves nothing to render for the show."""
        season = self._create_season("400", "Show Finale", watched=2)
        self.metadata["400"] = self.metadata["100"]

        response = self.client.post(
            reverse("up_next_watch", kwargs={"instance_id": season.id}),
        )

        self.assertEqual(response.status_code, 200)
        season.refresh_from_db()
        self.assertEqual(season.status, Status.COMPLETED.value)
        self.assertNotContains(response, f'id="up-next-{season.related_tv.id}"')

    def test_up_next_watch_other_users_season(self):
        """Test a user cannot watch episodes of another user's season."""
        other = get_user_model().objects.create_user(username="other")
        self.client.force_login(other)

        response = self.client.post(
            reverse("up_next_watch", kwargs={"instance_id": self.season.id}),
        )

        self.assertEqual(response.status_code, 404)
