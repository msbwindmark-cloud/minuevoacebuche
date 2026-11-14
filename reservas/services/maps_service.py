# -*- coding: utf-8 -*-
"""
Servicio de Google Maps Platform para El Acebuche.

Funciones:
- Geocodificar una dirección de alojamiento (obtener latitud/longitud)
- Calcular tiempo a pie hasta cada punto fijo de recogida (Distance Matrix o Routes)
- Proponer el punto más cercano si está a ≤ 10 minutos andando

Configurado con GOOGLE_MAPS_API_KEY en .env.
"""

import logging
import hashlib
from math import radians, cos, sin, asin, sqrt

from django.conf import settings

logger = logging.getLogger(__name__)

# Radio de la Tierra en kilómetros
RADIO_TIERRA_KM = 6371.0

# Centro de Sevilla, para las coordenadas simuladas del modo demo
_SEVILLA_LAT = 37.3891
_SEVILLA_LON = -5.9845

# Coordenadas reales aproximadas de los puntos de recogida habituales
_COORDS_DEMO = {
    "avenida de roma": (37.3866, -5.9822),
    "luis montoto": (37.3866, -5.9822),
    "becquer": (37.3928, -5.9931),
    "bécquer": (37.3928, -5.9931),
    "lumbreras": (37.3975, -5.9920),
    "alameda": (37.3975, -5.9920),
    "duque": (37.3920, -5.9977),
    "teniente borges": (37.3920, -5.9977),
    "corte ingles": (37.3844, -5.9736),
    "corte inglés": (37.3844, -5.9736),
    "hotel america": (37.3844, -5.9736),
    "hotel américa": (37.3844, -5.9736),
    "santa justa": (37.3927, -5.9743),
    "macarena": (37.4027, -5.9889),
    "plaza de toros": (37.3823, -5.9864),
    "murillo": (37.3833, -5.9873),
    "nervion": (37.3834, -5.9737),
    "nervión": (37.3834, -5.9737),
}


def _clave_maps_valida():
    """True si hay una API key de Google Maps real (no vacía ni de ejemplo)."""
    from core.models import Configuracion

    config = Configuracion.get()
    if config.usar_credenciales_panel:
        api_key = (config.google_maps_api_key or "").strip()
    else:
        api_key = (getattr(settings, "GOOGLE_MAPS_API_KEY", "") or "").strip()
    if not api_key:
        return False
    return not api_key.upper().startswith("API_KEY_")


def _geocodificar_demo(direccion):
    """
    Geocodificación SIMULADA para el modo demo.
    Usa coordenadas reales de puntos conocidos de Sevilla o genera una
    posición estable (determinista) alrededor del centro de la ciudad.
    """
    texto = (direccion or "").lower()
    for clave, coords in _COORDS_DEMO.items():
        if clave in texto:
            return coords

    semilla = int(hashlib.md5(texto.encode("utf-8")).hexdigest(), 16)
    lat = _SEVILLA_LAT + ((semilla % 1000) / 1000 - 0.5) * 0.04
    lon = _SEVILLA_LON + (((semilla // 1000) % 1000) / 1000 - 0.5) * 0.05
    return round(lat, 6), round(lon, 6)


def haversine_km(lat1, lon1, lat2, lon2):
    """
    Calcula la distancia en línea recta entre dos puntos en kilómetros
    usando la fórmula de Haversine.
    """
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return RADIO_TIERRA_KM * c


def estimar_minutos_andando(distancia_km):
    """
    Estima minutos andando a partir de la distancia en km.
    Velocidad promedio andando: 5 km/h = 12 min/km.
    """
    if distancia_km is None:
        return None
    return round(distancia_km * 12, 1)


def geocodificar_direccion(direccion):
    """
    Geocodifica una dirección usando Google Maps Geocoding API.
    Devuelve (latitud, longitud) o (None, None) si falla o no hay API key.
    """
    from core.models import Configuracion

    config = Configuracion.get()
    usar_panel = config.usar_credenciales_panel

    if usar_panel:
        api_key = (config.google_maps_api_key or "").strip()
        modo_demo_activo = config.modo_demo
    else:
        api_key = (getattr(settings, "GOOGLE_MAPS_API_KEY", "") or "").strip()
        modo_demo_activo = getattr(settings, "MODO_DEMO", False)

    if not _clave_maps_valida():
        if modo_demo_activo and direccion:
            lat, lon = _geocodificar_demo(direccion)
            logger.info("Geocodificación SIMULADA (modo demo) para: %s", direccion)
            return lat, lon
        logger.warning("GOOGLE_MAPS_API_KEY no configurada o dirección vacía.")
        return None, None

    try:
        import requests
    except ImportError:
        logger.error("requests no instalado. Ejecuta: pip install requests")
        return None, None

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": direccion,
        "key": api_key,
        "language": "es",
        "region": "ES",
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        datos = resp.json()

        if datos.get("status") == "OK" and datos.get("results"):
            ubicacion = datos["results"][0]["geometry"]["location"]
            return float(ubicacion["lat"]), float(ubicacion["lng"])

        logger.warning(f"Geocoding no devolvió resultados para: {direccion} (status: {datos.get('status')})")
        return None, None

    except Exception as exc:
        logger.error(f"Error geocodificando '{direccion}': {exc}")
        return None, None


def calcular_tiempo_a_pie(origen_lat, origen_lon, destino_lat, destino_lon):
    """
    Calcula el tiempo a pie entre dos puntos.

    Intenta usar Google Maps Distance Matrix API (modo walking).
    Si no hay API key o falla, usa Haversine + estimación de velocidad andando.

    Devuelve minutos estimados o None.
    """
    # La validez se comprueba con _clave_maps_valida(); aquí solo se usa si es válida
    if _clave_maps_valida():
        try:
            import requests
            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            params = {
                "origins": f"{origen_lat},{origen_lon}",
                "destinations": f"{destino_lat},{destino_lon}",
                "mode": "walking",
                "key": api_key,
                "language": "es",
                "region": "ES",
            }
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            datos = resp.json()

            if datos.get("status") == "OK":
                elementos = datos.get("rows", [{}])[0].get("elements", [])
                if elementos and elementos[0].get("status") == "OK":
                    duracion_segundos = elementos[0]["duration"]["value"]
                    return round(duracion_segundos / 60, 1)
        except Exception as exc:
            logger.warning(f"Distance Matrix falló, usando Haversine: {exc}")

    # Fallback: Haversine + estimación
    distancia = haversine_km(origen_lat, origen_lon, destino_lat, destino_lon)
    return estimar_minutos_andando(distancia)


def buscar_punto_recogida_mas_cercano(direccion_alojamiento, puntos_recogida, max_minutos=10):
    """
    Dada una dirección de alojamiento y una lista de puntos de recogida,
    devuelve el punto más cercano a pie si está dentro de max_minutos.

    Retorna un dict:
    {
        "punto": <objeto PuntoRecogida o None>,
        "minutos": <float o None>,
        "distancia_km": <float o None>,
        "cumple_regla": <bool>,
        "alojamiento_lat": <float o None>,
        "alojamiento_lon": <float o None>,
    }
    """
    resultado = {
        "punto": None,
        "minutos": None,
        "distancia_km": None,
        "cumple_regla": False,
        "alojamiento_lat": None,
        "alojamiento_lon": None,
        "modo_demo": not _clave_maps_valida(),
    }

    if not direccion_alojamiento:
        logger.warning("Dirección de alojamiento vacía, no se puede buscar punto de recogida.")
        return resultado

    # Geocodificar el alojamiento
    lat, lon = geocodificar_direccion(direccion_alojamiento)
    if lat is None or lon is None:
        logger.warning(f"No se pudo geocodificar: {direccion_alojamiento}")
        return resultado

    resultado["alojamiento_lat"] = lat
    resultado["alojamiento_lon"] = lon

    mejor_punto = None
    mejor_minutos = None
    mejor_distancia = None

    for punto in puntos_recogida:
        if not punto.activo:
            continue
        if punto.latitud is None or punto.longitud is None:
            # Intentar geocodificar el punto si no tiene coordenadas
            p_lat, p_lon = geocodificar_direccion(punto.direccion or punto.nombre)
            if p_lat is not None and p_lon is not None:
                punto.latitud = p_lat
                punto.longitud = p_lon
                punto.save(update_fields=["latitud", "longitud"])
            else:
                continue

        minutos = calcular_tiempo_a_pie(lat, lon, float(punto.latitud), float(punto.longitud))
        if minutos is None:
            continue

        distancia = haversine_km(lat, lon, float(punto.latitud), float(punto.longitud))

        if mejor_minutos is None or minutos < mejor_minutos:
            mejor_minutos = minutos
            mejor_distancia = distancia
            mejor_punto = punto

    if mejor_punto is not None:
        resultado["punto"] = mejor_punto
        resultado["minutos"] = mejor_minutos
        resultado["distancia_km"] = round(mejor_distancia, 2)
        resultado["cumple_regla"] = mejor_minutos <= max_minutos

    return resultado
