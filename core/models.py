"""
Modelos compartidos (core) de la app El Acebuche.

Incluye:
- Perfil: rol de usuario (administra / consulta calendario).
- LogApp: registro de auditoría de acciones de la app (quién, qué, cuándo).
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
