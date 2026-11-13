"""
Parser de correos de reservas del Centro Ecuestre El Acebuche.

Extrae datos estructurados de los correos que llegan a info@elacebuche.es.
Soporta los canales del Word: Airbnb, GetYourGuide (GYG), Viator, Web y correo directo.

NOTA: Los patrones de regex están basados en los asuntos y formatos descritos en el Word.
Si Lucia te pasa ejemplos reales de correos, ajusta los patrones aquí para que coincidan al 100%.
"""

import re
from datetime import datetime
from email.utils import parsedate_to_datetime


# ---------------------------------------------------------------------------
# Patrones de clasificación por asunto
# ---------------------------------------------------------------------------

PATRONES_PLATAFORMA = [
    # (regex_asunto, plataforma_nombre, tipo_correo)
    (r"Reserva\s*[-–]\s*\S+\s*[-–]\s*GYG", "GetYourGuide", "reserva_nueva"),
    (r"GYG", "GetYourGuide", "reserva_nueva"),
    (r"Nueva\s+reserva\s+para\s+el", "Viator", "reserva_nueva"),
    (r"#BR-", "Viator", "reserva_nueva"),
    (r"Conversaci.{0,3}n\s+con\s+.+\s+sobre\s+la\s+reserva\s+de\s+Viator", "Viator", "mensaje_cliente"),
    (r"ha\s+reservado\s+tu\s+experiencia\s+para\s+el", "Airbnb", "reserva_nueva"),
    (r"RE:\s*Horseback\s+riding\s+around\s+Do.ñana\s+National\s+Park", "Airbnb", "mensaje_cliente"),
    (r"Nuevo\s+mensaje\s+desde\s+.*Centro\s+Ecuestre\s+El\s+Acebuche", "Web", "consulta_web"),
    (r"info@elacebuche\.es", "Email", "correo_directo"),
]


def clasificar_correo(asunto, remitente, cuerpo=""):
    """
    Clasifica el correo y devuelve (plataforma, tipo_correo, confianza).
    tipo_correo: reserva_nueva, mensaje_cliente, cancelacion_cambio, consulta_web, correo_directo, otro
    """
    texto = f"{asunto or ''} {cuerpo or ''}".lower()

    # Cancelaciones / cambios
    if re.search(r"cancel|cancelaci|cambio|modific", texto):
        return ("otro", "cancelacion_cambio", 0.8)

    for patron, plataforma, tipo in PATRONES_PLATAFORMA:
        if re.search(patron, asunto or "", re.IGNORECASE):
            return (plataforma, tipo, 0.9)

    # Si no coincide con nada conocido
    return ("otro", "otro", 0.3)


# ---------------------------------------------------------------------------
# Extracción de datos del cuerpo del correo
# ---------------------------------------------------------------------------

def _extraer_fecha_hora(texto):
    """Intenta extraer fecha y hora del texto. Devuelve (fecha_str, hora_str) o (None, None)."""
    # Patrones comunes: "12 de noviembre de 2026", "12/11/2026", "2026-11-12", etc.
    patrones_fecha = [
        r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})",
        r"(\d{4})-(\d{2})-(\d{2})",
        r"(\d{1,2})/(\d{1,2})/(\d{4})",
    ]
    for p in patrones_fecha:
        m = re.search(p, texto, re.IGNORECASE)
        if m:
            try:
                if "de" in p:
                    dia, mes, anio = m.groups()
                    meses = {
                        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
                        "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
                        "septiembre": 9, "setiembre": 9, "octubre": 10,
                        "noviembre": 11, "diciembre": 12,
                    }
                    mes_num = meses.get(mes.lower(), 1)
                    fecha = datetime(int(anio), mes_num, int(dia))
                elif "-" in p:
                    anio, mes, dia = m.groups()
                    fecha = datetime(int(anio), int(mes), int(dia))
                else:
                    dia, mes, anio = m.groups()
                    fecha = datetime(int(anio), int(mes), int(dia))
                return fecha.strftime("%Y-%m-%d"), None
            except Exception:
                continue

    # Hora: patrones como 10:00, 13:00, 9:30, 12:30
    m_hora = re.search(r"(\d{1,2}):(\d{2})", texto)
    if m_hora:
        hora = f"{m_hora.group(1).zfill(2)}:{m_hora.group(2)}"
        return None, hora

    return None, None


def _extraer_numero_personas(texto):
    # "2 viajeros", "2 personas", "2 pax", etc.
    m = re.search(r"(\d+)\s*(pax|personas|viajeros|participantes)", texto, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # "viajeros: 2", "personas: 3", "pax: 1"
    m = re.search(r"(?:viajeros|personas|pax|participantes)\s*[:]\s*(\d+)", texto, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # Airbnb: número de viajeros
    m = re.search(r"(\d+)\s+viajeros", texto, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _extraer_nombre(texto):
    # Buscar patrones tipo "Nombre: Juan Pérez" o "Cliente principal: Juan Pérez"
    m = re.search(r"nombre\s*(?:del\s+cliente)?\s*[:]\s*([^\n,;]+)", texto, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"cliente\s*principal\s*[:]\s*([^\n,;]+)", texto, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"viajero\s*principal\s*[:]\s*([^\n,;]+)", texto, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Airbnb: "Nombre de pila: Pedro"
    m = re.search(r"nombre\s*de\s*pila\s*[:]\s*([^\n,;]+)", texto, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ""


def _extraer_telefono(texto):
    m = re.search(r"tel[eé]fono\s*[:]?\s*([+\d][\d\s\-]{6,})", texto, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"tlf\s*[:]?\s*([+\d][\d\s\-]{6,})", texto, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ""


def _extraer_email(texto):
    m = re.search(r"correo\s*(?:del\s+cliente)?\s*[:]?\s*([^\s@]+@[^\s@]+)", texto, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r"([^\s@]+@[^\s@]+\.[^\s@]+)", texto)
    if m:
        return m.group(1)
    return ""


def _extraer_edades(texto):
    edades = []
    m = re.search(r"edad[e]?\s*[:]?\s*([^\n;]+)", texto, re.IGNORECASE)
    if m:
        for num in re.findall(r"\d{1,3}", m.group(1)):
            edades.append(int(num))
    if edades:
        return edades
    return []


def _extraer_codigo_reserva(texto, plataforma):
    if plataforma == "Viator":
        m = re.search(r"#BR-([A-Z0-9]+)", texto)
        if m:
            return f"BR-{m.group(1)}"
    if plataforma == "GetYourGuide":
        m = re.search(r"(?:Reserva|GYG)\s*[-–]\s*([A-Z0-9]+)", texto, re.IGNORECASE)
        if m:
            return m.group(1)
    if plataforma == "Airbnb":
        m = re.search(r"(?:reserva|booking)\s*[:]?\s*([A-Z0-9]{6,})", texto, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""


def _detecta_transporte(texto):
    texto = texto.lower()
    return any(p in texto for p in ["transporte", "pickup", "recogida", "60", "coche", "vehículo", "vehiculo"])


def _extraer_idioma(texto):
    texto = texto.lower()
    if "español" in texto or "spanish" in texto:
        return "es"
    if "inglés" in texto or "english" in texto:
        return "en"
    if "alemán" in texto or "german" in texto:
        return "de"
    if "francés" in texto or "french" in texto:
        return "fr"
    return "en"


def extraer_datos_reserva(cuerpo, plataforma, tipo_correo):
    """
    Extrae un diccionario con los datos de la reserva desde el cuerpo del correo.
    Los campos que no se encuentren quedan vacíos (la reserva irá a pendientes).
    """
    texto = cuerpo or ""
    fecha, hora = _extraer_fecha_hora(texto)

    datos = {
        "plataforma": plataforma,
        "codigo_reserva": _extraer_codigo_reserva(texto, plataforma),
        "fecha_actividad": fecha,
        "hora_actividad": hora,
        "numero_personas": _extraer_numero_personas(texto) or 1,
        "nombre_cliente": _extraer_nombre(texto),
        "telefono_cliente": _extraer_telefono(texto),
        "email_cliente": _extraer_email(texto),
        "idioma": _extraer_idioma(texto),
        "edades": _extraer_edades(texto),
        "experiencia": "",
        "quiere_transporte": _detecta_transporte(texto),
        "direccion_alojamiento": "",
        "nacionalidad": "",
        "precio_actividad": 0,
        "cobrado": 0,
        "porcentaje_lucia": 0,
        "pago_otros": 0,
        "total_experiencia": 0,
        "recogida_en_coche": False,
        "monitor_recogida": "",
        "monitor_experiencia": "",
    }

    # Intentar extraer experiencia
    m_exp = re.search(r"experiencia\s*[:]?\s*([^\n]+)", texto, re.IGNORECASE)
    if m_exp:
        datos["experiencia"] = m_exp.group(1).strip()

    # Intentar extraer nacionalidad
    m_nac = re.search(r"nacionalidad\s*[:]?\s*([^\n,;]+)", texto, re.IGNORECASE)
    if m_nac:
        datos["nacionalidad"] = m_nac.group(1).strip()

    # Dirección de alojamiento (para transporte)
    m_dir = re.search(r"(?:direcci[oó]n|address|alojamiento|hotel|apartamento)\s*[:]?\s*([^\n,;]+)", texto, re.IGNORECASE)
    if m_dir:
        datos["direccion_alojamiento"] = m_dir.group(1).strip()

    return datos


def formatear_fecha_evento(fecha_str, hora_str, quiere_transporte=False):
    """
    Devuelve (fecha_hora_inicio, fecha_hora_fin, es_dia_entero)
    según las reglas del Word:
    - Sin transporte: empieza a la hora de la actividad, dura 2 horas.
    - Con transporte: empieza actividad - 30 min, dura 3 horas (incluye vuelta).
    """
    if not fecha_str:
        return None, None, False

    from datetime import timedelta

    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d")
    except ValueError:
        return None, None, False

    if hora_str:
        try:
            h, m = map(int, hora_str.split(":"))
            inicio = fecha.replace(hour=h, minute=m)
        except ValueError:
            inicio = fecha.replace(hour=10, minute=0)
    else:
        inicio = fecha.replace(hour=10, minute=0)

    if quiere_transporte:
        inicio = inicio - timedelta(minutes=30)
        fin = inicio + timedelta(hours=3)
    else:
        fin = inicio + timedelta(hours=2)

    return inicio, fin, False


def generar_descripcion_evento(reserva):
    """
    Genera la descripción del evento en Google Calendar con el formato del Word.
    """
    lineas = []

    # Primera línea: plataforma y código
    codigo = reserva.codigo_reserva or "Sin código"
    lineas.append(f"{reserva.plataforma.nombre} - {codigo}")

    # Datos del cliente
    lineas.append(f"- Nombre: {reserva.nombre_cliente}")
    lineas.append(f"- Número: {reserva.numero_personas}")

    if reserva.nacionalidad:
        lineas.append(f"- Nacionalidad: {reserva.nacionalidad}")

    if reserva.edades:
        edades_str = "; ".join(str(e) for e in reserva.edades)
        lineas.append(f"- Edad: {edades_str}")

    if reserva.telefono_cliente:
        lineas.append(f"- Tlf: {reserva.telefono_cliente}")

    if reserva.experiencia:
        lineas.append(f"- Experiencia: {reserva.experiencia}")

    # Transporte
    if reserva.quiere_transporte:
        lineas.append("- Tienen que abonar 60 €")
        if reserva.direccion_alojamiento:
            lineas.append(f"- Ubicación: {reserva.direccion_alojamiento}")
        if reserva.punto_recogida and reserva.punto_recogida.enlace_maps:
            lineas.append(f"- Punto de recogida: {reserva.punto_recogida.nombre}")
            lineas.append(reserva.punto_recogida.enlace_maps)
    else:
        lineas.append("- Irán por su cuenta")

    # Enlace al centro (Google Maps del centro)
    lineas.append("https://maps.app.goo.gl/zUVyMC1eGyYU9ub17")

    return "\n".join(lineas)
