import logging

from django.conf import settings
from django.db.models import Prefetch
from django.utils import timezone

from app.helpers import is_released_date
from app.models import Episode, MediaTypes, Season, Sources, Status
from app.providers import services, tmdb

logger = logging.getLogger(__name__)


def get_up_next(user):
    """Return the next released episode of each in-progress season.

    Entries are ordered by most recently watched first; seasons that have not
    been started yet come last, ordered by title.
    """
    seasons = (
        Season.objects.filter(
            user=user,
            status=Status.IN_PROGRESS.value,
            item__season_number__gt=0,
        )
        .select_related("item", "related_tv__item")
        .prefetch_related(
            Prefetch("episodes", queryset=Episode.objects.select_related("item")),
        )
    )

    today = timezone.localdate()
    entries = [
        entry
        for entry in (build_up_next_entry(season, today) for season in seasons)
        if entry is not None
    ]

    started = [entry for entry in entries if entry["last_watched_at"] is not None]
    not_started = [entry for entry in entries if entry["last_watched_at"] is None]
    started.sort(key=lambda entry: entry["last_watched_at"], reverse=True)
    not_started.sort(key=lambda entry: entry["season"].item.title.lower())
    return started + not_started


def build_up_next_entry(season, today=None):
    """Return the Up Next entry for a season, or None if nothing is ready."""
    try:
        season_metadata = services.get_media_metadata(
            MediaTypes.SEASON.value,
            season.item.media_id,
            season.item.source,
            [season.item.season_number],
        )
    except services.ProviderAPIError:
        logger.warning("Could not load metadata for Up Next: %s", season)
        return None

    episode = season.next_episode(season_metadata)
    if episode is None:
        return None

    # Manual entries usually have no air dates, so they are always ready
    air_date = episode.get("air_date")
    if season.item.source != Sources.MANUAL.value and not is_released_date(
        air_date,
        today,
    ):
        return None

    # TMDB episodes have a still_path, manual episodes an image
    if episode.get("still_path"):
        image = tmdb.get_image_url(episode["still_path"])
    else:
        image = episode.get("image") or settings.IMG_NONE
    if image == settings.IMG_NONE:
        image = season.item.image

    return {
        "season": season,
        "episode_number": episode["episode_number"],
        "episode_title": episode.get("name") or episode.get("title"),
        "air_date": air_date,
        "image": image,
        "remaining_episodes": _remaining_episodes(season_metadata, episode),
        "last_watched_at": season.progressed_at,
    }


def _remaining_episodes(season_metadata, next_episode):
    """Return how many episodes of the season are left, including the next one."""
    episode_numbers = [
        episode["episode_number"] for episode in season_metadata["episodes"]
    ]
    return len(episode_numbers) - episode_numbers.index(next_episode["episode_number"])
