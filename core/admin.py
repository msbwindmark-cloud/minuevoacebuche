from django.contrib import admin
from .models import Perfil, LogApp


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("user", "rol", "telefono")
    list_filter = ("rol",)
    search_fields = ("user__username", "user__first_name", "user__last_name")


@admin.register(LogApp)
class LogAppAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario", "accion", "modelo", "id_objeto")
    list_filter = ("accion", "fecha")
    search_fields = ("detalle", "usuario__username")
    readonly_fields = ("fecha", "usuario", "accion", "modelo", "id_objeto", "detalle", "ip", "user_agent")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
