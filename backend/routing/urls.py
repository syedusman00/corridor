from django.urls import path

from . import views

urlpatterns = [
    path("", views.root, name="api-root"),
    path("health/", views.health, name="health"),
    path("geocode/", views.geocode_view, name="geocode"),
    path("analyze/", views.analyze, name="analyze"),
]
