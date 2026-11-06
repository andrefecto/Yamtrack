from datetime import timedelta
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from app.media_sections import build_tv_sections
from app.models import TV, Item, MediaTypes, Sources, Status


def _tv(title, status, progress=0, max_progress=None, last_watched=None):
    return SimpleNamespace(
        item=SimpleNamespace(title=title),
        status=status,
        progress=progress,
        max_progress=max_progress,
        progressed_at=last_watched,
    )


class BuildTVSectionsTests(SimpleTestCase):
    """Tests for grouping TV shows into sections."""

    def test_sections_order_and_membership(self):
        """Test each show lands in the right section, in the right order."""
        now = timezone.now()
        recent = _tv("Recent", Status.IN_PROGRESS.value, 3, 10, now - timedelta(days=2))
        older = _tv("Older", Status.IN_PROGRESS.value, 3, 10, now - timedelta(days=9))
        stale = _tv("Stale", Status.IN_PROGRESS.value, 3, 10, now - timedelta(days=45))
        caught_up = _tv(
            "Caught Up",
            Status.IN_PROGRESS.value,
            10,
            10,
            now - timedelta(days=90),
        )
        no_watches = _tv("No Watches", Status.IN_PROGRESS.value, 0, 10)
        planned = _tv("Planned", Status.PLANNING.value)
        finished = _tv("Finished", Status.COMPLETED.value)
        paused = _tv("B Paused", Status.PAUSED.value)
        dropped = _tv("A Dropped", Status.DROPPED.value)

        sections = build_tv_sections(
            [
                planned,
                stale,
                older,
                dropped,
                caught_up,
                finished,
                recent,
                paused,
                no_watches,
            ],
            now=now,
        )

        self.assertEqual(
            [(section["key"], section["items"]) for section in sections],
            [
                ("watching", [recent, older, no_watches]),
                ("caught_up", [caught_up]),
                ("stale", [stale]),
                ("not_started", [planned]),
                ("finished", [finished]),
                ("on_hold", [dropped, paused]),
            ],
        )

    def test_empty_sections_are_omitted(self):
        """Test only sections with shows are returned."""
        sections = build_tv_sections([_tv("Planned", Status.PLANNING.value)])

        self.assertEqual([section["key"] for section in sections], ["not_started"])


class MediaListSectionsViewTests(TestCase):
    """Tests for the sectioned shows list."""

    def setUp(self):
        """Create a user with a planned and a finished show."""
        self.credentials = {"username": "test", "password": "12345"}
        self.user = get_user_model().objects.create_user(**self.credentials)
        self.client.login(**self.credentials)

        for media_id, title, status in (
            ("1", "Planned Show", Status.PLANNING.value),
            ("2", "Finished Show", Status.COMPLETED.value),
        ):
            item = Item.objects.create(
                media_id=media_id,
                source=Sources.TMDB.value,
                media_type=MediaTypes.TV.value,
                title=title,
                image="http://example.com/image.jpg",
            )
            TV.objects.bulk_create([TV(item=item, user=self.user, status=status)])

        self.url = reverse(
            "medialist",
            kwargs={"username": "test", "media_type": MediaTypes.TV.value},
        )

    def test_regular_grid_without_tab_bar(self):
        """Test the list is not sectioned when the tab bar is off."""
        response = self.client.get(self.url + "?layout=grid&status=All")

        self.assertFalse(response.context["sections_mode"])
        self.assertIsNone(response.context["sections"])

    def test_sections_with_tab_bar(self):
        """Test the list is sectioned with the tab bar and no status filter."""
        self.user.mobile_tab_bar = True
        self.user.save()

        response = self.client.get(self.url + "?layout=grid&status=All")

        self.assertEqual(
            [section["key"] for section in response.context["sections"]],
            ["not_started", "finished"],
        )
        self.assertContains(response, 'id="media-content"')
        self.assertContains(response, 'id="section-not_started"')

    def test_status_filter_shows_regular_grid(self):
        """Test a status filter falls back to the regular grid in the wrapper."""
        self.user.mobile_tab_bar = True
        self.user.save()

        response = self.client.get(
            self.url + "?layout=grid&status=Completed",
            headers={"HX-Request": "true"},
        )

        self.assertTemplateUsed(response, "app/components/media_sections.html")
        self.assertIsNone(response.context["sections"])
        self.assertNotContains(response, "Planned Show")

    def test_search_with_no_matches(self):
        """Test searching the sectioned list with no matches."""
        self.user.mobile_tab_bar = True
        self.user.save()

        response = self.client.get(
            self.url + "?layout=grid&status=All&search=zzz",
            headers={"HX-Request": "true"},
        )

        self.assertEqual(response.context["sections"], [])
        self.assertContains(response, "No shows match your search.")
