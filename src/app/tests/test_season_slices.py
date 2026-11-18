from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from app import season_slices
from app.models import TV, Episode, Item, MediaTypes, Season, Sources, Status

EPISODES = [
    {
        "episode_number": number,
        "name": f"Episode {number}",
        "overview": f"Synopsis {number}",
        "air_date": "2020-01-01",
        "still_path": None,
        "runtime": 45,
    }
    for number in (1, 2, 3)
]

SEASON_DATA = {
    "media_id": "100",
    "source": Sources.TMDB.value,
    "media_type": MediaTypes.SEASON.value,
    "title": "Show A",
    "image": "http://example.com/season.jpg",
    "season_number": 1,
    "season_title": "Season 1",
    "first_air_date": "2020-01-01",
    "max_progress": 3,
    "synopsis": "Season synopsis",
    "score": 7.5,
    "details": {
        "first_air_date": "2020-01-01",
        "last_air_date": "2020-01-15",
        "episodes": 3,
        "runtime": "45m",
        "total_runtime": "2h 15m",
    },
}


def _fake_metadata(media_type, *_args, **_kwargs):
    """Return metadata for show 100 and its only season."""
    season = {**SEASON_DATA, "episodes": EPISODES, "related": {}}
    if media_type == MediaTypes.SEASON.value:
        return season
    tv = {
        **SEASON_DATA,
        "media_type": MediaTypes.TV.value,
        "related": {"seasons": [SEASON_DATA]},
        "details": {},
    }
    if media_type == "tv_with_seasons":
        return {**tv, "season/1": season}
    return tv


class SeasonSlicesTests(TestCase):
    """Tests for season slices and their episode checkboxes."""

    def setUp(self):
        """Create a user in show tracker mode and mock the show metadata."""
        self.user = get_user_model().objects.create_user(
            username="test",
            show_tracker_mode=True,
        )
        self.client.force_login(self.user)

        patcher = patch(
            "app.providers.services.get_media_metadata",
            side_effect=_fake_metadata,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        tv_item = Item.objects.create(
            media_id="100",
            source=Sources.TMDB.value,
            media_type=MediaTypes.TV.value,
            title="Show A",
            image="http://example.com/tv.jpg",
        )
        self.tv = TV.objects.bulk_create(
            [TV(item=tv_item, user=self.user, status=Status.IN_PROGRESS.value)],
        )[0]

    def _episode_url(self, episode_number):
        return reverse(
            "season_slice_episode",
            kwargs={
                "source": Sources.TMDB.value,
                "media_id": "100",
                "season_number": 1,
                "episode_number": episode_number,
            },
        )

    def _watch_counts(self):
        return {
            number: Episode.objects.filter(
                related_season__user=self.user,
                item__episode_number=number,
            ).count()
            for number in (1, 2, 3)
        }

    def test_build_season_slice(self):
        """Test the slice counts distinct watched episodes."""
        season_slice = season_slices.build_season_slice(SEASON_DATA, None)

        self.assertEqual(season_slice["watched"], 0)
        self.assertEqual(season_slice["total"], 3)
        self.assertFalse(season_slice["complete"])

    def test_show_page_lists_season_slices(self):
        """Test the show page lists seasons as slices only in the mode."""
        url = reverse(
            "media_details",
            kwargs={
                "source": Sources.TMDB.value,
                "media_type": MediaTypes.TV.value,
                "media_id": "100",
                "title": "show-a",
            },
        )

        response = self.client.get(url)
        self.assertContains(response, 'id="season-slice-1"')
        self.assertContains(response, "0/3")
        self.assertContains(response, "{ tab: 'seasons' }")
        self.assertContains(response, "tab = 'about'")
        self.assertNotContains(response, "tab = 'overview'")
        # The poster stands in for the title
        self.assertNotContains(response, '<h1 class="text-3xl')
        self.assertContains(response, "{ open: false }")

        response = self.client.get(url + "?season=1&episode=2")
        self.assertContains(response, "{ open: true }")
        self.assertContains(response, "/season-slice/tmdb/100/1?episode=2")

        self.user.show_tracker_mode = False
        self.user.save()
        response = self.client.get(url)
        self.assertNotContains(response, 'id="season-slice-1"')
        self.assertContains(response, "{ tab: 'overview' }")
        self.assertContains(response, '<h1 class="text-3xl')

    def test_season_page_redirects_to_show(self):
        """Test the season page opens the show's slice in the mode."""
        url = reverse(
            "season_details",
            kwargs={
                "source": Sources.TMDB.value,
                "media_id": "100",
                "title": "show-a",
                "season_number": 1,
            },
        )

        response = self.client.get(url)
        self.assertRedirects(
            response,
            "/details/tmdb/tv/100/show-a?season=1#season-slice-1",
            fetch_redirect_response=False,
        )

        # The slice's Season details link still reaches the season page
        response = self.client.get(url + "?full=1")
        self.assertEqual(response.status_code, 200)

        self.user.show_tracker_mode = False
        self.user.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_season_slice_lists_episodes(self):
        """Test expanding a slice lists the episodes with checkboxes."""
        response = self.client.get(
            reverse(
                "season_slice",
                kwargs={
                    "source": Sources.TMDB.value,
                    "media_id": "100",
                    "season_number": 1,
                },
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="season-slice-1"')
        self.assertContains(response, "Episode 3")
        self.assertContains(response, "Synopsis 3")
        self.assertContains(response, "Season synopsis")
        self.assertContains(response, "45m per episode")
        self.assertContains(response, "2h 15m total")
        self.assertNotContains(response, "detailsOpen: true")

        response = self.client.get(response.request["PATH_INFO"] + "?episode=2")
        self.assertContains(response, "detailsOpen: true", count=1)
        self.assertContains(response, "0/3")
        self.assertContains(response, self._episode_url(1))

    def test_watch_creates_season_and_episode(self):
        """Test ticking an episode creates the season when it is missing."""
        response = self.client.post(self._episode_url(1), {"action": "watch"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._watch_counts(), {1: 1, 2: 0, 3: 0})
        self.assertContains(response, "1/3")

    def test_watch_with_previous(self):
        """Test ticking an episode can also mark the earlier ones."""
        self.client.post(self._episode_url(3), {"action": "watch_with_previous"})

        self.assertEqual(self._watch_counts(), {1: 1, 2: 1, 3: 1})
        season = Season.objects.get(user=self.user, item__season_number=1)
        self.assertEqual(season.status, Status.COMPLETED.value)

    def test_unticked_episode_offers_previous(self):
        """Test an episode after unwatched ones asks before marking them."""
        self.client.post(self._episode_url(1), {"action": "watch"})

        response = self.client.post(self._episode_url(2), {"action": "watch"})
        self.assertNotContains(response, "earlier episode")

        response = self.client.post(self._episode_url(2), {"action": "unwatch"})
        self.assertContains(response, "Also mark the earlier episode as watched?")

    def test_watch_again_and_unwatch(self):
        """Test watching again adds a watch and unwatching removes one."""
        self.client.post(self._episode_url(1), {"action": "watch"})
        response = self.client.post(self._episode_url(1), {"action": "watch"})

        self.assertEqual(self._watch_counts()[1], 2)
        self.assertContains(response, "\u00d72")
        self.assertContains(response, "Watched 2 times")

        response = self.client.post(self._episode_url(1), {"action": "unwatch"})
        self.assertEqual(self._watch_counts()[1], 1)
        self.assertNotContains(response, "\u00d72")

    def test_invalid_action(self):
        """Test an unknown action is rejected."""
        response = self.client.post(self._episode_url(1), {"action": "delete"})

        self.assertEqual(response.status_code, 400)

    def test_upcoming_watch(self):
        """Test watching from Upcoming returns the watched mark only."""
        response = self.client.post(
            reverse("upcoming_watch"),
            {
                "media_id": "100",
                "source": Sources.TMDB.value,
                "season_number": 1,
                "episode_number": 2,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._watch_counts(), {1: 0, 2: 1, 3: 0})
        self.assertContains(response, 'title="Watched"')
        self.assertNotContains(response, "hx-post")
