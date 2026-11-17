from django.db.models import Prefetch
from django.utils import timezone

from app.models import Episode, Item, MediaTypes, Season, Sources, Status
from app.providers import manual, services, tmdb

# Actions for an episode checkbox in a season slice
WATCH = "watch"
WATCH_WITH_PREVIOUS = "watch_with_previous"
UNWATCH = "unwatch"
EPISODE_ACTIONS = (WATCH, WATCH_WITH_PREVIOUS, UNWATCH)


def get_or_create_season(user, media_id, source, season_number):
    """Return the user's season, creating it as in progress if missing."""
    try:
        return Season.objects.get(
            item__media_id=media_id,
            item__source=source,
            item__season_number=season_number,
            item__episode_number=None,
            user=user,
        )
    except Season.DoesNotExist:
        tv_with_seasons_metadata = services.get_media_metadata(
            "tv_with_seasons",
            media_id,
            source,
            [season_number],
        )
        season_metadata = tv_with_seasons_metadata[f"season/{season_number}"]

        item, _created = Item.objects.get_or_create(
            media_id=media_id,
            source=Sources.TMDB.value,
            media_type=MediaTypes.SEASON.value,
            season_number=season_number,
            defaults={
                "title": tv_with_seasons_metadata["title"],
                "image": season_metadata["image"],
            },
        )
        return Season.objects.create(
            item=item,
            user=user,
            score=None,
            status=Status.IN_PROGRESS.value,
            notes="",
        )


def build_season_slice(season_data, season):
    """Return a season slice: the season, its watched count and its total.

    ``season_data`` is a related season from the show metadata and ``season``
    the user's season with its episodes prefetched, or None.
    """
    watched = (
        len({episode.item.episode_number for episode in season.episodes.all()})
        if season is not None
        else 0
    )
    total = season_data.get("max_progress") or 0
    return {
        "data": season_data,
        "season": season,
        "watched": watched,
        "total": total,
        "complete": total > 0 and watched >= total,
        # Loaded when the slice is expanded
        "episodes": None,
    }


def get_season_slice(user, media_id, source, season_number):
    """Return the season slice for one season of a show, with its episodes."""
    tv_metadata = services.get_media_metadata(MediaTypes.TV.value, media_id, source)
    season_data = next(
        season
        for season in tv_metadata["related"]["seasons"]
        if season["season_number"] == season_number
    )
    season = _get_user_season(user, media_id, source, season_number)

    season_metadata = _season_metadata(media_id, source, season_number)
    season_slice = build_season_slice(season_data, season)
    season_slice["episodes"] = _get_episodes(season_metadata, source, season)
    season_slice["info"] = _get_info(season_metadata)
    return season_slice


def apply_episode_action(user, media_id, source, season_number, episode_number, action):
    """Watch or unwatch an episode from its season slice checkbox."""
    now = timezone.now().replace(second=0, microsecond=0)

    if action == UNWATCH:
        season = _get_user_season(user, media_id, source, season_number)
        if season is not None:
            season.unwatch(episode_number)
        return

    season = get_or_create_season(user, media_id, source, season_number)
    if action == WATCH_WITH_PREVIOUS:
        watched = {episode.item.episode_number for episode in season.episodes.all()}
        for episode in _season_metadata(media_id, source, season_number)["episodes"]:
            number = episode["episode_number"]
            if number == episode_number:
                break
            if number not in watched:
                season.watch(number, now)
    season.watch(episode_number, now)


def _get_user_season(user, media_id, source, season_number):
    return (
        Season.objects.filter(
            user=user,
            item__media_id=media_id,
            item__source=source,
            item__season_number=season_number,
        )
        .select_related("item")
        .prefetch_related(
            Prefetch("episodes", queryset=Episode.objects.select_related("item")),
        )
        .first()
    )


def _season_metadata(media_id, source, season_number):
    tv_with_seasons_metadata = services.get_media_metadata(
        "tv_with_seasons",
        media_id,
        source,
        [season_number],
    )
    return tv_with_seasons_metadata[f"season/{season_number}"]


def _get_info(season_metadata):
    """Return the season details shown above its episodes."""
    synopsis = season_metadata.get("synopsis")
    return {
        "details": season_metadata.get("details", {}),
        "score": season_metadata.get("score"),
        # TMDB fills in a placeholder when a season has no synopsis
        "synopsis": None if synopsis == tmdb.get_synopsis("") else synopsis,
    }


def _get_episodes(season_metadata, source, season):
    """Return the season's episodes with their watch counts.

    Each episode also counts the unwatched episodes before it, so ticking it
    can offer to mark those as watched too.
    """
    episodes_in_db = season.episodes.all() if season is not None else []
    provider = manual if source == Sources.MANUAL.value else tmdb
    episodes = provider.process_episodes(season_metadata, episodes_in_db)

    unwatched_before = 0
    for episode in episodes:
        episode["watch_count"] = len(episode["history"])
        episode["unwatched_before"] = unwatched_before
        if not episode["watch_count"]:
            unwatched_before += 1
    return episodes
