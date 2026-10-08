from django.urls import path

from . import views


urlpatterns = [
    path("fix/", views.fix, name="factory-fix"),
    path("status/", views.status, name="factory-status"),
    path("demo-epoch/", views.demo_epoch, name="factory-demo-epoch"),
    path("reset/", views.reset_demo, name="factory-reset"),
]

