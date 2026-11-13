# Script de datos iniciales para El Acebuche.
# Ejecutar: python seed.py

import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "acebuche.settings")
django.setup()

from django.contrib.auth.models import User
from core.models import Perfil
from reservas.models import Plataforma, EstadoReserva, PuntoRecogida

# --- Superusuario ---
username = os.environ.get("ADMIN_USER", "admin")
password = os.environ.get("ADMIN_PASSWORD", "admin1234")
email = os.environ.get("ADMIN_EMAIL", "admin@elacebuche.es")

if not User.objects.filter(username=username).exists():
    u = User.objects.create_superuser(username, email, password)
    Perfil.objects.create(user=u, rol=Perfil.ROL_ADMIN)
    print("Superusuario creado: " + username + " / " + password)
else:
    print("El superusuario " + username + " ya existe.")

# --- Plataformas ---
for nombre in ["Airbnb", "GetYourGuide", "Viator", "Email", "Web"]:
    Plataforma.objects.get_or_create(nombre=nombre)
print("Plataformas creadas.")

# --- Estados de reserva ---
estados = [
    ("pendiente_datos", "amarillo"),
    ("pendiente_decision", "rojo"),
    ("completa", "verde"),
    ("cancelada", "gris"),
]
for nombre, color in estados:
    EstadoReserva.objects.get_or_create(nombre=nombre, defaults={"color": color})
print("Estados creados.")

# --- Puntos de recogida iniciales (Sevilla) ---
puntos = [
    ("Parking Avenida de Roma", "Esquina Luis Montoto con Menendez Pelayo", "https://maps.app.goo.gl/zUVyMC1eGyYU9ub17"),
    ("Hotel Becquer", "Esquina calle Lumbreras con Alameda de Hercules", ""),
    ("Plaza del Duque", "Esquina calle Teniente Borges", ""),
    ("Junto a El Corte Ingles, frente al Hotel America", "", ""),
    ("Santa Justa", "Parada de taxis de la rotonda u Hotel Ibis Styles Santa Justa", ""),
    ("Macarena", "Parada de taxis del Arco o de la Basílica, u Hotel Exe Macarena", ""),
    ("Enfrente de la Plaza de Toros", "Parada de bus de Menendez Pelayo (Jardines de Murillo)", ""),
    ("Muy usada en 2026", "", ""),
]
for nombre, direccion, maps in puntos:
    PuntoRecogida.objects.get_or_create(
        nombre=nombre,
        defaults={"direccion": direccion, "enlace_maps": maps, "activo": True},
    )
print("Puntos de recogida creados.")

print("\nDatos iniciales listos.")
