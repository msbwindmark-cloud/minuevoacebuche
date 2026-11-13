"""acebuche URL Configuration

Rutas principales de la app de reservas del Centro Ecuestre El Acebuche.
"""

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

from core.forms import LoginForm

urlpatterns = [
    path("admin/", admin.site.urls),

    # Autenticación
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="login.html",
            authentication_form=LoginForm,
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="login"),
        name="logout",
    ),

    # App de reservas
    path("", include("reservas.urls")),
]
