from django.urls import path

from . import views


urlpatterns = [
    path("", views.index, name="calculator"),
    path("calculate/", views.calculate, name="calculator-calculate"),
]
