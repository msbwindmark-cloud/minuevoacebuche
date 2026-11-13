"""
Servicio IMAP para leer correos de reservas de Hostalia (info@elacebuche.es).

Usa imaplib de la librería estándar de Python para no depender de paquetes externos.
Se conecta por IMAP4_SSL (puerto 993), lee los correos no vistos de INBOX,
extrae asunto/remitente/cuerpo y los mueve a la carpeta "Procesado" una vez
guardados en la base de datos.
"""

import email
import imaplib
import logging
from email.header import decode_header
from email.utils import parsedate_to_datetime

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def _decodificar_cabecera(valor):
    if not valor:
        return ""
    partes = decode_header(valor)
    resultado = []
    for parte, enc in partes:
        if isinstance(parte, bytes):
            try:
                resultado.append(parte.decode(enc or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                resultado.append(parte.decode("utf-8", errors="replace"))
        else:
            resultado.append(parte)
    return "".join(resultado)


def conectar_imap():
    """
    Conecta al servidor IMAP de Hostalia y selecciona la carpeta de entrada.
    Devuelve el objeto IMAP4_SSL o None si falla.
    """
    host = getattr(settings, "IMAP_HOST", "imap.servidor-correo.net")
    port = getattr(settings, "IMAP_PORT", 993)
    user = getattr(settings, "IMAP_USER", "")
    password = getattr(settings, "IMAP_PASSWORD", "")
    carpeta = getattr(settings, "IMAP_CARPETA_ENTRADA", "INBOX")

    if not user or not password:
        logger.warning("IMAP_USER o IMAP_PASSWORD no configurados en .env")
        return None

    try:
        mail = imaplib.IMAP4_SSL(host, port)
        mail.login(user, password)
        mail.select(carpeta)
        logger.info(f"Conectado a IMAP {host}, carpeta {carpeta}")
        return mail
    except Exception as exc:
        logger.error(f"Error conectando a IMAP: {exc}")
        return None


def obtener_correos_no_leidos(mail, limite=None):
    """
    Devuelve una lista de diccionarios con los correos no leídos.
    Si se indica `limite`, solo se procesan los `limite` correos más recientes.
    """
    carpeta_procesado = getattr(settings, "IMAP_CARPETA_PROCESADO", "Procesado")

    # Buscar mensajes no vistos
    status, mensajes = mail.search(None, "UNSEEN")
    if status != "OK":
        logger.warning("No se pudo buscar mensajes UNSEEN en IMAP")
        return []

    uids = mensajes[0].split()
    if limite and len(uids) > limite:
        # Los UIDs vienen ordenados; nos quedamos con los más recientes
        uids = uids[-limite:]
    correos = []

    for uid in uids:
        try:
            status, datos = mail.fetch(uid, "(RFC822)")
            if status != "OK":
                continue

            raw_email = datos[0][1]
            mensaje = email.message_from_bytes(raw_email)

            message_id = mensaje.get("Message-ID", "")
            asunto = _decodificar_cabecera(mensaje.get("Subject", ""))
            remitente = _decodificar_cabecera(mensaje.get("From", ""))
            fecha_raw = mensaje.get("Date", "")
            try:
                fecha = parsedate_to_datetime(fecha_raw) if fecha_raw else timezone.now()
            except Exception:
                fecha = timezone.now()

            # Extraer cuerpo texto plano
            cuerpo = ""
            if mensaje.is_multipart():
                for parte in mensaje.walk():
                    content_type = parte.get_content_type()
                    disposicion = str(parte.get("Content-Disposition"))
                    if content_type == "text/plain" and "attachment" not in disposicion:
                        payload = parte.get_payload(decode=True)
                        if payload:
                            charset = parte.get_content_charset() or "utf-8"
                            cuerpo = payload.decode(charset, errors="replace")
                            break
            else:
                payload = mensaje.get_payload(decode=True)
                if payload:
                    charset = mensaje.get_content_charset() or "utf-8"
                    cuerpo = payload.decode(charset, errors="replace")

            correos.append({
                "message_id": message_id.strip() or f"uid-{uid.decode() if isinstance(uid, bytes) else uid}",
                "asunto": asunto,
                "remitente": remitente,
                "cuerpo": cuerpo,
                "fecha": fecha,
                "raw_uid": uid.decode() if isinstance(uid, bytes) else str(uid),
            })

        except Exception as exc:
            logger.error(f"Error procesando correo UID {uid}: {exc}")
            continue

    return correos


def mover_a_procesado(mail, raw_uid):
    """
    Mueve un correo (por UID) de INBOX a la carpeta Procesado.
    Si la carpeta no existe, intenta crearla.
    """
    carpeta_procesado = getattr(settings, "IMAP_CARPETA_PROCESADO", "Procesado")

    try:
        # Copiar a Procesado
        mail.uid("COPY", raw_uid, carpeta_procesado)
        # Marcar como borrado en INBOX
        mail.uid("STORE", raw_uid, "+FLAGS", "\\Deleted")
        mail.expunge()
        logger.info(f"Correo UID {raw_uid} movido a {carpeta_procesado}")
        return True
    except Exception as exc:
        # Si la carpeta Procesado no existe, intentar crearla
        if "does not exist" in str(exc).lower() or "NO" in str(exc).upper():
            try:
                mail.create(carpeta_procesado)
                mail.uid("COPY", raw_uid, carpeta_procesado)
                mail.uid("STORE", raw_uid, "+FLAGS", "\\Deleted")
                mail.expunge()
                logger.info(f"Carpeta {carpeta_procesado} creada y correo movido.")
                return True
            except Exception as exc2:
                logger.error(f"Error creando carpeta/moviendo correo: {exc2}")
                return False
        logger.error(f"Error moviendo correo UID {raw_uid} a procesado: {exc}")
        return False


def desconectar(mail):
    try:
        mail.close()
        mail.logout()
    except Exception:
        pass
