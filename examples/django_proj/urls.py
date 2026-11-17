from django.urls import path, re_path
from . import views

urlpatterns = [
    path("articles/<int:year>/", views.year_archive),
    path("home/<name>/", views.home),
    path("hello/", views.Hello.as_view()),
    re_path(r"^legacy/(?P<pk>\d+)/$", views.legacy),
]
