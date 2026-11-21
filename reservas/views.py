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

import io
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
from core.forms import ConfiguracionForm
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
        perfil = None
        try:
            perfil = request.user.perfil
        except Exception:
            perfil = None
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
    from core.models import Configuracion

    config = Configuracion.get()
    if config.usar_credenciales_panel:
        dias_aviso = int(config.aviso_reserva_proxima_dias or 1)
    else:
        dias_aviso = int(getattr(settings, "AVISO_RESERVA_PROXIMA_DIAS", 1))
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

    from reservas.models import Consulta

    consultas_pendientes = Consulta.objects.filter(respondida=False).select_related("plataforma")

    return render(request, "pendientes.html", {
        "reservas": reservas,
        "recientes": recientes,
        "estados": estados,
        "avisos_urgentes": avisos_urgentes,
        "consultas_pendientes": consultas_pendientes,
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
        "modo_demo": interpretacion.get("modo_demo", False),
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
            "modo_demo": resultado.get("modo_demo", False),
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
            "modo_demo": resultado.get("modo_demo", False),
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
# Configuración avanzada: credenciales privadas de Lucía
# ---------------------------------------------------------------------------
@administra_required
@require_POST
def marcar_consulta_respondida(request, pk):
    from reservas.models import Consulta

    consulta = get_object_or_404(Consulta, pk=pk)
    consulta.respondida = True
    consulta.save(update_fields=["respondida"])
    return redirect("pendientes")


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
    perfil = getattr(request.user, "perfil", None)
    if not (request.user.is_superuser or (perfil and perfil.es_administra)):
        return JsonResponse({"error": "Solo el superusuario o un administrador puede ejecutar esto."}, status=403)

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


# ---------------------------------------------------------------------------
# Exportar reservas a Excel desde el panel (descarga directa)
# ---------------------------------------------------------------------------
@administra_required
def exportar_excel_vista(request):
    """
    Genera y descarga un Excel con las reservas del mes indicado.
    Parámetros GET: mes (1-12), anio (ej. 2026).
    """
    from django.http import HttpResponse
    try:
        mes = int(request.GET.get("mes", ""))
        anio = int(request.GET.get("anio", ""))
    except (TypeError, ValueError):
        from django.utils import timezone

        hoy = timezone.now()
        mes = hoy.month
        anio = hoy.year

    if not (1 <= mes <= 12):
        return JsonResponse({"ok": False, "error": "Mes inválido"}, status=400)

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        return HttpResponse(
            "<h3>Exportar a Excel no disponible</h3>"
            "<p>El paquete <code>openpyxl</code> no está instalado en el servidor. "
            "Ejecuta <code>pip install openpyxl</code> en la consola de PythonAnywhere.</p>"
            '<p><a href="/configuracion/">Volver a Configuración</a></p>',
            content_type="text/html; charset=utf-8",
            status=503,
        )

    from django.db.models import Sum, Count

    from reservas.models import Reserva

    reservas = (
        Reserva.objects.filter(
            fecha_actividad__year=anio,
            fecha_actividad__month=mes,
        )
        .select_related("plataforma", "estado", "punto_recogida")
        .order_by("fecha_actividad", "hora_actividad")
    )

    wb = Workbook()

    # Hoja 1: Reservas del mes
    ws1 = wb.active
    ws1.title = f"Reservas {mes:02d}-{anio}"

    cabeceras = [
        "Fecha Actividad", "Plataforma", "Nº de personas", "Nombre cliente",
        "Importe de actividad", "Cobrado", "Porcentaje Lucia",
        "Recogida en coche", "Precio recogida", "Monitor recogida",
        "Monitor experiencia", "Total experiencia", "Pago a otros",
        "Cod. Reserva", "Estado", "Teléfono", "Correo", "Nacionalidad",
        "Edades", "Quiere transporte", "Dirección alojamiento",
    ]

    font_negrita = Font(bold=True, color="FFFFFF")
    relleno_azul = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    alineacion_centro = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col_idx, cabecera in enumerate(cabeceras, start=1):
        celda = ws1.cell(row=1, column=col_idx, value=cabecera)
        celda.font = font_negrita
        celda.fill = relleno_azul
        celda.alignment = alineacion_centro

    fila = 2
    for r in reservas:
        ws1.cell(row=fila, column=1, value=r.fecha_actividad.strftime("%d/%m/%Y"))
        ws1.cell(row=fila, column=2, value=r.plataforma.nombre if r.plataforma else "")
        ws1.cell(row=fila, column=3, value=r.numero_personas)
        ws1.cell(row=fila, column=4, value=r.nombre_cliente)
        ws1.cell(row=fila, column=5, value=float(r.precio_actividad or 0))
        ws1.cell(row=fila, column=6, value=float(r.cobrado or 0))
        ws1.cell(row=fila, column=7, value=float(r.porcentaje_lucia or 0))
        ws1.cell(row=fila, column=8, value="SI" if r.recogida_en_coche else "NO")
        ws1.cell(row=fila, column=9, value=float(r.importe_recogida or 0))
        ws1.cell(row=fila, column=10, value=r.monitor_recogida or "")
        ws1.cell(row=fila, column=11, value=r.monitor_experiencia or "")
        ws1.cell(row=fila, column=12, value=float(r.total_experiencia or 0))
        ws1.cell(row=fila, column=13, value=float(r.pago_otros or 0))
        ws1.cell(row=fila, column=14, value=r.codigo_reserva or "")
        ws1.cell(row=fila, column=15, value=r.estado.nombre if r.estado else "")
        ws1.cell(row=fila, column=16, value=r.telefono_cliente or "")
        ws1.cell(row=fila, column=17, value=r.email_cliente or "")
        ws1.cell(row=fila, column=18, value=r.nacionalidad or "")
        ws1.cell(row=fila, column=19, value="; ".join(str(e) for e in (r.edades or [])))
        ws1.cell(row=fila, column=20, value="SI" if r.quiere_transporte else "NO")
        ws1.cell(row=fila, column=21, value=r.direccion_alojamiento or "")
        fila += 1

    anchos = [14, 15, 10, 22, 14, 10, 12, 12, 12, 14, 14, 13, 11, 15, 12, 15, 20, 15, 15, 12, 25]
    for i, ancho in enumerate(anchos, start=1):
        ws1.column_dimensions[get_column_letter(i)].width = ancho

    # Hoja 2: Por plataforma
    ws2 = wb.create_sheet(title="Por plataforma")
    ws2.append(["Plataforma", "Nº reservas", "Total personas", "Total cobrado (€)", "Total experiencia (€)"])
    for celda in ws2[1]:
        celda.font = font_negrita
        celda.fill = relleno_azul
        celda.alignment = alineacion_centro

    resumen = (
        reservas.values("plataforma__nombre")
        .annotate(
            num_reservas=Count("id"),
            total_personas=Sum("numero_personas"),
            total_cobrado=Sum("cobrado"),
            total_experiencia=Sum("total_experiencia"),
        )
        .order_by("plataforma__nombre")
    )
    for item in resumen:
        ws2.append([
            item["plataforma__nombre"] or "Sin plataforma",
            item["num_reservas"],
            item["total_personas"] or 0,
            round(float(item["total_cobrado"] or 0), 2),
            round(float(item["total_experiencia"] or 0), 2),
        ])
    for i, ancho in enumerate([20, 12, 14, 16, 18], start=1):
        ws2.column_dimensions[get_column_letter(i)].width = ancho

    # Hoja 3: Resumen mensual
    ws3 = wb.create_sheet(title="Resumen mes")
    ws3.append(["Concepto", "Valor"])
    for celda in ws3[1]:
        celda.font = font_negrita
        celda.fill = relleno_azul

    total_cobrado = reservas.aggregate(total=Sum("cobrado"))["total"] or 0
    total_experiencia = reservas.aggregate(total=Sum("total_experiencia"))["total"] or 0
    total_personas = reservas.aggregate(total=Sum("numero_personas"))["total"] or 0
    total_transporte = reservas.filter(quiere_transporte=True).aggregate(total=Sum("importe_recogida"))["total"] or 0
    total_otros = reservas.aggregate(total=Sum("pago_otros"))["total"] or 0

    for concepto, valor in [
        ("Total mes cobrado (EUR)", round(float(total_cobrado), 2)),
        ("Total experiencia (EUR)", round(float(total_experiencia), 2)),
        ("TOTAL PERSONAS", int(total_personas or 0)),
        ("Total transporte (EUR)", round(float(total_transporte), 2)),
        ("Total Otros (EUR)", round(float(total_otros), 2)),
        ("Nº de reservas", reservas.count()),
    ]:
        ws3.append([concepto, valor])
    for i, ancho in enumerate([30, 20], start=1):
        ws3.column_dimensions[get_column_letter(i)].width = ancho

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    nombre_archivo = f"reservas_{mes:02d}_{anio}.xlsx"
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'
    return response


# ---------------------------------------------------------------------------
# Configuración avanzada: credenciales privadas de Lucía
# ---------------------------------------------------------------------------
@administra_required
def configuracion_avanzada(request):
    """
    Permite a Lucía introducir sus credenciales privadas (correo, Google,
    Maps, IA) desde el panel, sin editar el .env ni compartirlas.
    """
    from core.models import Configuracion
    from core.forms import ConfiguracionForm

    config = Configuracion.get()

    if request.method == "POST":
        # Solo el superusuario puede cambiar el interruptor "Modo Lucía"
        if not request.user.is_superuser and "usar_credenciales_panel" in request.POST:
            post_data = request.POST.copy()
            post_data.pop("usar_credenciales_panel", None)
            form = ConfiguracionForm(post_data, instance=config)
        else:
            form = ConfiguracionForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Credenciales guardadas. La app las usará a partir de ahora.",
            )
            registrar_log(
                usuario=request.user,
                accion=LogApp.ACCION_EDITAR,
                modelo="Configuracion",
                id_objeto=1,
                detalle="Configuración avanzada actualizada desde el panel.",
                request=request,
            )
            return redirect("configuracion_avanzada")
    else:
        form = ConfiguracionForm(instance=config)

    return render(request, "configuracion_avanzada.html", {
        "form": form,
        "config": config,
    })


# ---------------------------------------------------------------------------
# Descargar guía para Lucía en PDF
# ---------------------------------------------------------------------------
@login_required
def descargar_guia_pdf(request):
    """Genera y descarga un PDF con la guía para Lucía y las instrucciones."""
    from django.http import HttpResponse
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
        from reportlab.lib import colors
    except ImportError:
        return HttpResponse(
            "<h3>Descargar guía PDF no disponible</h3>"
            "<p>El paquete <code>reportlab</code> no está instalado en el servidor. "
            "Ejecuta <code>pip install reportlab</code> en la consola de PythonAnywhere.</p>"
            '<p><a href="/configuracion/">Volver a Configuración</a></p>',
            content_type="text/html; charset=utf-8",
            status=503,
        )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                           topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    titulo = ParagraphStyle("titulo", parent=styles["Title"], fontSize=18, spaceAfter=12,
                            textColor=colors.HexColor("#1F4E79"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=13, spaceBefore=12,
                        spaceAfter=6, textColor=colors.HexColor("#1F4E79"))
    normal = ParagraphStyle("normal", parent=styles["Normal"], fontSize=10.5, spaceAfter=6,
                            leading=14)
    bullet = ParagraphStyle("bullet", parent=normal, leftIndent=18, bulletIndent=8)

    story = []
    story.append(Paragraph("Centro Ecuestre El Acebuche", titulo))
    story.append(Paragraph("Guía para Lucía — cómo usar la app de reservas", h2))
    story.append(Paragraph(
        "Esta guía explica paso a paso cómo introducir tus claves privadas en la app "
        "y cómo usar el resto de funciones. No hace falta saber de informática.", normal))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("Paso 1 — Correo de Hostalia (info@elacebuche.es)", h2))
    story.append(Paragraph("Rellena estos campos en Configuración → Credenciales privadas:", normal))
    for t in [
        "Host SMTP: déjalo como está (imap.servidor-correo.net).",
        "Puerto: 587.",
        "Usar TLS: marcado.",
        "Usuario: info@elacebuche.es.",
        "Contraseña del correo: la contraseña de tu correo de Hostalia.",
        "Correo remitente: info@elacebuche.es.",
        "Host IMAP, puerto 993, carpeta entrada INBOX, carpeta procesado Procesado: déjalos como están.",
    ]:
        story.append(Paragraph("• " + t, bullet))

    story.append(Paragraph("Paso 2 — Google Calendar (para crear eventos automáticamente)", h2))
    story.append(Paragraph("Necesitas crear unas credenciales en Google. Tu compañero puede ayudarte:", normal))
    for t in [
        "Entra a console.cloud.google.com con tu cuenta luciagilran2014@gmail.com.",
        "Crea un proyecto (ponle de nombre 'El Acebuche').",
        "Busca 'Google Calendar API' y actívala.",
        "Ve a Credenciales → Crear credenciales → ID de cliente OAuth 2.0 (tipo 'Aplicación web').",
        "En 'URIs de redirección autorizados' pon: https://tu-dominio.pythonanywhere.com/calendar/oauth2callback/",
        "Copia el Client ID y el Client Secret y pégalos en el panel de la app.",
        "Guarda el formulario.",
        "Pulsa el enlace 'Autorizar Google Calendar' e inicia sesión con luciagilran2014@gmail.com.",
    ]:
        story.append(Paragraph("• " + t, bullet))
    story.append(Paragraph(
        "Listo. Se genera un archivo automático en el servidor (google_token.json). "
        "No tienes que subir nada ni tocar ningún archivo .json.", normal))

    story.append(Paragraph("Paso 3 — Google Maps (para calcular puntos de recogida)", h2))
    for t in [
        "En la misma consola de Google Cloud, ve a Credenciales → Crear credencial → Clave de API.",
        "Copia la clave y pégala en el campo 'Google Maps API Key'.",
        "(Opcional) Restringe la clave por la IP del servidor para más seguridad.",
    ]:
        story.append(Paragraph("• " + t, bullet))
    story.append(Paragraph("No necesita archivos ni autorizaciones. Solo la clave.", normal))

    story.append(Paragraph("Paso 4 — Inteligencia artificial (para leer respuestas de clientes)", h2))
    for t in [
        "Claude (Anthropic): entra a console.anthropic.com → crea una API Key.",
        "OpenAI: entra a platform.openai.com → crea una API Key.",
        "Pon el proveedor (claude u openai) y la clave en los campos correspondientes.",
    ]:
        story.append(Paragraph("• " + t, bullet))

    story.append(Paragraph("Paso 5 — Activar el modo real (desactivar demo)", h2))
    for t in [
        "Cuando hayas introducido todas las claves, desactiva 'Modo demo (simular IA/Maps)'.",
        "Asegúrate de que 'Usar credenciales del panel (modo Lucía)' esté activado.",
        "Pulsa 'Guardar credenciales'.",
    ]:
        story.append(Paragraph("• " + t, bullet))
    story.append(Paragraph(
        "¡Listo! A partir de ahora la app usa tus claves reales. "
        "Si algo falla, vuelve a activar el modo demo y avisa a tu compañero.", normal))

    story.append(Paragraph("Respuesta a tus dudas frecuentes", h2))
    story.append(Paragraph("¿Qué es el 'client_id'?", normal))
    story.append(Paragraph(
        "Es un código largo (ejemplo: 123456-abc...apps.googleusercontent.com) que Google te da "
        "al crear las credenciales OAuth. Lo copias y lo pegas en el campo 'Google Client ID' del panel.", normal))
    story.append(Paragraph("¿Y el archivo .json?", normal))
    story.append(Paragraph(
        "Probablemente es el archivo client_secrets.json que Google te ofrece para descargar. "
        "NO tienes que subirlo ni tocarlo. Solo copia el client_id y el client_secret de ese archivo "
        "(o de la pantalla de Google Cloud Console) y pégalos en los campos del panel. "
        "El archivo google_token.json se genera automáticamente cuando pulsas 'Autorizar Google Calendar'.", normal))

    story.append(Paragraph("Consejo final", h2))
    story.append(Paragraph(
        "Si no tienes alguna clave todavía, déjala vacía. La app seguirá funcionando en modo demo "
        "para esa función (sin romperse). Rellénala cuando la tengas.", normal))

    doc.build(story)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="guia_lucia_el_acebuche.pdf"'
    return response
