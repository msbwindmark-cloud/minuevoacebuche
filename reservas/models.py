"""
Modelos de la app de reservas del Centro Ecuestre El Acebuche.

Flujo: leer correos → crear evento en Google Calendar → panel de pendientes.
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Plataforma(models.Model):
    """Canal de venta de la reserva."""

    nombre = models.CharField("plataforma", max_length=30, unique=True)  # Airbnb, GYG, Viator, Email, Web

    class Meta:
        verbose_name = "plataforma"
        verbose_name_plural = "plataformas"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class EstadoReserva(models.Model):
    """Estado de la reserva y color del evento en Google Calendar."""

    nombre = models.CharField("estado", max_length=30, unique=True)  # pendiente_datos, pendiente_decision, completa, cancelada
    color = models.CharField("color del evento", max_length=20, default="amarillo")  # amarillo, rojo, verde, gris

    class Meta:
        verbose_name = "estado de reserva"
        verbose_name_plural = "estados de reserva"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.color})"


class PuntoRecogida(models.Model):
    """Punto fijo de recogida en Sevilla (60 €/vehículo)."""

    nombre = models.CharField("nombre", max_length=100)
    direccion = models.CharField("dirección", max_length=200, blank=True)
    latitud = models.DecimalField("latitud", max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField("longitud", max_digits=9, decimal_places=6, null=True, blank=True)
    enlace_maps = models.URLField("enlace Google Maps", blank=True)
    activo = models.BooleanField("activo", default=True)

    class Meta:
        verbose_name = "punto de recogida"
        verbose_name_plural = "puntos de recogida"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Reserva(models.Model):
    """Reserva de ruta a caballo."""

    plataforma = models.ForeignKey(
        Plataforma, on_delete=models.PROTECT, verbose_name="plataforma"
    )
    codigo_reserva = models.CharField("código de reserva", max_length=50, blank=True)

    fecha_actividad = models.DateField("fecha de actividad")
    hora_actividad = models.TimeField("hora de actividad")

    numero_personas = models.PositiveIntegerField("número de personas")
    nombre_cliente = models.CharField("nombre del cliente", max_length=100)
    telefono_cliente = models.CharField("teléfono", max_length=30, blank=True)
    email_cliente = models.EmailField("correo del cliente", blank=True)
    idioma = models.CharField("idioma", max_length=10, default="en")

    edades = models.JSONField("edades", default=list, blank=True)  # ej. [34, 31]
    experiencia = models.TextField("experiencia con caballos", blank=True)

    quiere_transporte = models.BooleanField("quiere transporte", default=False)
    direccion_alojamiento = models.CharField("dirección alojamiento", max_length=255, blank=True)
    punto_recogida = models.ForeignKey(
        PuntoRecogida, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="punto de recogida",
    )
    enlace_maps_punto = models.URLField("enlace maps punto", blank=True)

    precio_actividad = models.DecimalField("importe actividad", max_digits=8, decimal_places=2, default=0)
    cobrado = models.DecimalField("cobrado", max_digits=8, decimal_places=2, default=0)
    porcentaje_lucia = models.DecimalField("porcentaje Lucía", max_digits=5, decimal_places=2, default=0)
    pago_otros = models.DecimalField("pago a otros", max_digits=8, decimal_places=2, default=0)
    total_experiencia = models.DecimalField("total experiencia", max_digits=8, decimal_places=2, default=0)

    # Campos extra del Word / Excel
    message_id = models.CharField("Message-ID del correo", max_length=255, blank=True, unique=True)
    fecha_procesado = models.DateTimeField("fecha procesado por la app", null=True, blank=True)
    nacionalidad = models.CharField("nacionalidad", max_length=100, blank=True)
    recogida_en_coche = models.BooleanField("recogida en coche", default=False)
    importe_recogida = models.DecimalField("importe recogida", max_digits=8, decimal_places=2, default=0)
    monitor_recogida = models.CharField("monitor recogida", max_length=100, blank=True)
    monitor_experiencia = models.CharField("monitor experiencia", max_length=100, blank=True)

    estado = models.ForeignKey(
        EstadoReserva, on_delete=models.PROTECT, verbose_name="estado",
        related_name="reservas",
    )
    color_evento = models.CharField("color evento", max_length=20, default="amarillo")

    google_calendar_event_id = models.CharField("ID evento Google Calendar", max_length=100, blank=True)

    fecha_creacion = models.DateTimeField("fecha creación", auto_now_add=True)
    fecha_actualizacion = models.DateTimeField("fecha actualización", auto_now=True)

    class Meta:
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"Actividad turismo ({self.numero_personas}pax) - {self.codigo_reserva or self.pk}"

    @property
    def titulo_evento(self):
        return f"Actividad turismo ({self.numero_personas}pax)"


class Conversacion(models.Model):
    """Agrupación de mensajes de una reserva."""

    reserva = models.OneToOneField(
        Reserva, on_delete=models.CASCADE, related_name="conversacion",
        verbose_name="reserva",
    )
    asunto = models.CharField("asunto", max_length=200, blank=True)
    fecha_ultimo_correo = models.DateTimeField("último correo", null=True, blank=True)

    class Meta:
        verbose_name = "conversación"
        verbose_name_plural = "conversaciones"

    def __str__(self):
        return f"Conversación - {self.reserva}"


class Mensaje(models.Model):
    """Mensaje enviado o recibido en una conversación."""

    DIRECCION_ENTRADA = "entrada"
    DIRECCION_SALIDA = "salida"

    DIRECCIONES = [
        (DIRECCION_ENTRADA, "Entrada"),
        (DIRECCION_SALIDA, "Salida"),
    ]

    conversacion = models.ForeignKey(
        Conversacion, on_delete=models.CASCADE, related_name="mensajes",
        verbose_name="conversación",
    )
    direccion = models.CharField("dirección", max_length=10, choices=DIRECCIONES)
    texto = models.TextField("texto")
    fecha = models.DateTimeField("fecha", auto_now_add=True)
    plataforma_mensaje = models.CharField(
        "plataforma del mensaje", max_length=30, blank=True
    )  # GYG chat, Viator chat, email, web

    class Meta:
        verbose_name = "mensaje"
        verbose_name_plural = "mensajes"
        ordering = ["fecha"]

    def __str__(self):
        return f"{self.get_direccion_display()} - {self.fecha}"


class Consulta(models.Model):
    """Consulta de un cliente por web o correo directo (sin reserva cerrada aún)."""

    plataforma = models.ForeignKey(
        Plataforma, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="plataforma",
    )
    nombre = models.CharField("nombre", max_length=100, blank=True)
    telefono = models.CharField("teléfono", max_length=30, blank=True)
    email = models.EmailField("correo", blank=True)
    texto = models.TextField("texto de la consulta")
    respondida = models.BooleanField("respondida", default=False)
    reserva = models.ForeignKey(
        Reserva, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="reserva creada",
        related_name="consultas",
    )
    fecha_creacion = models.DateTimeField("fecha", auto_now_add=True)

    class Meta:
        verbose_name = "consulta"
        verbose_name_plural = "consultas"
        ordering = ["-fecha_creacion"]

    def __str__(self):
        return f"Consulta de {self.nombre or 'cliente'} ({self.plataforma})"
