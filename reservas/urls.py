"""
URLs de la app reservas.
"""

from django.urls import path

from . import views
from . import views_calendar

urlpatterns = [
    # Pantalla principal: panel de pendientes
    path("", views.pendientes, name="pendientes"),

    # Detalle de reserva
    path("reserva/<int:pk>/", views.reserva_detalle, name="reserva_detalle"),

    # Cambiar estado (AJAX)
    path(
        "reserva/<int:pk>/cambiar-estado/",
        views.cambiar_estado,
        name="cambiar_estado",
    ),

    # Interpretar respuesta de cliente con IA (AJAX)
    path(
        "reserva/<int:pk>/interpretar-respuesta/",
        views.interpretar_respuesta,
        name="interpretar_respuesta",
    ),

    # Buscar punto de recogida con Google Maps (AJAX)
    path(
        "reserva/<int:pk>/buscar-punto/",
        views.buscar_punto_recogida,
        name="buscar_punto_recogida",
    ),

    # Calendario
    path("calendario/", views.calendario, name="calendario"),

    # Configuración (solo administra)
    path("configuracion/", views.configuracion, name="configuracion"),

    # API puntos de recogida
    path("api/puntos-recogida/", views.api_puntos_recogida, name="api_puntos_recogida"),

    # Google Calendar OAuth (solo administra)
    path(
        "calendar/autorizar/",
        views_calendar.autorizar_google_calendar,
        name="calendar_autorizar",
    ),
    path(
        "calendar/oauth2callback/",
        views_calendar.oauth2callback_google_calendar,
        name="calendar_oauth2callback",
    ),

    # Ejecutar procesamiento de correos desde web (solo superusuario)
    path(
        "procesar-correos/",
        views.procesar_correos_vista,
        name="procesar_correos_vista",
    ),
]
