"""
Servicio de Google Calendar para El Acebuche.

Crea y actualiza eventos en el calendario "Centro Ecuestre el Acebuche"
(cuenta luciagilran2014@gmail.com) siguiendo el formato del Word.

Requisitos (instalar en producción):
    pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

Flujo OAuth:
1. Lucia accede a /calendar/autorizar/ y se autentica con su cuenta de Google.
2. Se guarda el token en google_token.json (raíz del proyecto).
3. El comando procesar_correos usa ese token para crear eventos automáticamente.
"""

import json
import logging
import os
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _credenciales_disponibles():
    """Devuelve True si hay credenciales de Google configuradas."""
    from core.models import Configuracion

    config = Configuracion.get()
    if config.usar_credenciales_panel:
        client_id = config.google_client_id or ""
        client_secret = config.google_client_secret or ""
    else:
        client_id = getattr(settings, "GOOGLE_CLIENT_ID", "")
        client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", "")
    return bool(client_id and client_secret)


def obtener_servicio_calendar():
    """
    Intenta obtener un servicio autorizado de Google Calendar.
    Devuelve el objeto service o None si no se puede (no hay librerías o no hay token).
    """
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        logger.warning(
            "google-api-python-client no instalado. "
            "Instala: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        )
        return None

    from core.models import Configuracion

    config = Configuracion.get()
    token_file = None
    # token file path from settings or config default
    token_file = getattr(settings, "GOOGLE_TOKEN_FILE", None)
    creds = None

    if token_file and os.path.exists(token_file):
        try:
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        except Exception as exc:
            logger.warning(f"No se pudo leer el token de Google: {exc}")

    if not creds or not creds.valid:
        logger.warning(
            "No hay credenciales válidas de Google Calendar. "
            "Ve a /calendar/autorizar/ para autenticar con la cuenta de Lucia."
        )
        return None

    try:
        service = build("calendar", "v3", credentials=creds)
        return service
    except Exception as exc:
        logger.error(f"Error construyendo servicio de Google Calendar: {exc}")
        return None


def _formato_fecha_google(fecha_hora):
    """Convierte datetime a formato RFC3339 para Google Calendar."""
    if not fecha_hora:
        return None
    if timezone.is_naive(fecha_hora):
        fecha_hora = timezone.make_aware(fecha_hora)
    return fecha_hora.isoformat()


def crear_o_actualizar_evento(reserva):
    """
    Crea un evento en Google Calendar para la reserva, o lo actualiza si ya existe.
    Devuelve el ID del evento creado/actualizado, o None si no se pudo.
    """
    service = obtener_servicio_calendar()
    if not service:
        return None

    from core.models import Configuracion
    config = Configuracion.get()
    if config.usar_credenciales_panel:
        calendar_id = config.google_calendar_id or "luciagilran2014@gmail.com"
    else:
        calendar_id = getattr(settings, "GOOGLE_CALENDAR_ID", "luciagilran2014@gmail.com")

    from .parser import formatear_fecha_evento, generar_descripcion_evento

    inicio, fin, _dia_entero = formatear_fecha_evento(
        reserva.fecha_actividad.strftime("%Y-%m-%d"),
        reserva.hora_actividad.strftime("%H:%M") if reserva.hora_actividad else None,
        quiere_transporte=reserva.quiere_transporte,
    )

    if not inicio:
        logger.warning(f"No se pudo determinar fecha/hora para la reserva {reserva.pk}")
        return None

    # Color del evento según estado (Google Calendar usa colorId 1-11)
    color_map = {
        "amarillo": "6",   # amarillo
        "rojo": "11",      # rojo
        "verde": "2",      # verde
        "gris": "9",       # gris
    }
    color_id = color_map.get(reserva.color_evento or "amarillo", "6")

    evento = {
        "summary": reserva.titulo_evento,
        "description": generar_descripcion_evento(reserva),
        "start": {
            "dateTime": _formato_fecha_google(inicio),
            "timeZone": "Europe/Madrid",
        },
        "end": {
            "dateTime": _formato_fecha_google(fin),
            "timeZone": "Europe/Madrid",
        },
        "colorId": color_id,
    }

    try:
        if reserva.google_calendar_event_id:
            # Actualizar evento existente
            service.events().update(
                calendarId=calendar_id,
                eventId=reserva.google_calendar_event_id,
                body=evento,
            ).execute()
            logger.info(f"Evento actualizado en Google Calendar: {reserva.google_calendar_event_id}")
        else:
            # Crear nuevo evento
            creado = service.events().insert(
                calendarId=calendar_id,
                body=evento,
            ).execute()
            event_id = creado.get("id")
            logger.info(f"Evento creado en Google Calendar: {event_id}")
            return event_id

        return reserva.google_calendar_event_id

    except Exception as exc:
        logger.error(f"Error creando/actualizando evento Google Calendar: {exc}")
        return None
