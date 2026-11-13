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
from math import radians, cos, sin, asin, sqrt

from django.conf import settings

logger = logging.getLogger(__name__)

# Radio de la Tierra en kilómetros
RADIO_TIERRA_KM = 6371.0


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
    api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", "")
    if not api_key or not direccion:
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
    api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", "")

    if api_key:
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
