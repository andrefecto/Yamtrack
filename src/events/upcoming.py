import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from app.models import Episode, MediaTypes
from app.providers import services, tmdb
from events.models import Event

logger = logging.getLogger(__name__)

UPCOMING_DAYS = 14


def get_upcoming(user, today=None):
    """Return (date, entries) pairs for the user's releases in the coming days."""
    today = today or timezone.localdate()
    releases = Event.objects.get_user_events(
        user,
        today,
        today + timedelta(days=UPCOMING_DAYS - 1),
    )
    watched = _watched_episodes(user, releases)

    days = {}
    for release in releases:
        day = timezone.localtime(release.datetime).date()
        days.setdefault(day, []).append(_build_entry(release, watched))
    return sorted(days.items())


def _build_entry(release, watched):
    """Return the display data for one release."""
    entry = {
        "release": release,
        "is_episode": (
            release.item.media_type == MediaTypes.SEASON.value
            and release.content_number is not None
        ),
        "image": release.item.image,
    }
    if not entry["is_episode"]:
        return entry

    item = release.item
    entry["watched"] = (
        item.media_id,
        item.source,
        item.season_number,
        release.content_number,
    ) in watched

    episode = _episode_metadata(item, release.content_number)
    if episode:
        entry["episode_title"] = episode.get("name") or episode.get("title")
        if episode.get("still_path"):
            entry["image"] = tmdb.get_image_url(episode["still_path"])
        elif episode.get("image") and episode["image"] != settings.IMG_NONE:
            entry["image"] = episode["image"]
    return entry


def _episode_metadata(season_item, episode_number):
    """Return an episode's metadata from the cached season, or None."""
    try:
        season_metadata = services.get_media_metadata(
            MediaTypes.SEASON.value,
            season_item.media_id,
            season_item.source,
            [season_item.season_number],
        )
    except services.ProviderAPIError:
        logger.warning("Could not load metadata for Upcoming: %s", season_item)
        return None

    for episode in season_metadata["episodes"]:
        if episode["episode_number"] == episode_number:
            return episode
    return None


def _watched_episodes(user, releases):
    """Return the (media_id, source, season, episode) keys the user watched."""
    media_ids = {
        release.item.media_id
        for release in releases
        if release.item.media_type == MediaTypes.SEASON.value
    }
    if not media_ids:
        return set()

    return set(
        Episode.objects.filter(
            related_season__user=user,
            item__media_id__in=media_ids,
        ).values_list(
            "item__media_id",
            "item__source",
            "item__season_number",
            "item__episode_number",
        ),
    )
