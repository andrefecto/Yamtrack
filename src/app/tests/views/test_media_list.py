from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse
from django.utils import translation
from django.utils.html import escape

from app.models import (
    Item,
    MediaTypes,
    Movie,
    Sources,
    Status,
)
from app.templatetags import app_tags
from users.forms import UserUpdateForm


class MediaListViewTests(TestCase):
    """Test the media list view."""

    def setUp(self):
        """Create a user and log in."""
        self.credentials = {"username": "test", "password": "12345"}
        self.external_credentials = {
            "username": "test2",
            "password": "12345",
            "profile_private": True,
        }
        self.user = get_user_model().objects.create_user(**self.credentials)
        self.external_user = get_user_model().objects.create_user(
            **self.external_credentials
        )
        self.client.login(**self.credentials)

        movies_id = ["278", "238", "129", "424", "680"]
        num_completed = 3
        for i in range(1, 6):
            item = Item.objects.create(
                media_id=movies_id[i - 1],
                source=Sources.TMDB.value,
                media_type=MediaTypes.MOVIE.value,
                title=f"Test Movie {i}",
                image="http://example.com/image.jpg",
            )
            status = (
                Status.COMPLETED.value
                if i < num_completed
                else Status.IN_PROGRESS.value
            )
            Movie.objects.create(
                item=item,
                user=self.user,
                status=status,
                progress=1 if i < num_completed else 0,
                score=i,
            )

    def test_media_list_view(self):
        """Test the media list view displays media items."""
        response = self.client.get(
            reverse("medialist", args=[self.user.username, MediaTypes.MOVIE.value])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/media_list.html")

        self.assertIn("media_list", response.context)
        self.assertEqual(response.context["media_list"].paginator.count, 5)

        self.assertIn("sort_choices", response.context)
        self.assertIn("status_choices", response.context)
        self.assertEqual(response.context["media_type"], MediaTypes.MOVIE.value)
        self.assertEqual(
            response.context["media_type_plural"],
            app_tags.media_type_readable_plural(MediaTypes.MOVIE.value).lower(),
        )

    def test_empty_media_list_labels_use_singular_and_plural(self):
        """The empty state uses a singular title and plural description."""
        self.addCleanup(translation.deactivate)
        media_type = MediaTypes.COMIC.value

        for language, _name in settings.LANGUAGES:
            self.user.language = language
            self.user.save()

            response = self.client.get(
                reverse("medialist", args=[self.user.username, media_type])
            )

            with translation.override(language):
                expected_title = translation.gettext(
                    "No %(media_type_label)s Tracked Yet"
                ) % {
                    "media_type_label": escape(
                        app_tags.media_type_readable(media_type)
                    ),
                }
                expected_description = translation.gettext(
                    "Start tracking your %(media_type_plural)s to keep a record of "
                    "what you've %(past_verb)s."
                ) % {
                    "media_type_plural": escape(
                        app_tags.media_type_readable_plural(media_type)
                    ),
                    "past_verb": escape(app_tags.media_past_verb(media_type)),
                }

            with self.subTest(language=language):
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, expected_title)
                self.assertContains(response, expected_description)

    def test_media_list_with_filters(self):
        """Test the media list view with filters."""
        response = self.client.get(
            reverse("medialist", args=[self.user.username, MediaTypes.MOVIE.value])
            + "?status=Completed&sort=score&layout=table",
        )

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.context["current_status"],
            Status.COMPLETED.value,
        )
        self.assertEqual(response.context["current_sort"], "score")
        self.assertEqual(response.context["current_layout"], "table")

        self.assertEqual(response.context["media_list"].paginator.count, 2)

        self.user.refresh_from_db()
        self.assertEqual(self.user.movie_status, Status.COMPLETED.value)
        self.assertEqual(self.user.movie_sort, "score")
        self.assertEqual(self.user.movie_layout, "table")

    def test_media_list_htmx_request(self):
        """Test the media list view with HTMX request."""
        response = self.client.get(
            reverse("medialist", args=[self.user.username, MediaTypes.MOVIE.value])
            + "?layout=grid",
            headers={"hx-request": "true"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/components/media_grid_items.html")

        response = self.client.get(
            reverse("medialist", args=[self.user.username, MediaTypes.MOVIE.value])
            + "?layout=table",
            headers={"hx-request": "true"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/components/media_table_items.html")

    def test_media_list_soft_navigation_returns_full_page(self):
        """Soft-navigation body swaps (after an edit modal) get the full page."""
        response = self.client.get(
            reverse("medialist", args=[self.user.username, MediaTypes.MOVIE.value]),
            headers={"hx-request": "true", "x-soft-navigation": "true"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "app/media_list.html")

    def test_public_media_list_ignores_invalid_filters(self):
        """Test invalid public filters fall back to the target user's preferences."""
        self.external_user.profile_private = False
        self.external_user.save(update_fields=["profile_private"])

        response = self.client.get(
            reverse(
                "medialist", args=[self.external_user.username, MediaTypes.MOVIE.value]
            )
            + "?status=invalid&sort=bad_field&layout=invalid",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["current_status"], self.external_user.movie_status
        )
        self.assertEqual(
            response.context["current_sort"], self.external_user.movie_sort
        )
        self.assertEqual(
            response.context["current_layout"], self.external_user.movie_layout
        )

    def test_anonymous_user_can_view_public_media_list(self):
        """Test anonymous users can view public media lists."""
        self.external_user.profile_private = False
        self.external_user.save(update_fields=["profile_private"])
        self.client.logout()

        response = self.client.get(
            reverse(
                "medialist", args=[self.external_user.username, MediaTypes.MOVIE.value]
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("media_list", response.context)

    def test_profile_private_defaults_to_true(self):
        """Test new users have private profiles by default."""
        user = get_user_model().objects.create_user(
            username="private-default",
        )

        self.assertTrue(user.profile_private)

    def test_private_media_list(self):
        """Test the private media list view."""
        response = self.client.get(
            reverse(
                "medialist", args=[self.external_user.username, MediaTypes.MOVIE.value]
            )
        )
        self.assertEqual(response.status_code, 404)

        form = UserUpdateForm(
            data={"username": "test2", "profile_private": False},
            instance=self.external_user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        external_user = form.save()
        external_user.refresh_from_db()

        response = self.client.get(
            reverse(
                "medialist", args=[self.external_user.username, MediaTypes.MOVIE.value]
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("media_list", response.context)


class PosterOnlyCardTests(TestCase):
    """Test the poster-only cards used with the mobile tab bar."""

    overlay_marker = "absolute inset-x-0 bottom-0 bg-black/60"

    def setUp(self):
        """Create a user with one movie with a poster and one without."""
        self.credentials = {"username": "test", "password": "12345"}
        self.user = get_user_model().objects.create_user(**self.credentials)
        self.client.login(**self.credentials)

        for media_id, title, image in (
            ("278", "Poster Movie", "http://example.com/image.jpg"),
            ("238", "No Poster Movie", settings.IMG_NONE),
        ):
            Movie.objects.create(
                item=Item.objects.create(
                    media_id=media_id,
                    source=Sources.TMDB.value,
                    media_type=MediaTypes.MOVIE.value,
                    title=title,
                    image=image,
                ),
                user=self.user,
                status=Status.COMPLETED.value,
                progress=1,
            )
        self.url = reverse(
            "medialist",
            kwargs={"username": "test", "media_type": MediaTypes.MOVIE.value},
        )

    def test_default_cards_keep_titles(self):
        """Test cards keep titles and the bottom bar without the tab bar."""
        response = self.client.get(self.url + "?layout=grid")

        self.assertContains(response, 'title="Poster Movie">Poster Movie</a>')
        self.assertNotContains(response, self.overlay_marker)

    def test_poster_only_cards(self):
        """Test the title only shows without a poster and the bar overlays it."""
        self.user.mobile_tab_bar = True
        self.user.save()

        response = self.client.get(self.url + "?layout=grid")

        self.assertNotContains(response, 'title="Poster Movie">Poster Movie</a>')
        self.assertContains(
            response,
            'title="No Poster Movie">No Poster Movie</a>',
        )
        self.assertContains(response, self.overlay_marker, count=2)

    def test_caught_up_bar(self):
        """Test the overlay bar uses its own colour when caught up."""
        context = {
            "media": SimpleNamespace(status="In progress", progress=5, max_progress=5),
            "user": SimpleNamespace(progress_bar=True),
        }

        overlay = render_to_string(
            "app/components/progress_bar.html",
            {**context, "overlay": True},
        )
        default = render_to_string("app/components/progress_bar.html", context)

        self.assertIn("bg-yellow-400", overlay)
        self.assertNotIn("bg-yellow-400", default)

    def test_not_started_has_no_overlay_bar(self):
        """Test planned media get no bar on the poster, but keep the default one."""
        context = {
            "media": SimpleNamespace(status="Planning", progress=0, max_progress=10),
            "user": SimpleNamespace(progress_bar=True),
        }

        overlay = render_to_string(
            "app/components/progress_bar.html",
            {**context, "overlay": True},
        )
        default = render_to_string("app/components/progress_bar.html", context)

        self.assertNotIn("h-1.25", overlay)
        self.assertIn("h-1.25", default)
