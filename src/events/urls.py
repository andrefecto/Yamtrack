from django.urls import path

from events import views

urlpatterns = [
    path("calendar", views.calendar, name="calendar"),
    path("upcoming", views.upcoming, name="upcoming"),
    path("upcoming/watch", views.upcoming_watch, name="upcoming_watch"),
    path("reload_calendar", views.reload_calendar, name="reload_calendar"),
    path(
        "calendar/download/<str:token>",
        views.download_calendar,
        name="download_calendar",
    ),
]
