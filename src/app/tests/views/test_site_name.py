from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


class SiteNameTests(TestCase):
    """Test the configurable site name."""

    def setUp(self):
        """Create a user."""
        self.credentials = {"username": "test", "password": "12345"}
        get_user_model().objects.create_user(**self.credentials)

    @override_settings(SITE_NAME="Yamtrack")
    def test_default_name(self):
        """Pages should be named Yamtrack by default."""
        self.client.login(**self.credentials)

        response = self.client.get(reverse("home"))

        self.assertContains(response, "Yamtrack</h1>")

    @override_settings(SITE_NAME="TVTime")
    def test_custom_name(self):
        """The header and tab title should use the site name."""
        self.client.login(**self.credentials)

        response = self.client.get(reverse("home"))

        self.assertContains(response, "TVTime</h1>")
        self.assertRegex(response.content.decode(), r"Home\s*- TVTime")
        self.assertNotContains(response, "- Yamtrack")

    @override_settings(SITE_NAME="TVTime")
    def test_custom_name_on_login_page(self):
        """The login page should use the site name."""
        response = self.client.get(reverse("account_login"))

        self.assertContains(response, "TVTime")
        self.assertNotContains(response, "- Yamtrack")

    @override_settings(SITE_NAME="Yamtrack")
    def test_manifest_default_name(self):
        """The manifest should keep its names by default, without logging in."""
        response = self.client.get(reverse("web_manifest"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        self.assertEqual(response.json()["name"], "Yamtrack - Media Tracker")
        self.assertEqual(response.json()["short_name"], "Yamtrack")

    @override_settings(SITE_NAME="TVTime")
    def test_manifest_custom_name(self):
        """The manifest should use the site name for the home screen app."""
        response = self.client.get(reverse("web_manifest"))

        self.assertEqual(response.json()["name"], "TVTime")
        self.assertEqual(response.json()["short_name"], "TVTime")
