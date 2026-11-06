import calendar
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from app.models import TV, Episode, Item, MediaTypes, Season, Sources, Status
from events.models import Event
from users.models import WeekStartDayChoices


class CalendarViewTests(TestCase):
    """Tests for the calendar views."""

    def setUp(self):
        """Set up test data."""
        self.credentials = {"username": "testuser", "password": "testpassword"}
        self.user = get_user_model().objects.create_user(**self.credentials)
        self.client.login(**self.credentials)

    @patch("events.models.Event.objects.get_user_events")
    @patch.object(get_user_model(), "update_preference")
    def test_calendar_default_view(
        self,
        mock_update_preference,
        mock_get_user_events,
    ):
        """Test the calendar view with default parameters."""
        # Set up mocks
        mock_update_preference.return_value = "month"
        mock_get_user_events.return_value = []

        # Make the request
        response = self.client.get(reverse("calendar"))

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "events/calendar.html")

        # Check that the view called the mocked methods
        mock_update_preference.assert_called_once_with("calendar_layout", None)

        # Get today's date for verification
        today = timezone.localdate()
        first_day = date(today.year, today.month, 1)

        # Calculate last day of the month
        december = 12
        if today.month == december:
            last_day = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            last_day = date(today.year, today.month + 1, 1) - timedelta(days=1)

        mock_get_user_events.assert_called_once_with(self.user, first_day, last_day)

        # Check context data
        self.assertEqual(response.context["month"], today.month)
        self.assertEqual(response.context["year"], today.year)
        self.assertEqual(
            response.context["month_name"],
            calendar.month_name[today.month],
        )
        self.assertEqual(response.context["view_type"], "month")
        self.assertEqual(response.context["today"], today)

    @patch("events.models.Event.objects.get_user_events")
    @patch.object(get_user_model(), "update_preference")
    def test_calendar_with_month_year_params(
        self,
        mock_update_preference,
        mock_get_user_events,
    ):
        """Test the calendar view with month and year parameters."""
        # Set up mocks
        mock_update_preference.return_value = "month"
        mock_get_user_events.return_value = []

        # Make the request with specific month and year
        response = self.client.get(reverse("calendar") + "?month=6&year=2024")

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "events/calendar.html")

        # Check that the view called the mocked methods
        mock_update_preference.assert_called_once_with("calendar_layout", None)

        # Verify date range for June 2024
        first_day = date(2024, 6, 1)
        last_day = date(2024, 7, 1) - timedelta(days=1)
        mock_get_user_events.assert_called_once_with(self.user, first_day, last_day)

        # Check context data
        self.assertEqual(response.context["month"], 6)
        self.assertEqual(response.context["year"], 2024)
        self.assertEqual(response.context["month_name"], "June")
        self.assertEqual(response.context["prev_month"], 5)
        self.assertEqual(response.context["prev_year"], 2024)
        self.assertEqual(response.context["next_month"], 7)
        self.assertEqual(response.context["next_year"], 2024)

    @patch("events.models.Event.objects.get_user_events")
    @patch.object(get_user_model(), "update_preference")
    def test_calendar_with_view_param(
        self,
        mock_update_preference,
        mock_get_user_events,
    ):
        """Test the calendar view with view parameter."""
        # Set up mocks
        mock_update_preference.return_value = "list"
        mock_get_user_events.return_value = []

        # Make the request with view parameter
        response = self.client.get(reverse("calendar") + "?view=list")

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "events/calendar.html")

        # Check that the view called the mocked methods
        mock_update_preference.assert_called_once_with("calendar_layout", "list")

        # Check context data
        self.assertEqual(response.context["view_type"], "list")

    @patch("events.models.Event.objects.get_user_events")
    @patch.object(get_user_model(), "update_preference")
    def test_calendar_with_invalid_month_year(
        self,
        mock_update_preference,
        mock_get_user_events,
    ):
        """Test the calendar view with invalid month and year parameters."""
        # Set up mocks
        mock_update_preference.return_value = "month"
        mock_get_user_events.return_value = []

        # Make the request with invalid month and year
        response = self.client.get(
            reverse("calendar") + "?month=invalid&year=invalid",
        )

        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "events/calendar.html")

        # Get today's date for verification
        today = timezone.localdate()

        # Check context data - should default to current month/year
        self.assertEqual(response.context["month"], today.month)
        self.assertEqual(response.context["year"], today.year)

    @patch("events.models.Event.objects.get_user_events")
    @patch.object(get_user_model(), "update_preference")
    def test_calendar_december_navigation(
        self,
        mock_update_preference,
        mock_get_user_events,
    ):
        """Test the calendar navigation for December."""
        # Set up mocks
        mock_update_preference.return_value = "month"
        mock_get_user_events.return_value = []

        # Make the request for December
        response = self.client.get(reverse("calendar") + "?month=12&year=2024")

        # Check context data for navigation
        self.assertEqual(response.context["prev_month"], 11)
        self.assertEqual(response.context["prev_year"], 2024)
        self.assertEqual(response.context["next_month"], 1)
        self.assertEqual(response.context["next_year"], 2025)

    @patch("events.models.Event.objects.get_user_events")
    @patch.object(get_user_model(), "update_preference")
    def test_calendar_january_navigation(
        self,
        mock_update_preference,
        mock_get_user_events,
    ):
        """Test the calendar navigation for January."""
        # Set up mocks
        mock_update_preference.return_value = "month"
        mock_get_user_events.return_value = []

        # Make the request for January
        response = self.client.get(reverse("calendar") + "?month=1&year=2024")

        # Check context data for navigation
        self.assertEqual(response.context["prev_month"], 12)
        self.assertEqual(response.context["prev_year"], 2023)
        self.assertEqual(response.context["next_month"], 2)
        self.assertEqual(response.context["next_year"], 2024)

    @patch("events.models.Event.objects.get_user_events")
    @patch.object(get_user_model(), "update_preference")
    def test_calendar_with_events(
        self,
        mock_update_preference,
        mock_get_user_events,
    ):
        """Test the calendar with events."""
        # Set up mocks
        mock_update_preference.return_value = "month"

        item1 = Item(
            id=1,
            media_id="123",
            source=Sources.MANUAL.value,
            media_type=MediaTypes.ANIME.value,
            title="Test Show 1",
            image="https://example.com/image1.jpg",
        )

        item2 = Item(
            id=2,
            media_id="456",
            source=Sources.MANUAL.value,
            media_type=MediaTypes.MOVIE.value,
            title="Test Movie",
            image="https://example.com/image2.jpg",
        )

        # Create some mock events
        today = timezone.localdate()
        event1 = Event(
            item=item1,
            datetime=timezone.make_aware(
                timezone.datetime(today.year, today.month, 15, 12, 0),
            ),
        )
        event2 = Event(
            item=item1,
            content_number=2,
            datetime=timezone.make_aware(
                timezone.datetime(today.year, today.month, 15, 18, 0),
            ),
        )
        event3 = Event(
            item=item2,
            datetime=timezone.make_aware(
                timezone.datetime(today.year, today.month, 20, 9, 0),
            ),
        )

        mock_get_user_events.return_value = [event1, event2, event3]

        # Make the request
        response = self.client.get(reverse("calendar"))

        # Check response
        self.assertEqual(response.status_code, 200)

        # Check release_dict in context
        release_dict = response.context["release_dict"]
        self.assertEqual(len(release_dict), 2)  # Two days with events
        self.assertEqual(len(release_dict[15]), 2)  # Two events on the 15th
        self.assertEqual(len(release_dict[20]), 1)  # One event on the 20th

    @patch("events.tasks.reload_calendar.delay")
    def test_reload_calendar(self, mock_reload_task):
        """Test the reload_calendar view."""
        # Make the request
        response = self.client.post(reverse("reload_calendar"))

        # Check response
        self.assertRedirects(response, reverse("calendar"))

        # Check that the task was called
        mock_reload_task.assert_called_once_with(self.user)

        # Check for message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn("refresh upcoming releases", str(messages[0]))

    def test_reload_calendar_get_method_not_allowed(self):
        """Test that GET requests to reload_calendar are not allowed."""
        # Make a GET request
        response = self.client.get(reverse("reload_calendar"))

        # Check response - should be 405 Method Not Allowed
        self.assertEqual(response.status_code, 405)


class DownloadCalendarViewTests(TestCase):
    """Tests for the download_calendar view."""

    def setUp(self):
        """Set up test data."""
        self.credentials = {"username": "testuser", "password": "testpassword"}
        self.user = get_user_model().objects.create_user(**self.credentials)
        self.url = reverse("download_calendar", args=[self.user.token])

    def test_download_calendar_invalid_token(self):
        """Test that an invalid token returns 401."""
        url = reverse("download_calendar", args=["invalid-token"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)

    @patch("events.models.Event.objects.get_user_events")
    def test_download_calendar_empty(self, mock_get_user_events):
        """Test downloading a calendar with no events."""
        mock_get_user_events.return_value = []

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/calendar")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="calendar.ics"',
        )

        content = response.content.decode()
        self.assertIn("BEGIN:VCALENDAR", content)
        self.assertIn("PRODID:-//Yamtrack//EN", content)
        self.assertIn("VERSION:2.0", content)
        self.assertIn("END:VCALENDAR", content)
        self.assertNotIn("BEGIN:VEVENT", content)

    @patch("events.models.Event.objects.get_user_events")
    def test_download_calendar_with_events(self, mock_get_user_events):
        """Test downloading a calendar with events."""
        item1 = Item.objects.create(
            media_id="123",
            source=Sources.MANUAL.value,
            media_type=MediaTypes.ANIME.value,
            title="Test Show",
            image="https://example.com/image.jpg",
        )
        item2 = Item.objects.create(
            media_id="456",
            source=Sources.MANUAL.value,
            media_type=MediaTypes.MOVIE.value,
            title="Test Movie",
            image="https://example.com/image2.jpg",
        )

        event1 = Event.objects.create(
            item=item1,
            content_number=5,
            datetime=timezone.make_aware(
                timezone.datetime(2024, 6, 15, 12, 0),
            ),
        )
        event2 = Event.objects.create(
            item=item2,
            datetime=timezone.make_aware(
                timezone.datetime(2024, 6, 20, 18, 0),
            ),
        )

        mock_get_user_events.return_value = [event1, event2]

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/calendar")

        content = response.content.decode()
        self.assertIn("BEGIN:VCALENDAR", content)
        self.assertIn("BEGIN:VEVENT", content)
        self.assertIn("END:VEVENT", content)
        self.assertIn("END:VCALENDAR", content)

        # Verify event count
        self.assertEqual(content.count("BEGIN:VEVENT"), 2)

        # Verify the date range passed to get_user_events
        mock_get_user_events.assert_called_once()
        call_args = mock_get_user_events.call_args
        self.assertEqual(call_args[0][0], self.user)

        # Start date should be 30 days ago, end date 90 days in the future
        today = timezone.now().date()
        expected_start = today - timedelta(days=30)
        expected_end = today + timedelta(days=90)
        self.assertEqual(call_args[0][1], expected_start)
        self.assertEqual(call_args[0][2], expected_end)

    def test_download_calendar_head_request(self):
        """Test that HEAD requests are allowed."""
        response = self.client.head(self.url)
        self.assertEqual(response.status_code, 200)

    @patch("events.models.Event.objects.get_user_events")
    def test_download_calendar_no_auth_required(self, mock_get_user_events):
        """Test that download_calendar does not require login."""
        mock_get_user_events.return_value = []

        # Use a new client that is not logged in
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_download_calendar_post_not_allowed(self):
        """Test that POST requests are not allowed."""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 405)


class CalendarWeekStartDayTests(TestCase):
    """Tests for the calendar view honoring the user's week_start_day."""

    def setUp(self):
        """Set up test user/client."""
        self.credentials = {"username": "wsuser", "password": "testpassword"}
        self.user = get_user_model().objects.create_user(**self.credentials)
        self.client.login(**self.credentials)

    @patch("events.models.Event.objects.get_user_events")
    @patch.object(get_user_model(), "update_preference")
    def test_calendar_monday_start(
        self,
        mock_update_preference,
        mock_get_user_events,
    ):
        """Calendar with Monday week-start has Monday-first headers and grid."""
        mock_update_preference.return_value = "month"
        mock_get_user_events.return_value = []
        self.user.week_start_day = WeekStartDayChoices.MONDAY
        self.user.save()

        response = self.client.get(reverse("calendar") + "?month=6&year=2024")
        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.context["weekday_headers"],
            ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        )
        # June 2024 starts on Saturday; under a Monday-first layout the first
        # row places 1 in the Saturday column and 2 in the Sunday column.
        first_row = response.context["calendar"][0]
        self.assertEqual(first_row, [0, 0, 0, 0, 0, 1, 2])

    @patch("events.models.Event.objects.get_user_events")
    @patch.object(get_user_model(), "update_preference")
    def test_calendar_sunday_start(
        self,
        mock_update_preference,
        mock_get_user_events,
    ):
        """Calendar with Sunday week-start has Sunday-first headers and grid."""
        mock_update_preference.return_value = "month"
        mock_get_user_events.return_value = []
        self.user.week_start_day = WeekStartDayChoices.SUNDAY
        self.user.save()

        response = self.client.get(reverse("calendar") + "?month=6&year=2024")
        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.context["weekday_headers"],
            ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        )
        # June 2024 starts on Saturday; under a Sunday-first layout the first
        # row places 1 in the Saturday column with all earlier columns empty.
        first_row = response.context["calendar"][0]
        self.assertEqual(first_row, [0, 0, 0, 0, 0, 0, 1])

    @patch("events.models.Event.objects.get_user_events")
    @patch.object(get_user_model(), "update_preference")
    def test_today_button_targets_today_cell(
        self,
        mock_update_preference,
        mock_get_user_events,
    ):
        """The Today button links to an anchor that exists in the current month."""
        mock_update_preference.return_value = "grid"
        mock_get_user_events.return_value = []

        response = self.client.get(reverse("calendar"))
        content = response.content.decode()

        self.assertIn('#today">Today</a>', content)
        self.assertEqual(content.count('id="today"'), 1)

    @patch("events.models.Event.objects.get_user_events")
    @patch.object(get_user_model(), "update_preference")
    def test_today_anchor_absent_in_other_months(
        self,
        mock_update_preference,
        mock_get_user_events,
    ):
        """Only the current month's grid has a today cell."""
        mock_update_preference.return_value = "grid"
        mock_get_user_events.return_value = []

        response = self.client.get(reverse("calendar") + "?month=6&year=2000")

        self.assertNotIn('id="today"', response.content.decode())

    def _list_view_with_releases_on(self, days, today):
        """Render list view for `today`'s month with one release on each day."""
        item = Item(
            id=1,
            media_id="123",
            source=Sources.MANUAL.value,
            media_type=MediaTypes.MOVIE.value,
            title="Test Movie",
            image="https://example.com/image.jpg",
        )
        events = [
            Event(
                item=item,
                datetime=timezone.make_aware(
                    timezone.datetime(today.year, today.month, day, 12, 0),
                ),
            )
            for day in days
        ]
        with (
            patch("events.models.Event.objects.get_user_events") as mock_events,
            patch.object(get_user_model(), "update_preference") as mock_pref,
            patch("events.views.timezone.localdate", return_value=today),
        ):
            mock_events.return_value = events
            mock_pref.return_value = "list"
            return self.client.get(reverse("calendar") + "?view=list")

    def test_list_view_today_anchor_on_todays_releases(self):
        """In list view the today anchor sits on today's releases."""
        response = self._list_view_with_releases_on([5, 15, 20], date(2026, 10, 15))

        self.assertEqual(response.context["list_anchor_day"], 15)
        content = response.content.decode()
        self.assertIn('#today">Today</a>', content)
        self.assertEqual(content.count('id="today"'), 1)

    def test_list_view_today_anchor_on_next_release_day(self):
        """With no releases today, the anchor moves to the next day that has one."""
        response = self._list_view_with_releases_on([5, 20, 25], date(2026, 10, 15))

        self.assertEqual(response.context["list_anchor_day"], 20)
        self.assertEqual(response.content.decode().count('id="today"'), 1)

    def test_list_view_no_today_anchor_after_last_release(self):
        """Once every release this month is past, there is nothing to scroll to."""
        response = self._list_view_with_releases_on([5, 10], date(2026, 10, 15))

        self.assertIsNone(response.context["list_anchor_day"])
        self.assertNotIn('id="today"', response.content.decode())


class UpcomingViewTests(TestCase):
    """Tests for the upcoming releases view."""

    def setUp(self):
        """Create a user, a tracked season with releases, and a movie release."""
        self.credentials = {"username": "testuser", "password": "testpassword"}
        self.user = get_user_model().objects.create_user(**self.credentials)
        self.client.login(**self.credentials)

        self.today = timezone.localdate()
        self.season_item = Item.objects.create(
            media_id="100",
            source=Sources.TMDB.value,
            media_type=MediaTypes.SEASON.value,
            title="Show A",
            image="http://example.com/season.jpg",
            season_number=3,
        )
        movie_item = Item.objects.create(
            media_id="200",
            source=Sources.TMDB.value,
            media_type=MediaTypes.MOVIE.value,
            title="Movie B",
            image="http://example.com/movie.jpg",
        )
        Event.objects.create(
            item=self.season_item,
            content_number=2,
            datetime=self._at_noon(self.today),
        )
        Event.objects.create(
            item=self.season_item,
            content_number=3,
            datetime=self._at_noon(self.today + timedelta(days=1)),
        )
        Event.objects.create(
            item=movie_item,
            datetime=self._at_noon(self.today + timedelta(days=5)),
        )

        events_patcher = patch(
            "events.models.Event.objects.get_user_events",
            return_value=Event.objects.order_by("datetime"),
        )
        self.mock_get_user_events = events_patcher.start()
        self.addCleanup(events_patcher.stop)

        metadata_patcher = patch(
            "app.providers.services.get_media_metadata",
            return_value={
                "episodes": [
                    {"episode_number": n, "name": f"Title {n}", "still_path": None}
                    for n in (1, 2, 3)
                ],
            },
        )
        metadata_patcher.start()
        self.addCleanup(metadata_patcher.stop)

    def _at_noon(self, day):
        return timezone.make_aware(
            timezone.datetime(day.year, day.month, day.day, 12),
        )

    def test_upcoming_groups_releases_by_day(self):
        """Test releases are grouped by day with episode details."""
        response = self.client.get(reverse("upcoming"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "events/upcoming.html")
        self.mock_get_user_events.assert_called_once_with(
            self.user,
            self.today,
            self.today + timedelta(days=13),
        )

        days = response.context["days"]
        self.assertEqual(
            [day for day, _entries in days],
            [
                self.today,
                self.today + timedelta(days=1),
                self.today + timedelta(days=5),
            ],
        )
        self.assertContains(response, "S03 | E02")
        self.assertContains(response, "Title 2")
        self.assertContains(response, "Movie B")
        self.assertContains(response, "Today")
        self.assertContains(response, "Tomorrow")

    def test_upcoming_marks_watched_episodes(self):
        """Test watched episodes have no watch button and others post to save."""
        season = Season.objects.bulk_create(
            [
                Season(
                    item=self.season_item,
                    user=self.user,
                    related_tv=TV.objects.bulk_create(
                        [
                            TV(
                                item=Item.objects.create(
                                    media_id="100",
                                    source=Sources.TMDB.value,
                                    media_type=MediaTypes.TV.value,
                                    title="Show A",
                                ),
                                user=self.user,
                                status=Status.IN_PROGRESS.value,
                            ),
                        ],
                    )[0],
                    status=Status.IN_PROGRESS.value,
                ),
            ],
        )[0]
        episode_item = Item.objects.create(
            media_id="100",
            source=Sources.TMDB.value,
            media_type=MediaTypes.EPISODE.value,
            title="Show A",
            season_number=3,
            episode_number=2,
        )
        Episode.save_base(
            Episode(item=episode_item, related_season=season, end_date=timezone.now()),
        )

        response = self.client.get(reverse("upcoming"))

        entries = [
            entry
            for _day, day_entries in response.context["days"]
            for entry in day_entries
        ]
        watched = {
            entry["release"].content_number: entry["watched"]
            for entry in entries
            if entry["is_episode"]
        }
        self.assertEqual(watched, {2: True, 3: False})
        self.assertContains(response, reverse("episode_save"), count=1)

    def test_upcoming_empty(self):
        """Test the empty state when nothing is coming out."""
        self.mock_get_user_events.return_value = Event.objects.none()

        response = self.client.get(reverse("upcoming"))

        self.assertEqual(response.context["days"], [])
        self.assertContains(response, "in the next 14 days")
