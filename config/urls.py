from django.contrib import admin
from django.conf.urls.static import static
from django.urls import include, path
from django.contrib.auth import views as auth_views

from config import settings
from tickets.views import IndexView
from tickets.views import register

urlpatterns = [
    path("", IndexView.as_view(), name="home"),
    path("", include("tickets.urls")),
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path(
        "accounts/logout/", auth_views.LogoutView.as_view(next_page="/"), name="logout"
    ),
    path("accounts/register/", register, name="register"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
