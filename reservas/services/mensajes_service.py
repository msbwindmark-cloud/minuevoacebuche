# -*- coding: utf-8 -*-
"""
Servicio de mensajes automáticos al cliente para El Acebuche.

Plantillas basadas en las secciones 8.1, 8.2 y 8.3 del documento de requisitos.
Los textos son editables desde la configuración de la app.

Se envían desde info@elacebuche.es (dirección registrada en las plataformas).
"""

import logging
from urllib.parse import quote

from django.conf import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Plantillas de mensajes (se pueden sobrescribir desde la configuración)
# ---------------------------------------------------------------------------

MENSAJE_PREGUNTAS = (
    "Hi, I need to know this things :\n"
    "- What is your phone number? (+ prefix - number)\n"
    "- Do you speak Spanish?\n"
    "- Where are you from?\n"
    "- How old are you?\n"
    "- Do you have experience riding horses? What experience?\n"
    "If you're interested in transport service, we need to know the address of your hotel or apartment "
    "to find a nearby pick-up point that is convenient for you.\n"
    "About transportation, we have an additional service of pickup of clients. "
    "The price's 60 € for vehicle, not for person, round trip. "
    "You have to pay it in cash in our farm."
)

RESPUESTA_SIN_TRANSPORTE = (
    "Hi {nombre},\n"
    "Thank you for sharing your information!\n"
    "Here is the location of our farm so you can get there easily: "
    "https://maps.app.goo.gl/zUVyMC1eGyYU9ub17\n"
    "The activity starts at {hora} on {fecha}.\n"
    "There is no need to arrive earlier.\n"
    "See you soon !"
)

RESPUESTA_CON_TRANSPORTE = (
    "Hi {nombre},\n"
    "Thank you for the information!\n"
    "We will pick you up on {fecha} at {hora_recogida} at this point {punto}.\n"
    "I send you the location in the following link: {enlace_maps}\n"
    "Remember that the transport service costs 60 € per vehicle (round trip), "
    "paid in cash at our farm.\n"
    "See you soon !"
)


def obtener_mensaje_preguntas():
    """
    Devuelve el mensaje de preguntas (sección 8.1 del Word).
    Se puede personalizar desde la configuración de la app.
    """
    return getattr(settings, "MENSAJE_PREGUNTAS", MENSAJE_PREGUNTAS)


def obtener_respuesta_sin_transportes(nombre, fecha, hora):
    """
    Devuelve la respuesta si el cliente NO necesita transporte (sección 8.2).
    """
    plantilla = getattr(settings, "RESPUESTA_SIN_TRANSPORTE", RESPUESTA_SIN_TRANSPORTE)
    return plantilla.format(
        nombre=nombre,
        fecha=fecha,
        hora=hora,
    )


def obtener_respuesta_con_transporte(nombre, fecha, hora_recogida, punto, enlace_maps):
    """
    Devuelve la respuesta si el cliente SÍ necesita transporte (sección 8.3).
    """
    plantilla = getattr(settings, "RESPUESTA_CON_TRANSPORTE", RESPUESTA_CON_TRANSPORTE)
    return plantilla.format(
        nombre=nombre,
        fecha=fecha,
        hora_recogida=hora_recogida,
        punto=punto,
        enlace_maps=enlace_maps or "",
    )


def generar_enlace_whatsapp(telefono, mensaje):
    """
    Genera un enlace wa.me para enviar un mensaje por WhatsApp.
    """
    if not telefono:
        return "#"
    texto_codificado = quote(mensaje)
    return f"https://wa.me/{telefono}?text={texto_codificado}"


def mensaje_aviso_coche_listo(nombre_cliente, telefono_cliente):
    """
    Mensaje de aviso de "coche listo" para WhatsApp (adaptado del concepto de reserva).
    """
    mensaje = (
        f"Hola {nombre_cliente or 'cliente'}, "
        f"tu actividad en Centro Ecuestre El Acebuche ya está lista. "
        f"¡Gracias por confiar en nosotros!"
    )
    return generar_enlace_whatsapp(telefono_cliente, mensaje)
