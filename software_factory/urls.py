from django.urls import include, path


urlpatterns = [
    path("", include("calculator.urls")),
    path("factory/", include("factory.urls")),
]

