"""
Comando de gestion: procesar correos de reservas.

Lee info@elacebuche.es por IMAP (Hostalia), clasifica cada correo,
extrae los datos, crea/actualiza reservas en la base de datos y crea
eventos en Google Calendar de Lucia.

Uso:
    python manage.py procesar_correos

Se puede programar en PythonAnywhere como tarea programada cada 3 horas.
"""

import logging
from datetime import time

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from core.models import registrar_log, LogApp
from reservas.models import (
    Plataforma, EstadoReserva, Reserva, Conversacion, Mensaje,
)
from reservas.services.imap_service import (
    conectar_imap, obtener_correos_no_leidos, mover_a_procesado, desconectar,
)
from reservas.services.calendar_service import crear_o_actualizar_evento
from reservas.services.parser import (
    clasificar_correo, extraer_datos_reserva,
)

logger = logging.getLogger(__name__)


def _obtener_estado(nombre):
    """Obtiene o crea un estado por nombre."""
    estado, _ = EstadoReserva.objects.get_or_create(
        nombre=nombre,
        defaults={"color": "amarillo" if nombre == "pendiente_datos" else "verde"},
    )
    return estado


def _obtener_plataforma(nombre):
    """Obtiene o crea una plataforma por nombre."""
    plataforma, _ = Plataforma.objects.get_or_create(nombre=nombre)
    return plataforma


def _buscar_reserva_por_codigo(texto):
    """Busca una reserva existente por codigo en el texto del correo."""
    import re
    # Buscar codigos tipo BR-XXXXXX o SXXXXX
    m = re.search(r"(?:#BR-|BR-|GYG[--]\s*)([A-Z0-9]{6,})", texto, re.IGNORECASE)
    if m:
        codigo = m.group(1)
        if codigo.startswith("BR-"):
            codigo = f"BR-{codigo[3:]}" if not codigo.startswith("BR-") else codigo
        try:
            return Reserva.objects.filter(codigo_reserva__iexact=codigo).first()
        except Reserva.DoesNotExist:
            return None
    return None


class Command(BaseCommand):
    help = "Lee correos de reservas de Hostalia y los sincroniza con la BD y Google Calendar"

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-calendar",
            action="store_true",
            help="No crear eventos en Google Calendar (solo procesar correos y BD)",
        )
        parser.add_argument(
            "--no-mover",
            action="store_true",
            help="No mover correos a la carpeta Procesado",
        )
        parser.add_argument(
            "--limite",
            type=int,
            default=25,
            help="Maximo de correos no leidos a procesar por ejecucion (por defecto 25)",
        )

    def handle(self, *args, **options):
        no_calendar = options["no_calendar"]
        no_mover = options["no_mover"]
        limite = options["limite"]

        self.stdout.write(self.style.NOTICE("[MAIL] Iniciando procesamiento de correos..."))

        mail = conectar_imap()
        if not mail:
            self.stderr.write(self.style.ERROR("No se pudo conectar al servidor IMAP."))
            return

        correos = obtener_correos_no_leidos(mail, limite=limite)
        self.stdout.write(f"Se encontraron {len(correos)} correo(s) no leido(s).")

        procesados = 0
        creados = 0
        actualizados = 0
        omitidos = 0

        for correo in correos:
            message_id = correo["message_id"]
            asunto = correo["asunto"]
            remitente = correo["remitente"]
            cuerpo = correo["cuerpo"]
            fecha = correo["fecha"]

            # Evitar duplicados por message_id
            if Reserva.objects.filter(message_id=message_id).exists():
                omitidos += 1
                if not no_mover:
                    mover_a_procesado(mail, correo["raw_uid"])
                continue

            # Clasificar
            plataforma_nombre, tipo_correo, confianza = clasificar_correo(
                asunto, remitente, cuerpo
            )

            asunto_seguro = (asunto or "")[:60].encode("ascii", "replace").decode("ascii")
            self.stdout.write(
                f"  * {asunto_seguro}... -> {plataforma_nombre} / {tipo_correo}"
            )

            try:
                with transaction.atomic():
                    if tipo_correo == "reserva_nueva":
                        reserva = self._crear_reserva_desde_correo(
                            correo, plataforma_nombre, tipo_correo
                        )
                        if reserva:
                            creados += 1
                            # Crear evento en Google Calendar
                            if not no_calendar:
                                event_id = crear_o_actualizar_evento(reserva)
                                if event_id:
                                    reserva.google_calendar_event_id = event_id
                                    reserva.save(update_fields=["google_calendar_event_id"])

                            # Registrar log
                            registrar_log(
                                usuario=None,
                                accion=LogApp.ACCION_CREAR,
                                modelo="Reserva",
                                id_objeto=reserva.pk,
                                detalle=f"Reserva creada desde correo {plataforma_nombre}: {asunto}",
                            )

                    elif tipo_correo == "mensaje_cliente":
                        # Intentar vincular a reserva existente por codigo
                        reserva = _buscar_reserva_por_codigo(asunto + " " + cuerpo)
                        if reserva:
                            actualizados += 1
                            # Guardar mensaje en conversacion
                            conversacion, _ = Conversacion.objects.get_or_create(
                                reserva=reserva,
                                defaults={"asunto": asunto},
                            )
                            Mensaje.objects.create(
                                conversacion=conversacion,
                                direccion=Mensaje.DIRECCION_ENTRADA,
                                texto=cuerpo,
                                plataforma_mensaje=plataforma_nombre,
                            )
                            registrar_log(
                                usuario=None,
                                accion=LogApp.ACCION_MENSAJE,
                                modelo="Reserva",
                                id_objeto=reserva.pk,
                                detalle=f"Mensaje de cliente recibido: {asunto}",
                            )
                            # Actualizar evento si hay cambios relevantes
                            if not no_calendar:
                                crear_o_actualizar_evento(reserva)
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"    Mensaje de cliente sin reserva asociada: {asunto[:50]}"
                                )
                            )
                            omitidos += 1

                    elif tipo_correo == "cancelacion_cambio":
                        self.stdout.write(
                            self.style.WARNING(f"    Cancelacion/cambio detectado: {asunto[:50].encode('ascii', 'replace').decode('ascii')}")
                        )
                        omitidos += 1
                        # Aqui se podria buscar la reserva y cambiar su estado a cancelada

                    else:
                        # Consulta web, correo directo u otro
                        omitidos += 1

            except Exception as exc:
                exc_seguro = str(exc).encode("ascii", "replace").decode("ascii")
                logger.error(f"Error procesando correo {message_id}: {exc_seguro}")
                self.stderr.write(self.style.ERROR(f"  [X] Error: {exc_seguro}"))
                continue

            # Mover a Procesado
            if not no_mover:
                mover_a_procesado(mail, correo["raw_uid"])

            procesados += 1

        desconectar(mail)

        self.stdout.write(
            self.style.SUCCESS(
                f"[OK] Procesamiento finalizado: {procesados} procesado(s), "
                f"{creados} reserva(s) nueva(s), {actualizados} actualizada(s), "
                f"{omitidos} omitida(s)."
            )
        )

    def _crear_reserva_desde_correo(self, correo, plataforma_nombre, tipo_correo):
        """
        Crea una Reserva a partir de un correo clasificado como reserva_nueva.
        """
        plataforma = _obtener_plataforma(plataforma_nombre)
        datos = extraer_datos_reserva(correo["cuerpo"], plataforma_nombre, tipo_correo)

        # Estado inicial: pendiente_datos (amarillo) porque faltan datos del cliente
        estado = _obtener_estado("pendiente_datos")

        fecha_actividad = None
        if datos.get("fecha_actividad"):
            try:
                from datetime import datetime
                fecha_actividad = datetime.strptime(
                    datos["fecha_actividad"], "%Y-%m-%d"
                ).date()
            except ValueError:
                fecha_actividad = None

        hora_actividad = None
        if datos.get("hora_actividad"):
            try:
                from datetime import datetime
                hora_actividad = datetime.strptime(
                    datos["hora_actividad"], "%H:%M"
                ).time()
            except ValueError:
                hora_actividad = None

        reserva = Reserva.objects.create(
            plataforma=plataforma,
            codigo_reserva=datos.get("codigo_reserva", ""),
            fecha_actividad=fecha_actividad or correo["fecha"].date(),
            hora_actividad=hora_actividad or time(10, 0),
            numero_personas=datos.get("numero_personas", 1),
            nombre_cliente=datos.get("nombre_cliente", "Cliente por confirmar"),
            telefono_cliente=datos.get("telefono_cliente", ""),
            email_cliente=datos.get("email_cliente", ""),
            idioma=datos.get("idioma", "en"),
            edades=datos.get("edades", []),
            experiencia=datos.get("experiencia", ""),
            quiere_transporte=datos.get("quiere_transporte", False),
            direccion_alojamiento=datos.get("direccion_alojamiento", ""),
            nacionalidad=datos.get("nacionalidad", ""),
            precio_actividad=datos.get("precio_actividad", 0),
            cobrado=datos.get("cobrado", 0),
            porcentaje_lucia=datos.get("porcentaje_lucia", 0),
            pago_otros=datos.get("pago_otros", 0),
            total_experiencia=datos.get("total_experiencia", 0),
            recogida_en_coche=datos.get("recogida_en_coche", False),
            monitor_recogida=datos.get("monitor_recogida", ""),
            monitor_experiencia=datos.get("monitor_experiencia", ""),
            estado=estado,
            color_evento="amarillo",
            message_id=correo["message_id"],
            fecha_procesado=timezone.now(),
        )

        # Crear conversacion vacia para ir guardando mensajes
        Conversacion.objects.create(
            reserva=reserva,
            asunto=correo["asunto"],
            fecha_ultimo_correo=correo["fecha"],
        )

        return reserva
