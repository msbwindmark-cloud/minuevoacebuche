from django import forms
from django.contrib import admin
from django.contrib.auth.models import User

from .models import Configuracion, LogApp, Perfil


class ConfiguracionAdminForm(forms.ModelForm):
    """Formulario del admin con campos sensibles como password."""

    class Meta:
        model = Configuracion
        fields = "__all__"
        widgets = {
            "email_host_password": forms.PasswordInput(render_value=True),
            "imap_password": forms.PasswordInput(render_value=True),
            "google_client_secret": forms.PasswordInput(render_value=True),
            "google_maps_api_key": forms.PasswordInput(render_value=True),
            "ia_api_key": forms.PasswordInput(render_value=True),
        }


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("user", "rol", "telefono")
    list_filter = ("rol",)
    search_fields = ("user__username",)


@admin.register(LogApp)
class LogAppAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario", "accion", "modelo", "id_objeto")
    list_filter = ("accion", "modelo")
    search_fields = ("detalle", "usuario__username")
    readonly_fields = ("fecha", "usuario", "accion", "modelo", "id_objeto", "detalle", "ip", "user_agent")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Configuracion)
class ConfiguracionAdmin(admin.ModelAdmin):
    form = ConfiguracionAdminForm
    fieldsets = (
        ("Correo (Hostalia / SMTP)", {
            "fields": ("email_host", "email_port", "email_use_tls", "email_host_user",
                       "email_host_password", "default_from_email"),
        }),
        ("IMAP (lectura de correos)", {
            "fields": ("imap_host", "imap_port", "imap_user", "imap_password",
                       "imap_carpeta_entrada", "imap_carpeta_procesado"),
        }),
        ("Google Calendar", {
            "fields": ("google_calendar_id", "google_client_id", "google_client_secret",
                       "google_redirect_uri"),
        }),
        ("Google Maps", {
            "fields": ("google_maps_api_key",),
        }),
        ("Inteligencia artificial", {
            "fields": ("ia_proveedor", "ia_api_key"),
        }),
        ("Otros", {
            "fields": ("modo_demo", "precio_transporte", "aviso_reserva_proxima_dias"),
        }),
        ("Plantillas de mensajes", {
            "fields": ("mensaje_preguntas", "respuesta_sin_transporte", "respuesta_con_transporte"),
            "classes": ("collapse",),
        }),
    )

    def has_add_permission(self, request):
        # Singleton: no se pueden crear más instancias
        return not Configuracion.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
