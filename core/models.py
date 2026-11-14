"""
Modelos compartidos (core) de la app El Acebuche.

Incluye:
- Perfil: rol de usuario (administra / consulta calendario).
- LogApp: registro de auditoría de acciones de la app (quién, qué, cuándo).
- Configuracion: configuración global (singleton) editable por Lucía desde el panel.
"""

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models


class Perfil(models.Model):
    """Perfil de usuario del centro ecuestre."""

    ROL_ADMIN = "administra"
    ROL_CONSULTA = "consulta"

    ROLES = [
        (ROL_ADMIN, "Administra (puede aprobar/enviar mensajes)"),
        (ROL_CONSULTA, "Consulta (solo ve calendario y pendientes)"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="perfil")
    rol = models.CharField("rol", max_length=20, choices=ROLES, default=ROL_CONSULTA)
    telefono = models.CharField("teléfono", max_length=30, blank=True)

    class Meta:
        verbose_name = "perfil"
        verbose_name_plural = "perfiles"

    def __str__(self):
        return f"{self.user.username} ({self.get_rol_display()})"

    @property
    def es_administra(self):
        return self.rol == self.ROL_ADMIN or self.user.is_superuser


class LogApp(models.Model):
    """Registro de auditoría de acciones realizadas en la app."""

    ACCION_CREAR = "crear"
    ACCION_EDITAR = "editar"
    ACCION_BORRAR = "borrar"
    ACCION_CAMBIO_ESTADO = "cambio_estado"
    ACCION_MENSAJE = "mensaje"
    ACCION_LOGIN = "login"
    ACCION_CORREO = "correo"

    ACCIONES = [
        (ACCION_CREAR, "Crear"),
        (ACCION_EDITAR, "Editar"),
        (ACCION_BORRAR, "Borrar"),
        (ACCION_CAMBIO_ESTADO, "Cambio de estado"),
        (ACCION_MENSAJE, "Mensaje enviado"),
        (ACCION_LOGIN, "Inicio de sesión"),
        (ACCION_CORREO, "Correo procesado"),
    ]

    fecha = models.DateTimeField("fecha y hora", auto_now_add=True)
    usuario = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="usuario",
    )
    accion = models.CharField("acción", max_length=30, choices=ACCIONES)
    modelo = models.CharField("modelo", max_length=50, blank=True)
    id_objeto = models.PositiveIntegerField("ID del objeto", null=True, blank=True)
    detalle = models.TextField("detalle", blank=True)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    user_agent = models.CharField("dispositivo / user agent", max_length=255, blank=True)

    class Meta:
        verbose_name = "registro de auditoría"
        verbose_name_plural = "registros de auditoría"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.fecha} - {self.get_accion_display()} - {self.usuario}"


def registrar_log(usuario, accion, modelo="", id_objeto=None, detalle="", request=None):
    """Función de utilidad para registrar una acción en la auditoría."""
    ip = None
    user_agent = ""
    if request is not None:
        ip = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")
    return LogApp.objects.create(
        usuario=usuario,
        accion=accion,
        modelo=modelo,
        id_objeto=id_objeto,
        detalle=detalle,
        ip=ip,
        user_agent=user_agent,
    )


from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
    """Crea automáticamente un Perfil al crear un User (rol admin si es superuser)."""
    if created:
        rol = Perfil.ROL_ADMIN if instance.is_superuser else Perfil.ROL_CONSULTA
        Perfil.objects.get_or_create(user=instance, defaults={"rol": rol})
class Configuracion(models.Model):
    """
    Configuración global de la app (singleton).

    Permite que Lucía introduzca sus credenciales privadas (correo, Google,
    Maps, IA) desde el panel de administración, sin tener que editar el
    archivo .env ni compartirlas con el desarrollador.
    """

    # --- Correo (Hostalia / SMTP) ---
    email_host = models.CharField("host SMTP", max_length=100, blank=True, default="imap.servidor-correo.net")
    email_port = models.PositiveIntegerField("puerto SMTP", default=587)
    email_use_tls = models.BooleanField("usar TLS", default=True)
    email_host_user = models.CharField("usuario correo", max_length=100, blank=True, default="info@elacebuche.es")
    email_host_password = models.CharField("contraseña correo", max_length=200, blank=True)
    default_from_email = models.CharField("correo remitente", max_length=100, blank=True, default="info@elacebuche.es")

    # --- IMAP ---
    imap_host = models.CharField("host IMAP", max_length=100, blank=True, default="imap.servidor-correo.net")
    imap_port = models.PositiveIntegerField("puerto IMAP", default=993)
    imap_user = models.CharField("usuario IMAP", max_length=100, blank=True, default="info@elacebuche.es")
    imap_password = models.CharField("contraseña IMAP", max_length=200, blank=True)
    imap_carpeta_entrada = models.CharField("carpeta entrada", max_length=50, blank=True, default="INBOX")
    imap_carpeta_procesado = models.CharField("carpeta procesado", max_length=50, blank=True, default="Procesado")

    # --- Google Calendar ---
    google_calendar_id = models.CharField("ID calendario", max_length=100, blank=True, default="luciagilran2014@gmail.com")
    google_client_id = models.CharField("Google Client ID", max_length=200, blank=True)
    google_client_secret = models.CharField("Google Client Secret", max_length=200, blank=True)
    google_redirect_uri = models.CharField("Google Redirect URI", max_length=200, blank=True, default="http://localhost:8000/calendar/oauth2callback/")

    # --- Google Maps ---
    google_maps_api_key = models.CharField("Google Maps API Key", max_length=200, blank=True)

    # --- IA ---
    ia_proveedor = models.CharField("proveedor IA", max_length=20, blank=True, default="claude")
    ia_api_key = models.CharField("IA API Key", max_length=200, blank=True)

    # --- Otros ---
    usar_credenciales_panel = models.BooleanField(
        "usar credenciales del panel (modo Lucía)", default=False,
        help_text="Desactivado: usa las credenciales del archivo .env (desarrollador). "
                  "Activado: usa las credenciales introducidas aquí (Lucía).",
    )
    modo_demo = models.BooleanField("modo demo (simular IA/Maps)", default=True)
    precio_transporte = models.DecimalField("precio transporte", max_digits=8, decimal_places=2, default=60)
    aviso_reserva_proxima_dias = models.PositiveIntegerField("días aviso urgente", default=1)

    # --- Plantillas de mensajes ---
    mensaje_preguntas = models.TextField("mensaje de preguntas (8.1)", blank=True)
    respuesta_sin_transporte = models.TextField("respuesta sin transporte (8.2)", blank=True)
    respuesta_con_transporte = models.TextField("respuesta con transporte (8.3)", blank=True)

    class Meta:
        verbose_name = "configuración de la app"
        verbose_name_plural = "configuración de la app"

    def __str__(self):
        return "Configuración global"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        if created:
            from django.conf import settings as dj_settings

            obj.email_host = getattr(dj_settings, "EMAIL_HOST", obj.email_host) or obj.email_host
            obj.email_port = getattr(dj_settings, "EMAIL_PORT", obj.email_port) or obj.email_port
            obj.email_use_tls = getattr(dj_settings, "EMAIL_USE_TLS", obj.email_use_tls)
            obj.email_host_user = getattr(dj_settings, "EMAIL_HOST_USER", obj.email_host_user) or obj.email_host_user
            obj.email_host_password = getattr(dj_settings, "EMAIL_HOST_PASSWORD", obj.email_host_password) or obj.email_host_password
            obj.default_from_email = getattr(dj_settings, "DEFAULT_FROM_EMAIL", obj.default_from_email) or obj.default_from_email

            obj.imap_host = getattr(dj_settings, "IMAP_HOST", obj.imap_host) or obj.imap_host
            obj.imap_port = getattr(dj_settings, "IMAP_PORT", obj.imap_port) or obj.imap_port
            obj.imap_user = getattr(dj_settings, "IMAP_USER", obj.imap_user) or obj.imap_user
            obj.imap_password = getattr(dj_settings, "IMAP_PASSWORD", obj.imap_password) or obj.imap_password
            obj.imap_carpeta_entrada = getattr(dj_settings, "IMAP_CARPETA_ENTRADA", obj.imap_carpeta_entrada) or obj.imap_carpeta_entrada
            obj.imap_carpeta_procesado = getattr(dj_settings, "IMAP_CARPETA_PROCESADO", obj.imap_carpeta_procesado) or obj.imap_carpeta_procesado

            obj.google_calendar_id = getattr(dj_settings, "GOOGLE_CALENDAR_ID", obj.google_calendar_id) or obj.google_calendar_id
            obj.google_client_id = getattr(dj_settings, "GOOGLE_CLIENT_ID", obj.google_client_id) or obj.google_client_id
            obj.google_client_secret = getattr(dj_settings, "GOOGLE_CLIENT_SECRET", obj.google_client_secret) or obj.google_client_secret
            obj.google_redirect_uri = getattr(dj_settings, "GOOGLE_REDIRECT_URI", obj.google_redirect_uri) or obj.google_redirect_uri

            obj.google_maps_api_key = getattr(dj_settings, "GOOGLE_MAPS_API_KEY", obj.google_maps_api_key) or obj.google_maps_api_key

            obj.ia_proveedor = getattr(dj_settings, "IA_PROVEEDOR", obj.ia_proveedor) or obj.ia_proveedor
            obj.ia_api_key = getattr(dj_settings, "IA_API_KEY", obj.ia_api_key) or obj.ia_api_key

            obj.modo_demo = getattr(dj_settings, "MODO_DEMO", obj.modo_demo)
            obj.precio_transporte = getattr(dj_settings, "PRECIO_TRANSPORTE", obj.precio_transporte) or obj.precio_transporte
            obj.aviso_reserva_proxima_dias = getattr(dj_settings, "AVISO_RESERVA_PROXIMA_DIAS", obj.aviso_reserva_proxima_dias) or obj.aviso_reserva_proxima_dias

            obj.mensaje_preguntas = getattr(dj_settings, "MENSAJE_PREGUNTAS", obj.mensaje_preguntas) or obj.mensaje_preguntas
            obj.respuesta_sin_transporte = getattr(dj_settings, "RESPUESTA_SIN_TRANSPORTE", obj.respuesta_sin_transporte) or obj.respuesta_sin_transporte
            obj.respuesta_con_transporte = getattr(dj_settings, "RESPUESTA_CON_TRANSPORTE", obj.respuesta_con_transporte) or obj.respuesta_con_transporte

            obj.save()
        return obj
