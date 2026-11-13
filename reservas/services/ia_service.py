# -*- coding: utf-8 -*-
"""
Servicio de IA para interpretar respuestas de clientes de El Acebuche.

Lee textos libres en cualquier idioma (respuestas a preguntas, consultas, etc.)
y devuelve datos estructurados: nacionalidad, edades, teléfono, experiencia,
si quiere transporte, dirección de alojamiento.

Proveedor recomendado: Anthropic Claude (u otro equivalente).
Se configura con IA_API_KEY e IA_PROVEEDOR en .env.
"""

import json
import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)


def _clave_ia_valida():
    """True si hay una clave de IA real (no vacía ni de ejemplo)."""
    api_key = (getattr(settings, "IA_API_KEY", "") or "").strip()
    if not api_key:
        return False
    return not api_key.upper().startswith("API_KEY_")


# Países que reconoce el modo demo (sin IA real)
_PAISES_DEMO = {
    "reino unido": "Reino Unido",
    "united kingdom": "Reino Unido",
    "inglaterra": "Reino Unido",
    "england": "Reino Unido",
    "uk": "Reino Unido",
    "irlanda": "Irlanda",
    "ireland": "Irlanda",
    "alemania": "Alemania",
    "germany": "Alemania",
    "francia": "Francia",
    "france": "Francia",
    "italia": "Italia",
    "italy": "Italia",
    "estados unidos": "Estados Unidos",
    "united states": "Estados Unidos",
    "usa": "Estados Unidos",
    "mexico": "México",
    "méxico": "México",
    "espana": "España",
    "españa": "España",
    "spain": "España",
    "holanda": "Países Bajos",
    "paises bajos": "Países Bajos",
    "países bajos": "Países Bajos",
    "netherlands": "Países Bajos",
    "belgica": "Bélgica",
    "bélgica": "Bélgica",
    "belgium": "Bélgica",
    "suiza": "Suiza",
    "switzerland": "Suiza",
    "canada": "Canadá",
    "canadá": "Canadá",
    "australia": "Australia",
    "portugal": "Portugal",
}


def _contiene_palabra(texto, palabra):
    patron = r"(?<![a-záéíóúñ])" + re.escape(palabra) + r"(?![a-záéíóúñ])"
    return re.search(patron, texto) is not None


def _interpretar_demo(texto, idioma_origen="en"):
    """
    Interpretación SIMULADA para el modo demo (sin IA_API_KEY real).
    Extrae datos con reglas sencillas para poder probar el flujo completo.
    """
    texto = texto or ""
    bajo = texto.lower()

    nacionalidad = ""
    for clave, valor in _PAISES_DEMO.items():
        if _contiene_palabra(bajo, clave):
            nacionalidad = valor
            break

    telefono = ""
    m = re.search(r"(\+\d[\d\s\-().]{6,}\d)", texto)
    if m:
        telefono = re.sub(r"\s+", " ", m.group(1)).strip()

    edades = []
    for patron in (
        r"(\d{1,2})\s*(?:años|years|yrs|yo)\b",
        r"(?:edad|age)\D{0,8}(\d{1,2})\b",
        r"\b(?:i'?m|i am|tengo)\s*(\d{1,2})\b",
    ):
        for numero in re.findall(patron, texto, re.IGNORECASE):
            edad = int(numero)
            if 5 <= edad <= 90 and edad not in edades:
                edades.append(edad)

    experiencia = ""
    for linea in texto.splitlines():
        if any(
            clave in linea.lower()
            for clave in ("experiencia", "experience", "montado", "ridden", "riding", "trote", "galope")
        ):
            experiencia = linea.strip()[:200]
            break

    negativos = (
        "no transport", "no transporte", "don't need transport", "do not need transport",
        "sin transporte", "no necesitamos", "we don't need", "no thanks", "no thank you",
    )
    positivos = (
        "transport", "transporte", "pickup", "pick up", "pick-up", "recogida", "nos recogen",
    )
    quiere_transporte = None
    if any(p in bajo for p in negativos):
        quiere_transporte = False
    elif any(p in bajo for p in positivos):
        quiere_transporte = True

    direccion = ""
    m = re.search(
        r"((?:hotel|hostal|apartamento|apartment|airbnb|calle|avenida|street|address|direcci[oó]n)"
        r"\s+[^\n\.;]{2,80})",
        texto,
        re.IGNORECASE,
    )
    if m:
        direccion = m.group(1).strip()

    return {
        "nacionalidad": nacionalidad,
        "edades": edades,
        "telefono": telefono,
        "experiencia": experiencia,
        "quiere_transporte": quiere_transporte,
        "direccion_alojamiento": direccion,
        "confianza": 0.75,
        "texto_original": texto,
        "idioma_detectado": idioma_origen,
        "requiere_revision_manual": False,
        "modo_demo": True,
    }


def interpretar_respuesta_cliente(texto, idioma_origen="en"):
    """
    Interpreta un texto libre de un cliente y devuelve un diccionario con
    los campos estructurados que faltan en la reserva.

    Retorna un dict como:
    {
        "nacionalidad": "Reino Unido",
        "edades": [34, 31],
        "telefono": "+44 7700 900123",
        "experiencia": "Él sin experiencia; ella ha montado varios años",
        "quiere_transporte": True,
        "direccion_alojamiento": "Parking Avenida de Roma, Sevilla",
        "confianza": 0.9,
        "texto_original": "...",
        "idioma_detectado": "en"
    }

    Si no hay clave de IA configurada, devuelve valores vacíos para que
    Lucía lo complete manualmente desde el panel de pendientes.
    """
    api_key = getattr(settings, "IA_API_KEY", "")
    proveedor = getattr(settings, "IA_PROVEEDOR", "claude")

    if not _clave_ia_valida():
        if getattr(settings, "MODO_DEMO", False):
            logger.info("IA en MODO DEMO: interpretación simulada sin IA_API_KEY real.")
            return _interpretar_demo(texto, idioma_origen)

        logger.warning("IA_API_KEY no configurada. Se devuelve vacío para rellenar manualmente.")
        return {
            "nacionalidad": "",
            "edades": [],
            "telefono": "",
            "experiencia": "",
            "quiere_transporte": None,
            "direccion_alojamiento": "",
            "confianza": 0.0,
            "texto_original": texto or "",
            "idioma_detectado": idioma_origen,
            "requiere_revision_manual": True,
        }

    try:
        if proveedor.lower() == "claude":
            return _interpretar_con_claude(texto, idioma_origen, api_key)
        elif proveedor.lower() == "openai":
            return _interpretar_con_openai(texto, idioma_origen, api_key)
        else:
            logger.warning(f"Proveedor IA '{proveedor}' no soportado. Devuelve vacío.")
            return {
                "nacionalidad": "",
                "edades": [],
                "telefono": "",
                "experiencia": "",
                "quiere_transporte": None,
                "direccion_alojamiento": "",
                "confianza": 0.0,
                "texto_original": texto or "",
                "idioma_detectado": idioma_origen,
                "requiere_revision_manual": True,
            }
    except Exception as exc:
        logger.error(f"Error interpretando respuesta con IA: {exc}")
        return {
            "nacionalidad": "",
            "edades": [],
            "telefono": "",
            "experiencia": "",
            "quiere_transporte": None,
            "direccion_alojamiento": "",
            "confianza": 0.0,
            "texto_original": texto or "",
            "idioma_detectado": idioma_origen,
            "requiere_revision_manual": True,
            "error": str(exc),
        }


def _interpretar_con_claude(texto, idioma_origen, api_key):
    """
    Llama a la API de Anthropic Claude para extraer datos estructurados.
    """
    try:
        import anthropic
    except ImportError:
        logger.error("anthropic no instalado. Ejecuta: pip install anthropic")
        return _resultado_vacio(texto, idioma_origen, error="anthropic no instalado")

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""
Eres un asistente que extrae datos de reservas de rutas a caballo del Centro Ecuestre El Acebuche (Doñana, Sevilla).

El cliente ha respondido a un mensaje de preguntas. El texto puede estar en cualquier idioma.
Extrae la siguiente información y devuélvela ÚNICAMENTE en formato JSON válido, sin texto adicional:

Campos a extraer:
- nacionalidad: país del cliente (string)
- edades: lista de edades numéricas (array de enteros)
- telefono: número de teléfono con prefijo internacional (string)
- experiencia: experiencia con caballos del cliente (string)
- quiere_transporte: true si pide servicio de recogida/transporte, false si no, null si no se sabe
- direccion_alojamiento: dirección del hotel o apartamento si quiere transporte (string)
- confianza: tu nivel de confianza en la extracción (0.0 a 1.0)

Texto del cliente:
"{texto}"

Idioma detectado aproximado: {idioma_origen}

Responde solo con el JSON.
"""

    try:
        mensaje = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=500,
            temperature=0,
            system="Eres un extractor de datos estructurados para reservas de turismo ecuestre. Responde solo JSON válido.",
            messages=[{"role": "user", "content": prompt}],
        )

        contenido = mensaje.content[0].text if mensaje.content else "{}"
        # Limpiar posibles marcadores de código
        contenido = contenido.replace("```json", "").replace("```", "").strip()
        datos = json.loads(contenido)

        return {
            "nacionalidad": datos.get("nacionalidad", ""),
            "edades": datos.get("edades", []) if isinstance(datos.get("edades"), list) else [],
            "telefono": datos.get("telefono", ""),
            "experiencia": datos.get("experiencia", ""),
            "quiere_transporte": datos.get("quiere_transporte"),
            "direccion_alojamiento": datos.get("direccion_alojamiento", ""),
            "confianza": float(datos.get("confianza", 0.5)),
            "texto_original": texto or "",
            "idioma_detectado": idioma_origen,
            "requiere_revision_manual": datos.get("confianza", 1.0) < 0.7,
        }

    except json.JSONDecodeError as exc:
        logger.error(f"Error parseando JSON de Claude: {exc}")
        return _resultado_vacio(texto, idioma_origen, error=f"JSON inválido: {exc}")
    except Exception as exc:
        logger.error(f"Error en llamada a Claude: {exc}")
        return _resultado_vacio(texto, idioma_origen, error=str(exc))


def _interpretar_con_openai(texto, idioma_origen, api_key):
    """
    Llama a la API de OpenAI para extraer datos estructurados.
    """
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai no instalado. Ejecuta: pip install openai")
        return _resultado_vacio(texto, idioma_origen, error="openai no instalado")

    client = OpenAI(api_key=api_key)

    prompt = f"""
Extrae datos de reserva de ruta a caballo del Centro Ecuestre El Acebuche.
Texto del cliente (cualquier idioma): "{texto}"
Devuelve SOLO JSON válido con: nacionalidad, edades (array), telefono, experiencia, quiere_transporte (true/false/null), direccion_alojamiento, confianza (0-1).
"""

    try:
        respuesta = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )

        contenido = respuesta.choices[0].message.content or "{}"
        contenido = contenido.replace("```json", "").replace("```", "").strip()
        datos = json.loads(contenido)

        return {
            "nacionalidad": datos.get("nacionalidad", ""),
            "edades": datos.get("edades", []) if isinstance(datos.get("edades"), list) else [],
            "telefono": datos.get("telefono", ""),
            "experiencia": datos.get("experiencia", ""),
            "quiere_transporte": datos.get("quiere_transporte"),
            "direccion_alojamiento": datos.get("direccion_alojamiento", ""),
            "confianza": float(datos.get("confianza", 0.5)),
            "texto_original": texto or "",
            "idioma_detectado": idioma_origen,
            "requiere_revision_manual": datos.get("confianza", 1.0) < 0.7,
        }

    except json.JSONDecodeError as exc:
        logger.error(f"Error parseando JSON de OpenAI: {exc}")
        return _resultado_vacio(texto, idioma_origen, error=f"JSON inválido: {exc}")
    except Exception as exc:
        logger.error(f"Error en llamada a OpenAI: {exc}")
        return _resultado_vacio(texto, idioma_origen, error=str(exc))


def _resultado_vacio(texto, idioma_origen, error=None):
    resultado = {
        "nacionalidad": "",
        "edades": [],
        "telefono": "",
        "experiencia": "",
        "quiere_transporte": None,
        "direccion_alojamiento": "",
        "confianza": 0.0,
        "texto_original": texto or "",
        "idioma_detectado": idioma_origen,
        "requiere_revision_manual": True,
    }
    if error:
        resultado["error"] = error
    return resultado


def aplicar_interpretacion_a_reserva(reserva, interpretacion):
    """
    Aplica los datos extraídos por IA a una reserva existente.
    Solo rellena campos que estén vacíos en la reserva.
    """
    cambios = []

    if interpretacion.get("nacionalidad") and not reserva.nacionalidad:
        reserva.nacionalidad = interpretacion["nacionalidad"]
        cambios.append("nacionalidad")

    if interpretacion.get("edades") and not reserva.edades:
        reserva.edades = interpretacion["edades"]
        cambios.append("edades")

    if interpretacion.get("telefono") and not reserva.telefono_cliente:
        reserva.telefono_cliente = interpretacion["telefono"]
        cambios.append("telefono")

    if interpretacion.get("experiencia") and not reserva.experiencia:
        reserva.experiencia = interpretacion["experiencia"]
        cambios.append("experiencia")

    if interpretacion.get("quiere_transporte") is not None and not reserva.quiere_transporte:
        reserva.quiere_transporte = interpretacion["quiere_transporte"]
        cambios.append("quiere_transporte")

    if interpretacion.get("direccion_alojamiento") and not reserva.direccion_alojamiento:
        reserva.direccion_alojamiento = interpretacion["direccion_alojamiento"]
        cambios.append("direccion_alojamiento")

    return cambios
