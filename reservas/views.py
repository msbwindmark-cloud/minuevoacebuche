# -*- coding: utf-8 -*-
"""
Vistas de la app de reservas del Centro Ecuestre El Acebuche.

Stack: Django + Bootswatch + SweetAlert2 + AJAX (fetch + CSRF) + toasts.

Incluye:
- Panel de pendientes con avisos urgentes y acciones concretas
- Detalle de reserva con IA, Google Maps, mensajes automáticos y cambio de estado
- Configuración de puntos de recogida
- Ejecución de procesamiento de correos desde web
"""

import json
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib import messages
from django.core.management import call_command
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET

from core.models import LogApp, registrar_log
from .models import Reserva, EstadoReserva, PuntoRecogida, Plataforma, Conversacion, Mensaje
from .services.ia_service import interpretar_respuesta_cliente, aplicar_interpretacion_a_reserva
from .services.maps_service import buscar_punto_recogida_mas_cercano
from .services.mensajes_service import (
    obtener_mensaje_preguntas,
    obtener_respuesta_sin_transportes,
    obtener_respuesta_con_transporte,
    generar_enlace_whatsapp,
    mensaje_aviso_coche_listo,
)


# ---------------------------------------------------------------------------
# Decorador: solo usuarios que administran
# ---------------------------------------------------------------------------
def administra_required(view_func):
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        perfil = getattr(request.user, "perfil", None)
        if not perfil or not perfil.es_administra:
            return HttpResponseForbidden("No tienes permiso para esta acción.")
        return view_func(request, *args, **kwargs)
    return _wrapped


# ---------------------------------------------------------------------------
# Login personalizado
# ---------------------------------------------------------------------------
class LoginView(auth_views.LoginView):
    template_name = "login.html"

    def form_invalid(self, request=None, *args, **kwargs):
        messages.error(self.request, "Usuario o contraseña incorrectos.")
        return super().form_invalid(*args, **kwargs)


# ---------------------------------------------------------------------------
# Panel de pendientes (pantalla principal)
# ---------------------------------------------------------------------------
@login_required
def pendientes(request):
    """Lista de reservas que necesitan atención (no completas), con avisos urgentes."""
    estados_pendientes = EstadoReserva.objects.exclude(
        nombre="completa"
    ).exclude(nombre="cancelada")
    reservas = (
        Reserva.objects.filter(estado__in=estados_pendientes)
        .select_related("plataforma", "estado", "punto_recogida")
        .order_by("fecha_actividad", "hora_actividad")
    )

    # Reservas completas recientes para contexto (últimas 10)
    recientes = (
        Reserva.objects.filter(estado__nombre="completa")
        .order_by("-fecha_actualizacion")[:10]
    )

    estados = EstadoReserva.objects.all().order_by("nombre")

    # --- Avisos urgentes (sección 5 y 13 del Word) ---
    hoy = date.today()
    manana = hoy + timedelta(days=1)
    dias_aviso = int(getattr(settings, "AVISO_RESERVA_PROXIMA_DIAS", "1"))
    fecha_limite = hoy + timedelta(days=dias_aviso)

    avisos_urgentes = []

    for r in reservas:
        # Reserva para hoy o mañana sin datos
        if r.fecha_actividad <= fecha_limite and r.estado.color == "amarillo":
            avisos_urgentes.append({
                "tipo": "sin_datos",
                "reserva": r,
                "mensaje": f"Reserva de {r.nombre_cliente} el {r.fecha_actividad.strftime('%d/%m')} a las {r.hora_actividad} aún falta datos del cliente.",
                "accion": "Completar ficha del cliente",
                "url": reverse("reserva_detalle", args=[r.pk]),
            })

        # Reserva con transporte sin punto de recogida decidido
        if r.quiere_transporte and not r.punto_recogida and r.estado.color in ("amarillo", "rojo"):
            avisos_urgentes.append({
                "tipo": "punto_sin_decidir",
                "reserva": r,
                "mensaje": f"{r.nombre_cliente} quiere transporte pero no hay punto de recogida decidido.",
                "accion": "Elegir punto de recogida",
                "url": reverse("reserva_detalle", args=[r.pk]),
            })

    # Ordenar avisos: más próximos primero
    avisos_urgentes.sort(key=lambda a: a["reserva"].fecha_actividad)

    return render(request, "pendientes.html", {
        "reservas": reservas,
        "recientes": recientes,
        "estados": estados,
        "avisos_urgentes": avisos_urgentes,
    })


# ---------------------------------------------------------------------------
# Detalle de una reserva
# ---------------------------------------------------------------------------
@login_required
def reserva_detalle(request, pk):
    reserva = get_object_or_404(
        Reserva.objects.select_related("plataforma", "estado", "punto_recogida"),
        pk=pk,
    )
    estados = EstadoReserva.objects.all().order_by("nombre")
    puntos = PuntoRecogida.objects.filter(activo=True).order_by("nombre")

    # Enlaces automáticos
    enlace_whatsapp = generar_enlace_whatsapp(reserva.telefono_cliente, "")
    enlace_aviso_listo = mensaje_aviso_coche_listo(reserva.nombre_cliente, reserva.telefono_cliente)

    # Datos para mensajes automáticos
    mensaje_preguntas = obtener_mensaje_preguntas()
    if reserva.quiere_transporte and reserva.punto_recogida:
        respuesta_transporte = obtener_respuesta_con_transporte(
            nombre=reserva.nombre_cliente,
            fecha=reserva.fecha_actividad.strftime("%d de %B de %Y"),
            hora_recogida=(reserva.hora_actividad.strftime("%H:%M") if reserva.hora_actividad else "9:30"),
            punto=reserva.punto_recogida.nombre,
            enlace_maps=reserva.punto_recogida.enlace_maps or "",
        )
    else:
        respuesta_transporte = ""

    if not reserva.quiere_transporte:
        respuesta_sin_transporte = obtener_respuesta_sin_transportes(
            nombre=reserva.nombre_cliente,
            fecha=reserva.fecha_actividad.strftime("%d de %B de %Y"),
            hora=(reserva.hora_actividad.strftime("%H:%M") if reserva.hora_actividad else "10:00"),
        )
    else:
        respuesta_sin_transporte = ""

    return render(request, "reserva_detalle.html", {
        "reserva": reserva,
        "estados": estados,
        "puntos": puntos,
        "enlace_whatsapp": enlace_whatsapp,
        "enlace_aviso_listo": enlace_aviso_listo,
        "mensaje_preguntas": mensaje_preguntas,
        "respuesta_sin_transporte": respuesta_sin_transporte,
        "respuesta_transporte": respuesta_transporte,
    })


# ---------------------------------------------------------------------------
# Cambiar estado de reserva (AJAX)
# ---------------------------------------------------------------------------
@require_POST
@login_required
def cambiar_estado(request, pk):
    reserva = get_object_or_404(Reserva, pk=pk)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    nuevo_estado_id = data.get("estado_id")
    if not nuevo_estado_id:
        return JsonResponse({"ok": False, "error": "Falta estado_id"}, status=400)

    nuevo_estado = get_object_or_404(EstadoReserva, pk=nuevo_estado_id)
    estado_anterior = reserva.estado.nombre
    reserva.estado = nuevo_estado
    reserva.color_evento = nuevo_estado.color
    reserva.fecha_actualizacion = timezone.now()
    reserva.save()

    registrar_log(
        usuario=request.user,
        accion="cambio_estado",
        modelo="Reserva",
        id_objeto=reserva.pk,
        detalle=f"Estado de '{estado_anterior}' a '{nuevo_estado.nombre}'.",
        request=request,
    )

    return JsonResponse({
        "ok": True,
        "nuevo_estado": nuevo_estado.nombre,
        "color": nuevo_estado.color,
    })


# ---------------------------------------------------------------------------
# Interpretar respuesta de cliente con IA
# ---------------------------------------------------------------------------
@require_POST
@login_required
def interpretar_respuesta(request, pk):
    """
    Recibe el texto de la respuesta de un cliente, lo envía a la IA
    y actualiza la reserva con los datos extraídos.
    """
    reserva = get_object_or_404(Reserva, pk=pk)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    texto_cliente = data.get("texto", "").strip()
    if not texto_cliente:
        return JsonResponse({"ok": False, "error": "Falta el texto de la respuesta"}, status=400)

    # Guardar mensaje entrante en la conversación
    conversacion, _ = Conversacion.objects.get_or_create(
        reserva=reserva,
        defaults={"asunto": f"Respuesta cliente - {reserva.codigo_reserva or reserva.pk}"},
    )
    Mensaje.objects.create(
        conversacion=conversacion,
        direccion=Mensaje.DIRECCION_ENTRADA,
        texto=texto_cliente,
        plataforma_mensaje="email",
    )

    # Interpretar con IA
    interpretacion = interpretar_respuesta_cliente(
        texto_cliente, idioma_origen=reserva.idioma or "en"
    )

    # Aplicar a la reserva
    cambios = aplicar_interpretacion_a_reserva(reserva, interpretacion)
    reserva.fecha_actualizacion = timezone.now()
    reserva.save()

    # Si ya tiene todos los datos clave, cambiar estado a pendiente_decision o completa
    datos_completos = bool(
        reserva.nombre_cliente and reserva.telefono_cliente and
        (not reserva.quiere_transporte or reserva.direccion_alojamiento)
    )
    if datos_completos and reserva.estado.color == "amarillo":
        estado_decision = EstadoReserva.objects.filter(nombre="pendiente_decision").first()
        if estado_decision:
            reserva.estado = estado_decision
            reserva.color_evento = estado_decision.color
            reserva.save()
            cambios.append(f"estado->{estado_decision.nombre}")

    registrar_log(
        usuario=request.user,
        accion="editar",
        modelo="Reserva",
        id_objeto=reserva.pk,
        detalle=f"IA interpretó respuesta del cliente. Cambios: {', '.join(cambios) if cambios else 'ninguno'}. IA confianza: {interpretacion.get('confianza', 0)}",
        request=request,
    )

    return JsonResponse({
        "ok": True,
        "interpretacion": interpretacion,
        "cambios_aplicados": cambios,
        "requiere_revision_manual": interpretacion.get("requiere_revision_manual", True),
    })


# ---------------------------------------------------------------------------
# Buscar punto de recogida con Google Maps
# ---------------------------------------------------------------------------
@require_POST
@login_required
def buscar_punto_recogida(request, pk):
    """
    Dado un alojamiento, busca el punto de recogida más cercano usando Google Maps.
    Si cumple la regla de ≤10 min, lo asigna a la reserva.
    """
    reserva = get_object_or_404(Reserva, pk=pk)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "JSON inválido"}, status=400)

    direccion = data.get("direccion", "").strip() or reserva.direccion_alojamiento
    if not direccion:
        return JsonResponse({"ok": False, "error": "Falta dirección de alojamiento"}, status=400)

    # Actualizar dirección si se envió una nueva
    if direccion != reserva.direccion_alojamiento:
        reserva.direccion_alojamiento = direccion
        reserva.save(update_fields=["direccion_alojamiento"])

    puntos = list(PuntoRecogida.objects.filter(activo=True))
    resultado = buscar_punto_recogida_mas_cercano(direccion, puntos, max_minutos=10)

    if resultado["punto"] and resultado["cumple_regla"]:
        reserva.punto_recogida = resultado["punto"]
        reserva.enlace_maps_punto = resultado["punto"].enlace_maps or ""
        reserva.fecha_actualizacion = timezone.now()
        reserva.save()

        registrar_log(
            usuario=request.user,
            accion="editar",
            modelo="Reserva",
            id_objeto=reserva.pk,
            detalle=f"Punto de recogida asignado automáticamente: {resultado['punto'].nombre} ({resultado['minutos']} min andando).",
            request=request,
        )

        return JsonResponse({
            "ok": True,
            "punto_asignado": True,
            "punto": resultado["punto"].nombre,
            "minutos": resultado["minutos"],
            "distancia_km": resultado["distancia_km"],
            "enlace_maps": resultado["punto"].enlace_maps or "",
            "mensaje": f"Punto asignado: {resultado['punto'].nombre} ({resultado['minutos']} min andando).",
        })
    else:
        # No hay punto cerca: pasar a pendiente_decisión para que Lucía elija
        estado_decision = EstadoReserva.objects.filter(nombre="pendiente_decision").first()
        if estado_decision and reserva.estado.color != "rojo":
            reserva.estado = estado_decision
            reserva.color_evento = estado_decision.color
            reserva.save()

        return JsonResponse({
            "ok": True,
            "punto_asignado": False,
            "minutos": resultado.get("minutos"),
            "distancia_km": resultado.get("distancia_km"),
            "mensaje": "Ningún punto está a ≤10 min andando. Reserva marcada para decisión de Lucía.",
            "requiere_decision_lucia": True,
        })


# ---------------------------------------------------------------------------
# Calendario (vista de referencia, enlaza a Google Calendar)
# ---------------------------------------------------------------------------
@login_required
def calendario(request):
    return render(request, "calendario.html", {})


# ---------------------------------------------------------------------------
# Configuración: puntos de recogida y plantillas
# ---------------------------------------------------------------------------
@login_required
@administra_required
def configuracion(request):
    puntos = PuntoRecogida.objects.all().order_by("nombre")
    estados = EstadoReserva.objects.all().order_by("nombre")
    plataformas = Plataforma.objects.all().order_by("nombre")

    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "crear_punto":
            nombre = request.POST.get("nombre", "").strip()
            direccion = request.POST.get("direccion", "").strip()
            enlace = request.POST.get("enlace_maps", "").strip()
            if nombre:
                PuntoRecogida.objects.create(
                    nombre=nombre, direccion=direccion, enlace_maps=enlace
                )
                messages.success(request, f"Punto '{nombre}' creado.")
                registrar_log(
                    usuario=request.user, accion="crear", modelo="PuntoRecogida",
                    detalle=f"Punto de recogida '{nombre}'.", request=request,
                )
            else:
                messages.error(request, "El nombre es obligatorio.")
        elif accion == "crear_estado":
            nombre = request.POST.get("nombre_estado", "").strip()
            color = request.POST.get("color_estado", "amarillo")
            if nombre:
                EstadoReserva.objects.get_or_create(
                    nombre=nombre, defaults={"color": color}
                )
                messages.success(request, f"Estado '{nombre}' creado.")
            else:
                messages.error(request, "El nombre del estado es obligatorio.")
        elif accion == "crear_plataforma":
            nombre = request.POST.get("nombre_plataforma", "").strip()
            if nombre:
                Plataforma.objects.get_or_create(nombre=nombre)
                messages.success(request, f"Plataforma '{nombre}' creada.")
            else:
                messages.error(request, "El nombre de la plataforma es obligatorio.")
        return redirect("configuracion")

    return render(request, "configuracion.html", {
        "puntos": puntos,
        "estados": estados,
        "plataformas": plataformas,
    })


# ---------------------------------------------------------------------------
# API: lista de puntos de recogida (para AJAX en el detalle)
# ---------------------------------------------------------------------------
@require_GET
@login_required
def api_puntos_recogida(request):
    puntos = PuntoRecogida.objects.filter(activo=True).order_by("nombre").values(
        "id", "nombre", "direccion", "enlace_maps"
    )
    return JsonResponse({"ok": True, "puntos": list(puntos)})


# ---------------------------------------------------------------------------
# Ejecutar procesamiento de correos desde el navegador (solo superusuario)
# ---------------------------------------------------------------------------
@login_required
def procesar_correos_vista(request):
    if not request.user.is_superuser:
        return JsonResponse({"error": "Solo el superusuario puede ejecutar esto."}, status=403)

    no_calendar = request.GET.get("no_calendar", "0") == "1"
    no_mover = request.GET.get("no_mover", "0") == "1"

    args = []
    if no_calendar:
        args.append("--no-calendar")
    if no_mover:
        args.append("--no-mover")

    try:
        call_command("procesar_correos", *args)
        return JsonResponse({"ok": True, "mensaje": "Correos procesados correctamente."})
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)
