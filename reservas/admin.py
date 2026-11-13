from django.contrib import admin
from .models import (
    Plataforma, EstadoReserva, PuntoRecogida, Reserva,
    Conversacion, Mensaje, Consulta,
)


@admin.register(Plataforma)
class PlataformaAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre",)


@admin.register(EstadoReserva)
class EstadoReservaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "color")
    list_filter = ("color",)


@admin.register(PuntoRecogida)
class PuntoRecogidaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre", "direccion")


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = (
        "codigo_reserva", "plataforma", "fecha_actividad", "hora_actividad",
        "nombre_cliente", "numero_personas", "estado", "color_evento",
    )
    list_filter = ("estado", "plataforma", "quiere_transporte", "fecha_actividad")
    search_fields = ("codigo_reserva", "nombre_cliente", "telefono_cliente")
    date_hierarchy = "fecha_actividad"


@admin.register(Conversacion)
class ConversacionAdmin(admin.ModelAdmin):
    list_display = ("reserva", "asunto", "fecha_ultimo_correo")
    search_fields = ("asunto", "reserva__nombre_cliente")


@admin.register(Mensaje)
class MensajeAdmin(admin.ModelAdmin):
    list_display = ("conversacion", "direccion", "fecha", "plataforma_mensaje")
    list_filter = ("direccion", "plataforma_mensaje")
@admin.register(Consulta)
class ConsultaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "plataforma", "respondida", "fecha_creacion")
    list_filter = ("respondida", "plataforma")
    search_fields = ("nombre", "texto", "email")
