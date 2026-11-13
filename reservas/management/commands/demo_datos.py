# -*- coding: utf-8 -*-
"""
Carga datos ficticios para probar toda la app sin credenciales reales.

Crea (o recrea) reservas de ejemplo en todos los estados, de todas las
plataformas, con y sin transporte, incluyendo avisos urgentes para hoy y
mañana, conversaciones y registros de auditoría.

Uso:
    python manage.py demo_datos
    python manage.py demo_datos --reset    # borra y vuelve a crear los datos demo

Los datos demo se identifican porque su Message-ID empieza por "demo-".
Los datos reales (correos procesados de verdad) no se tocan.
"""

from datetime import date, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import LogApp, Perfil, registrar_log
from reservas.models import (
    Conversacion,
    EstadoReserva,
    Mensaje,
    Plataforma,
    PuntoRecogida,
    Reserva,
)

DEMO_MARK = "demo-"

PLATAFORMAS = ["Airbnb", "GetYourGuide", "Viator", "Email", "Web"]

ESTADOS = [
    ("pendiente_datos", "amarillo"),
    ("pendiente_decision", "rojo"),
    ("completa", "verde"),
    ("cancelada", "gris"),
]

# Nombre, dirección, enlace maps, latitud, longitud
PUNTOS = [
    ("Parking Avenida de Roma", "Esquina Luis Montoto con Menéndez Pelayo",
     "https://maps.app.goo.gl/zUVyMC1eGyYU9ub17", "37.386600", "-5.982200"),
    ("Hotel Bécquer", "Calle Lumbreras con Alameda de Hércules",
     "", "37.392800", "-5.993100"),
    ("Plaza del Duque", "Esquina calle Teniente Borges",
     "", "37.392000", "-5.997700"),
    ("El Corte Inglés - Hotel América", "Esquina Luis Montoto con Menéndez Pelayo",
     "", "37.384400", "-5.973600"),
    ("Santa Justa", "Parada de taxis de la rotonda u Hotel Ibis Styles Santa Justa",
     "", "37.392700", "-5.974300"),
    ("Macarena", "Parada de taxis del Arco o de la Basílica, u Hotel Exe Macarena",
     "", "37.402700", "-5.988900"),
    ("Plaza de Toros", "Parada de bus de Menéndez Pelayo (Jardines de Murillo)",
     "", "37.382300", "-5.986400"),
    ("Jardines de Murillo", "Parada de bus de Menéndez Pelayo",
     "", "37.383300", "-5.987300"),
]

# Cada reserva: offset de días respecto a hoy y datos del Excel de Lucía
RESERVAS = [
    {
        "offset": 0, "hora": "10:00", "plataforma": "GetYourGuide",
        "codigo": "GYG-2026-101", "personas": 2, "nombre": "Luka",
        "estado": "pendiente_datos", "transporte": False,
        "precio_unitario": "67.50", "pago_otros": "66.00",
    },
    {
        "offset": 1, "hora": "13:00", "plataforma": "Airbnb",
        "codigo": "HM4X2YZABC", "personas": 1, "nombre": "Andrea",
        "estado": "pendiente_datos", "transporte": False,
        "precio_unitario": "71.20",
    },
    {
        "offset": 2, "hora": "10:00", "plataforma": "Email",
        "codigo": "EM-2026-014", "personas": 2, "nombre": "Nadja",
        "telefono": "+34 600 111 222", "email": "nadja@example.com",
        "estado": "pendiente_decision", "transporte": True,
        "direccion": "Hotel Bécquer, Sevilla", "punto": None,
        "precio_unitario": "75.00", "pago_otros": "60.00",
        "nacionalidad": "Alemania", "edades": [38, 35],
    },
    {
        "offset": 3, "hora": "13:00", "plataforma": "GetYourGuide",
        "codigo": "GYG-2026-102", "personas": 2, "nombre": "Dmitri",
        "telefono": "+44 7700 900123", "email": "dmitri@example.com",
        "estado": "completa", "transporte": True,
        "direccion": "Parking Avenida de Roma, Sevilla",
        "punto": "Parking Avenida de Roma",
        "precio_unitario": "67.50", "pago_otros": "60.00",
        "nacionalidad": "Reino Unido", "edades": [34, 31],
        "experiencia": "Él sin experiencia; ella ha montado varios años (paso, trote y galope).",
        "monitor_recogida": "Marta", "monitor_experiencia": "Marta",
    },
    {
        "offset": 4, "hora": "10:00", "plataforma": "Airbnb",
        "codigo": "HM8KLMNOPQ", "personas": 2, "nombre": "Juan",
        "telefono": "+34 655 222 333", "email": "juan@example.com",
        "estado": "completa", "transporte": False,
        "precio_unitario": "71.20", "nacionalidad": "España",
        "edades": [45, 43], "experiencia": "Sin experiencia previa.",
    },
    {
        "offset": 5, "hora": "13:00", "plataforma": "Viator",
        "codigo": "BR-0000000456", "personas": 4, "nombre": "Daniela",
        "telefono": "+52 55 0000 0000", "email": "daniela@example.com",
        "estado": "completa", "transporte": False,
        "precio_unitario": "66.75", "nacionalidad": "México",
        "edades": [45, 43, 12, 10], "experiencia": "Los adultos han montado alguna vez.",
    },
    {
        "offset": 6, "hora": "10:00", "plataforma": "Email",
        "codigo": "EM-2026-015", "personas": 2, "nombre": "Sara",
        "telefono": "+34 611 333 444", "email": "sara@example.com",
        "estado": "completa", "transporte": True,
        "direccion": "Plaza del Duque, Sevilla", "punto": "Plaza del Duque",
        "precio_unitario": "75.00", "pago_otros": "30.00",
        "nacionalidad": "España", "edades": [29, 27],
        "monitor_recogida": "Marta", "monitor_experiencia": "Marta",
    },
    {
        "offset": 8, "hora": "13:00", "plataforma": "GetYourGuide",
        "codigo": "GYG-2026-103", "personas": 3, "nombre": "Katherine",
        "estado": "pendiente_datos", "transporte": False,
        "precio_unitario": "67.50", "pago_otros": "33.00",
        "monitor_experiencia": "Marta",
    },
    {
        "offset": -1, "hora": "10:00", "plataforma": "Airbnb",
        "codigo": "HM1ABCDEFG", "personas": 2, "nombre": "Fernanda",
        "telefono": "+55 11 99999 0000", "email": "fernanda@example.com",
        "estado": "completa", "transporte": True,
        "direccion": "Calle Lumbreras, Sevilla", "punto": "Hotel Bécquer",
        "precio_unitario": "71.20", "pago_otros": "0.00",
        "nacionalidad": "Brasil", "edades": [33, 30],
        "experiencia": "Principiantes, sin experiencia.",
    },
    {
        "offset": -2, "hora": "13:00", "plataforma": "GetYourGuide",
        "codigo": "GYG-2026-099", "personas": 2, "nombre": "Justus",
        "telefono": "+49 151 2345678", "email": "justus@example.com",
        "estado": "completa", "transporte": False,
        "precio_unitario": "67.50", "nacionalidad": "Alemania",
        "edades": [41, 39], "experiencia": "Con experiencia.",
    },
    {
        "offset": -5, "hora": "10:00", "plataforma": "Viator",
        "codigo": "BR-0000000401", "personas": 2, "nombre": "Alisha",
        "telefono": "+1 415 555 0101", "email": "alisha@example.com",
        "estado": "cancelada", "transporte": True,
        "direccion": "Hotel América, Sevilla", "punto": "El Corte Inglés - Hotel América",
        "precio_unitario": "66.75", "nacionalidad": "Estados Unidos",
        "edades": [36, 34], "experiencia": "Con experiencia.",
    },
    {
        "offset": 10, "hora": "10:00", "plataforma": "Web",
        "codigo": "WEB-2026-007", "personas": 4, "nombre": "Ana",
        "telefono": "+34 622 444 555", "email": "ana@example.com",
        "estado": "pendiente_decision", "transporte": False,
        "precio_unitario": "70.00", "nacionalidad": "España",
        "edades": [42, 40, 9, 7], "experiencia": "Los niños nunca han montado.",
    },
    {
        "offset": 12, "hora": "13:00", "plataforma": "Email",
        "codigo": "EM-2026-016", "personas": 2, "nombre": "Marco",
        "telefono": "+39 333 1234567", "email": "marco@example.com",
        "estado": "completa", "transporte": False,
        "precio_unitario": "75.00", "pago_otros": "45.00",
        "nacionalidad": "Italia", "edades": [50, 48],
        "experiencia": "Monta desde niño.",
    },
    {
        "offset": 15, "hora": "10:00", "plataforma": "GetYourGuide",
        "codigo": "GYG-2026-104", "personas": 2, "nombre": "Elena",
        "email": "elena@example.com",
        "estado": "pendiente_datos", "transporte": True,
        "direccion": "Santa Justa, Sevilla", "punto": None,
        "precio_unitario": "67.50", "nacionalidad": "Rusia",
        "edades": [31, 29],
    },
    {
        "offset": 1, "hora": "13:00", "plataforma": "Web",
        "codigo": "WEB-2026-008", "personas": 2, "nombre": "Peter",
        "telefono": "+44 7700 900999", "email": "peter@example.com",
        "estado": "pendiente_datos", "transporte": False,
        "precio_unitario": "70.00", "nacionalidad": "Reino Unido",
        "edades": [44, 42],
    },
    {
        "offset": 20, "hora": "10:00", "plataforma": "Airbnb",
        "codigo": "HM9QRSTUVW", "personas": 2, "nombre": "Sophie",
        "telefono": "+33 6 12 34 56 78", "email": "sophie@example.com",
        "estado": "completa", "transporte": False,
        "precio_unitario": "71.20", "nacionalidad": "Francia",
        "edades": [28, 30], "experiencia": "Con experiencia.",
    },
]

CONVERSACIONES = {
    "GYG-2026-102": [
        ("entrada", "Hi! We would like to book the transport service, we are staying at "
                    "Parking Avenida de Roma. I am 34 and my wife is 31. Our phone is "
                    "+44 7700 900123. We are from the UK.", "email"),
        ("salida", "Hi Dmitri, thank you for the information! We will pick you up at 12:30 "
                   "at Parking Avenida de Roma.", "email"),
    ],
    "EM-2026-014": [
        ("entrada", "Hola, somos Nadja y Klaus, de Alemania. Tenemos 38 y 35 años. "
                    "Queremos transporte, estamos en el Hotel Bécquer. Teléfono +34 600 111 222.",
         "email"),
    ],
    "WEB-2026-007": [
        ("entrada", "Hola, somos una familia de 4 (dos adultos y dos niños de 9 y 7 años). "
                    "¿Hay disponibilidad el día 10 a las 10:00? Gracias.", "web"),
    ],
}


class Command(BaseCommand):
    help = "Carga reservas y datos ficticios para probar la app sin credenciales reales"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra las reservas demo anteriores y las vuelve a crear",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        demo_previas = Reserva.objects.filter(message_id__startswith=DEMO_MARK)
        if demo_previas.exists():
            if not options["reset"]:
                self.stdout.write(
                    self.style.WARNING(
                        f"Ya hay {demo_previas.count()} reservas demo. "
                        "Usa --reset para borrarlas y crearlas de nuevo."
                    )
                )
                return
            borradas = demo_previas.count()
            demo_previas.delete()
            self.stdout.write(f"Reservas demo anteriores borradas: {borradas}")

        # --- Datos maestros -------------------------------------------------
        for nombre in PLATAFORMAS:
            Plataforma.objects.get_or_create(nombre=nombre)

        estados = {}
        for nombre, color in ESTADOS:
            estado, _ = EstadoReserva.objects.get_or_create(
                nombre=nombre, defaults={"color": color}
            )
            if estado.color != color:
                estado.color = color
                estado.save(update_fields=["color"])
            estados[nombre] = estado

        puntos = {}
        for nombre, direccion, enlace, lat, lon in PUNTOS:
            punto, _ = PuntoRecogida.objects.get_or_create(
                nombre=nombre,
                defaults={
                    "direccion": direccion,
                    "enlace_maps": enlace,
                    "latitud": Decimal(lat),
                    "longitud": Decimal(lon),
                    "activo": True,
                },
            )
            # Aseguramos coordenadas para que Maps funcione en modo demo
            if punto.latitud is None or punto.longitud is None:
                punto.latitud = Decimal(lat)
                punto.longitud = Decimal(lon)
                punto.save(update_fields=["latitud", "longitud"])
            puntos[nombre] = punto

        # --- Usuarios demo --------------------------------------------------
        lucia = self._crear_usuario("lucia", "lucia1234", "Lucía", Perfil.ROL_ADMIN)
        self._crear_usuario("dani", "dani1234", "Dani", Perfil.ROL_CONSULTA)

        # --- Reservas -------------------------------------------------------
        hoy = date.today()
        creadas = 0

        for datos in RESERVAS:
            plataforma = Plataforma.objects.get(nombre=datos["plataforma"])
            precio = (Decimal(datos["precio_unitario"]) * datos["personas"]).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            transporte = datos.get("transporte", False)
            importe_recogida = Decimal("60.00") if transporte else Decimal("0.00")
            total_experiencia = precio + importe_recogida
            porcentaje = (precio * Decimal("0.10")).quantize(Decimal("0.01"))

            fecha = hoy + timedelta(days=datos["offset"])
            hora = time.fromisoformat(datos["hora"])

            reserva = Reserva.objects.create(
                plataforma=plataforma,
                codigo_reserva=datos["codigo"],
                fecha_actividad=fecha,
                hora_actividad=hora,
                numero_personas=datos["personas"],
                nombre_cliente=datos["nombre"],
                telefono_cliente=datos.get("telefono", ""),
                email_cliente=datos.get("email", ""),
                idioma=datos.get("idioma", "en"),
                edades=datos.get("edades", []),
                experiencia=datos.get("experiencia", ""),
                quiere_transporte=transporte,
                direccion_alojamiento=datos.get("direccion", ""),
                punto_recogida=puntos.get(datos.get("punto")),
                enlace_maps_punto=(
                    puntos[datos["punto"]].enlace_maps
                    if datos.get("punto") in puntos
                    else ""
                ),
                precio_actividad=precio,
                cobrado=Decimal("0.00"),
                porcentaje_lucia=porcentaje,
                pago_otros=Decimal(datos.get("pago_otros", "0.00")),
                total_experiencia=total_experiencia,
                recogida_en_coche=transporte,
                importe_recogida=importe_recogida,
                monitor_recogida=datos.get("monitor_recogida", ""),
                monitor_experiencia=datos.get("monitor_experiencia", ""),
                nacionalidad=datos.get("nacionalidad", ""),
                estado=estados[datos["estado"]],
                color_evento=estados[datos["estado"]].color,
                message_id=f"{DEMO_MARK}{datos['codigo']}@elacebuche.local",
                fecha_procesado=timezone.now(),
            )

            conversacion = Conversacion.objects.create(
                reserva=reserva,
                asunto=f"Reserva {datos['codigo']} - {datos['nombre']}",
                fecha_ultimo_correo=timezone.now(),
            )
            for direccion, texto, canal in CONVERSACIONES.get(datos["codigo"], []):
                Mensaje.objects.create(
                    conversacion=conversacion,
                    direccion=direccion,
                    texto=texto,
                    plataforma_mensaje=canal,
                )

            registrar_log(
                usuario=lucia,
                accion=LogApp.ACCION_CREAR,
                modelo="Reserva",
                id_objeto=reserva.pk,
                detalle=(
                    f"Reserva demo creada desde {plataforma.nombre} "
                    f"({datos['codigo']}) para {datos['nombre']}."
                ),
            )
            creadas += 1

        # Un par de registros de auditoría adicionales
        for reserva in Reserva.objects.filter(message_id__startswith=DEMO_MARK)[:3]:
            registrar_log(
                usuario=lucia,
                accion=LogApp.ACCION_CAMBIO_ESTADO,
                modelo="Reserva",
                id_objeto=reserva.pk,
                detalle=f"Estado revisado por Lucía: {reserva.estado.nombre}.",
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"OK Datos demo cargados: {creadas} reservas, "
                f"{Plataforma.objects.count()} plataformas, "
                f"{EstadoReserva.objects.count()} estados y "
                f"{PuntoRecogida.objects.count()} puntos de recogida."
            )
        )
        self.stdout.write("")
        self.stdout.write("Usuarios de prueba:")
        self.stdout.write("  lucia / lucia1234  (rol administra)")
        self.stdout.write("  dani  / dani1234   (rol consulta)")
        self.stdout.write("  admin / admin1234  (superusuario, si ejecutaste seed.py)")
        self.stdout.write("")
        self.stdout.write("Prueba ahora: http://127.0.0.1:8000/")

    def _crear_usuario(self, username, password, first_name, rol):
        usuario = User.objects.filter(username=username).first()
        if not usuario:
            usuario = User.objects.create_user(
                username=username, password=password, first_name=first_name
            )
        perfil, _ = Perfil.objects.get_or_create(
            user=usuario, defaults={"rol": rol}
        )
        if perfil.rol != rol:
            perfil.rol = rol
            perfil.save(update_fields=["rol"])
        return usuario
