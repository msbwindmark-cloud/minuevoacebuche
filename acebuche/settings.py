"""
Configuración del proyecto - Centro Ecuestre El Acebuche
App de reservas de turismo ecuestre: leer correos → Google Calendar → panel de pendientes.

Stack (según especificaciones):
- Python 3.11+ / Django >=5.2,<7
- Bootswatch + SweetAlert2 + toasts + AJAX (fetch + CSRF)
- WhiteNoise para estáticos (despliegue en PythonAnywhere)
- SQLite en desarrollo, PostgreSQL en producción (comentado)
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas base
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Carga de variables de entorno desde archivo .env (si existe)
# ---------------------------------------------------------------------------
def _load_env():
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

_load_env()

# ---------------------------------------------------------------------------
# Seguridad
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-cambiar-en-produccion")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h.strip() for h in os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1"
).split(",") if h.strip()]

# ---------------------------------------------------------------------------
# Aplicaciones
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Apps propias
    "core",
    "reservas",

    # WhiteNoise para servir estáticos en producción (PythonAnywhere)
    "whitenoise.runserver_nostatic",
]

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Middleware propio (asigna organización a la request si multi-tenant)
    "core.middleware.OrganizacionMiddleware",
]

ROOT_URLCONF = "acebuche.urls"

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "acebuche.wsgi.application"
ASGI_APPLICATION = "acebuche.asgi.application"

# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------
# Desarrollo: SQLite. Producción (PythonAnywhere): descomentar DATABASE_URL
# e instalar dj-database-url / psycopg2 para PostgreSQL.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Ejemplo PostgreSQL (descomentar y configurar .env en producción):
# import dj_database_url  # pip install dj-database-url
# DATABASES = {"default": dj_database_url.config(
#     default=os.environ.get("DATABASE_URL"),
#     conn_max_age=600,
# )}

# ---------------------------------------------------------------------------
# Validación de contraseñas
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internacionalización
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "es-es"
TIME_ZONE = "Europe/Madrid"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Archivos estáticos y media
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# WhiteNoise: comprimir y servir estáticos en producción
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# Clave primaria por defecto
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "pendientes"
LOGOUT_REDIRECT_URL = "login"

# ---------------------------------------------------------------------------
# Correo (Hostalia - info@elacebuche.es)
# ---------------------------------------------------------------------------
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "imap.servidor-correo.net")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "info@elacebuche.es")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "info@elacebuche.es")

# IMAP para leer correos entrantes (Hostalia)
IMAP_HOST = os.environ.get("IMAP_HOST", "imap.servidor-correo.net")
IMAP_PORT = int(os.environ.get("IMAP_PORT", "993"))
IMAP_USER = os.environ.get("IMAP_USER", "info@elacebuche.es")
IMAP_PASSWORD = os.environ.get("IMAP_PASSWORD", "")
IMAP_CARPETA_ENTRADA = os.environ.get("IMAP_CARPETA_ENTRADA", "INBOX")
IMAP_CARPETA_PROCESADO = os.environ.get("IMAP_CARPETA_PROCESADO", "Procesado")
IMAP_REVISAR_CADA_HORAS = int(os.environ.get("IMAP_REVISAR_CADA_HORAS", "3"))

# ---------------------------------------------------------------------------
# Google Calendar
# ---------------------------------------------------------------------------
GOOGLE_CALENDAR_ID = os.environ.get(
    "GOOGLE_CALENDAR_ID", "luciagilran2014@gmail.com"
)
GOOGLE_CALENDAR_NAME = "Centro Ecuestre el Acebuche"
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI", "http://localhost:8000/calendar/oauth2callback/"
)
GOOGLE_TOKEN_FILE = BASE_DIR / "google_token.json"
GOOGLE_CREDENTIALS_FILE = BASE_DIR / "google_client_secrets.json"

# ---------------------------------------------------------------------------
# Google Maps (geocodificación y distancia a pie)
# ---------------------------------------------------------------------------
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

# ---------------------------------------------------------------------------
# IA (opcional, para interpretar respuestas de clientes en varios idiomas)
# ---------------------------------------------------------------------------
IA_API_KEY = os.environ.get("IA_API_KEY", "")

# ---------------------------------------------------------------------------
# Auditoría / registro de acciones de la app
# ---------------------------------------------------------------------------
AUDIT_LOG_ENABLED = True

# ---------------------------------------------------------------------------
# Precio transporte fijo (según Word: 60 € por vehículo, ida y vuelta)
# ---------------------------------------------------------------------------
PRECIO_TRANSPORTE = float(os.environ.get("PRECIO_TRANSPORTE", "60.00"))

# ---------------------------------------------------------------------------
# Plantillas de mensajes (secciones 8.1, 8.2, 8.3 del Word)
# Se pueden personalizar desde .env o desde la base de datos más adelante.
# ---------------------------------------------------------------------------
MENSAJE_PREGUNTAS = os.environ.get(
    "MENSAJE_PREGUNTAS",
    "Hi, I need to know this things :\n"
    "- What is your phone number? (+ prefix - number)\n"
    "- Do you speak Spanish?\n"
    "- Where are you from?\n"
    "- How old are you?\n"
    "- Do you have experience riding horses? What experience?\n"
    "If you're interested in transport service, we need to know the address of your hotel or apartment "
    "to find a nearby pick-up point that is convenient for you.\n"
    "About transportation, we have an additional service of pickup of clients. "
    "The price's 60 € for vehicle, not for person, round trip. "
    "You have to pay it in cash in our farm.",
)

RESPUESTA_SIN_TRANSPORTE = os.environ.get(
    "RESPUESTA_SIN_TRANSPORTE",
    "Hi {nombre},\n"
    "Thank you for sharing your information!\n"
    "Here is the location of our farm so you can get there easily: "
    "https://maps.app.goo.gl/zUVyMC1eGyYU9ub17\n"
    "The activity starts at {hora} on {fecha}.\n"
    "There is no need to arrive earlier.\n"
    "See you soon !",
)

RESPUESTA_CON_TRANSPORTE = os.environ.get(
    "RESPUESTA_CON_TRANSPORTE",
    "Hi {nombre},\n"
    "Thank you for the information!\n"
    "We will pick you up on {fecha} at {hora_recogida} at this point {punto}.\n"
    "I send you the location in the following link: {enlace_maps}\n"
    "Remember that the transport service costs 60 € per vehicle (round trip), "
    "paid in cash at our farm.\n"
    "See you soon !",
)

# ---------------------------------------------------------------------------
# Avisos urgentes (días de antelación)
# ---------------------------------------------------------------------------
AVISO_RESERVA_PROXIMA_DIAS = int(os.environ.get("AVISO_RESERVA_PROXIMA_DIAS", "1"))
