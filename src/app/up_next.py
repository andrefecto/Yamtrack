import logging
from collections import defaultdict
from datetime import date, datetime

from django.conf import settings
from django.db.models import Max, Prefetch, Q
from django.utils import timezone

from app.helpers import is_released_date
from app.models import Episode, MediaTypes, Season, Sources, Status
from app.providers import services, tmdb

logger = logging.getLogger(__name__)


# Episodes that aired this recently are flagged as new
NEW_EPISODE_DAYS = 7

# Released episodes listed per show; the rest are counted
UP_NEXT_EPISODES = 3


def get_up_next(user, today=None):
    """Return the released episodes left to watch of each show being watched.

    Shows are ordered by the most recently watched first. Shows with nothing
    watched yet come last, ordered by title.
    """
    entries = _build_entries(Season.objects.filter(user=user), today)

    started = [entry for entry in entries if entry["last_watched_at"] is not None]
    not_started = [entry for entry in entries if entry["last_watched_at"] is None]
    started.sort(key=lambda entry: entry["last_watched_at"], reverse=True)
    not_started.sort(key=lambda entry: entry["season"].item.title.lower())
    return started + not_started


def get_show_entry(tv, today=None):
    """Return the Up Next entry for a single show, or None."""
    entries = _build_entries(Season.objects.filter(related_tv=tv), today)
    return entries[0] if entries else None


def _build_entries(seasons, today=None):
    """Return one entry per show from the given seasons queryset.

    In-progress seasons are tried first. Planning seasons of in-progress shows
    are tried next: those are created when a new season is announced for a show
    that was already caught up.
    """
    today = today or timezone.localdate()
    seasons = (
        seasons.filter(
            Q(status=Status.IN_PROGRESS.value)
            | Q(
                status=Status.PLANNING.value,
                related_tv__status=Status.IN_PROGRESS.value,
            ),
            item__season_number__gt=0,
        )
        .select_related("item", "related_tv__item")
        .prefetch_related(
            Prefetch("episodes", queryset=Episode.objects.select_related("item")),
        )
    )

    seasons_by_show = defaultdict(list)
    for season in seasons:
        seasons_by_show[season.related_tv_id].append(season)

    last_watched_by_show = dict(
        Episode.objects.filter(related_season__related_tv__in=list(seasons_by_show))
        .values("related_season__related_tv")
        .annotate(last_watched=Max("end_date"))
        .values_list("related_season__related_tv", "last_watched"),
    )

    entries = []
    for show_id, show_seasons in seasons_by_show.items():
        show_seasons.sort(
            key=lambda season: (
                season.status != Status.IN_PROGRESS.value,
                season.item.season_number,
            ),
        )
        for season in show_seasons:
            entry = build_up_next_entry(season, today)
            if entry is not None:
                entry["last_watched_at"] = last_watched_by_show.get(show_id)
                entries.append(entry)
                break
    return entries


def _parse_air_date(air_date):
    """Return the air date as a date, or None if it is missing or partial."""
    if isinstance(air_date, datetime):
        return timezone.localtime(air_date).date()
    if isinstance(air_date, date):
        return air_date
    try:
        return date.fromisoformat(air_date)
    except (TypeError, ValueError):
        return None


def build_up_next_entry(season, today=None):
    """Return the Up Next entry for a season, or None if nothing is ready.

    The entry lists the season's released episodes from the next one to watch,
    up to ``UP_NEXT_EPISODES``, and counts the released ones left after those.
    """
    today = today or timezone.localdate()
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

    next_episode = season.next_episode(season_metadata)
    if next_episode is None:
        return None

    episodes = season_metadata["episodes"]
    released = []
    for episode in episodes[episodes.index(next_episode) :]:
        # Manual entries usually have no air dates, so they are always ready
        if season.item.source != Sources.MANUAL.value and not is_released_date(
            episode.get("air_date"),
            today,
        ):
            break
        released.append(episode)
    if not released:
        return None

    return {
        "season": season,
        "episodes": [
            _episode_row(season, episode, position, today)
            for position, episode in enumerate(released[:UP_NEXT_EPISODES])
        ],
        "more_episodes": max(len(released) - UP_NEXT_EPISODES, 0),
    }


def _episode_row(season, episode, position, today):
    """Return one episode row of an Up Next entry.

    ``position`` is how many unwatched episodes come before it in the entry.
    """
    # TMDB episodes have a still_path, manual episodes an image
    if episode.get("still_path"):
        image = tmdb.get_image_url(episode["still_path"])
    else:
        image = episode.get("image") or settings.IMG_NONE
    if image == settings.IMG_NONE:
        image = season.item.image

    aired_on = _parse_air_date(episode.get("air_date"))
    return {
        "episode_number": episode["episode_number"],
        "title": episode.get("name") or episode.get("title"),
        "air_date": episode.get("air_date"),
        "image": image,
        "is_new": aired_on is not None and (today - aired_on).days < NEW_EPISODE_DAYS,
        "unwatched_before": position,
    }
