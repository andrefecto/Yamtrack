from datetime import timedelta

from django.db.models import Max
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from app.models import MediaTypes, Status
from events.models import Event

# In-progress shows not watched for this long move to their own section
STALE_AFTER = timedelta(days=30)


def build_tv_sections(tv_list, now=None):
    """Group TV shows into sections by how the user is watching them.

    Expects ``max_progress`` to be annotated on each show (released episodes).
    Each section keeps the list's sort order. An episode that aired after the
    last watched one counts as activity, so a show with a new episode is not
    treated as stale. Empty sections are left out.
    """
    now = now or timezone.now()
    latest_releases = _latest_release_by_show(tv_list, now)
    for tv in tv_list:
        tv.last_activity = _last_activity(tv, latest_releases)

    sections = {
        "watching": {"title": _("Watching"), "items": []},
        "caught_up": {"title": _("Caught up"), "items": []},
        "stale": {"title": _("Haven't watched in a while"), "items": []},
        "not_started": {"title": _("Not started"), "items": []},
        "finished": {"title": _("Finished"), "items": []},
        "on_hold": {"title": _("Paused & dropped"), "items": []},
    }

    for tv in tv_list:
        sections[_section_key(tv, now)]["items"].append(tv)

    return [
        {"key": key, **section} for key, section in sections.items() if section["items"]
    ]


def build_movie_sections(movie_list):
    """Group movies into to watch, watched, and paused or dropped.

    Movies to watch keep the list's sort order, watched movies are ordered by
    most recently watched. Empty sections are left out.
    """
    sections = {
        "to_watch": {"title": _("To watch"), "items": []},
        "watched": {"title": _("Watched"), "items": []},
        "on_hold": {"title": _("Paused & dropped"), "items": []},
    }

    for movie in movie_list:
        if movie.status == Status.COMPLETED.value:
            key = "watched"
        elif movie.status in (Status.PAUSED.value, Status.DROPPED.value):
            key = "on_hold"
        else:
            key = "to_watch"
        sections[key]["items"].append(movie)

    # Movies without a watch date sort after everything else
    sections["watched"]["items"].sort(
        key=lambda movie: (
            movie.end_date is not None,
            movie.end_date or timezone.now(),
        ),
        reverse=True,
    )
    sections["on_hold"]["items"].sort(key=lambda movie: movie.item.title.lower())

    return [
        {"key": key, **section} for key, section in sections.items() if section["items"]
    ]


def _section_key(tv, now):
    if tv.status == Status.PLANNING.value:
        return "not_started"
    if tv.status == Status.COMPLETED.value:
        return "finished"
    if tv.status in (Status.PAUSED.value, Status.DROPPED.value):
        return "on_hold"

    max_progress = getattr(tv, "max_progress", None)
    if max_progress and tv.progress >= max_progress:
        return "caught_up"

    if tv.last_activity is not None and now - tv.last_activity > STALE_AFTER:
        return "stale"
    return "watching"


def _latest_release_by_show(tv_list, now):
    """Return the latest released episode datetime keyed by (media_id, source)."""
    if not tv_list:
        return {}
    rows = (
        Event.objects.filter(
            item__media_type=MediaTypes.SEASON.value,
            item__media_id__in={tv.item.media_id for tv in tv_list},
            item__season_number__gt=0,
            content_number__isnull=False,
            datetime__lte=now,
        )
        .values("item__media_id", "item__source")
        .annotate(latest=Max("datetime"))
    )
    return {(row["item__media_id"], row["item__source"]): row["latest"] for row in rows}


def _last_activity(tv, latest_releases):
    """Return the most recent of the last watch and an unwatched release."""
    last_watched = tv.progressed_at
    if last_watched is None:
        return None

    max_progress = getattr(tv, "max_progress", None)
    has_unwatched = max_progress is not None and tv.progress < max_progress
    latest_release = latest_releases.get((tv.item.media_id, tv.item.source))
    if has_unwatched and latest_release is not None:
        return max(last_watched, latest_release)
    return last_watched
