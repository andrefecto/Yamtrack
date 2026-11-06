from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from app.models import Status

# In-progress shows not watched for this long move to their own section
STALE_AFTER = timedelta(days=30)


def build_tv_sections(tv_list, now=None):
    """Group TV shows into sections by how the user is watching them.

    Expects ``max_progress`` to be annotated on each show (released episodes).
    Empty sections are left out.
    """
    now = now or timezone.now()
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

    # Shows being watched are ordered by most recently watched
    for key in ("watching", "caught_up", "stale"):
        sections[key]["items"].sort(key=_last_watched_sort_key, reverse=True)
    for key in ("not_started", "finished", "on_hold"):
        sections[key]["items"].sort(key=lambda tv: tv.item.title.lower())

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

    last_watched = tv.progressed_at
    if last_watched is not None and now - last_watched > STALE_AFTER:
        return "stale"
    return "watching"


def _last_watched_sort_key(tv):
    last_watched = tv.progressed_at
    # Shows with nothing watched yet sort after everything else
    return (last_watched is not None, last_watched or timezone.now())
