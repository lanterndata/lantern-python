from django.urls import path

from . import views

urlpatterns = [
    path("lantern/", views.index, name="index"),
]
