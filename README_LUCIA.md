# Centro Ecuestre El Acebuche - App de reservas

## Para poner en marcha (solo faltan las claves de Lucía)

### 1. Configurar las credenciales en `.env`
Edita el archivo `.env` en la raíz del proyecto y rellena:

| Variable | Qué es | Dónde conseguirla |
|---|---|---|
| `EMAIL_HOST_PASSWORD` | Contraseña del correo `info@elacebuche.es` (Hostalia) | Lucía la tiene |
| `IMAP_PASSWORD` | Contraseña IMAP (misma que el correo) | Lucía la tiene |
| `GOOGLE_CLIENT_ID` | ID de cliente de Google Cloud Console | Lucía lo crea en Google Cloud |
| `GOOGLE_CLIENT_SECRET` | Secreto de cliente de Google Cloud Console | Lucía lo crea en Google Cloud |
| `GOOGLE_MAPS_API_KEY` | API key de Google Maps Platform | Lucía la crea en Google Cloud |
| `IA_API_KEY` | Clave de IA (Claude o OpenAI) | Lucía la consigue en Anthropic o OpenAI |

### 2. Autenticar Google Calendar (una sola vez)
Entra como administrador en:
```
http://localhost:8000/calendar/autorizar/
```
Inicia sesión con la cuenta `luciagilran2014@gmail.com` y acepta los permisos.  
Se guardará el token en `google_token.json`.

### 3. Probar el flujo completo
```
python manage.py procesar_correos
```
Esto lee los correos de `info@elacebuche.es`, crea las reservas y los eventos en Google Calendar.

O desde el navegador (solo admin):
```
http://localhost:8000/procesar-correos/
```

---

## Qué hace la app (según el Word y el Excel)

### Leer correos (IMAP cada 3 horas)
- Lee `info@elacebuche.es` (Hostalia)
- Clasifica: reserva nueva (Airbnb, GYG, Viator, Email, Web), mensaje de cliente, cancelación, consulta, otros
- Extrae: plataforma, código de reserva, fecha, hora, personas, nombre, teléfono, idioma, dirección

### Google Calendar
- Crea eventos con formato: "Actividad turismo (N pax)"
- Descripción con plataforma, código, datos del cliente, transporte, enlace Maps del centro
- Colores: amarillo (faltan datos), rojo (decisión de Lucía), verde (completa), gris (cancelada)

### Panel de pendientes
- Pantalla única con todo lo que necesita atención de Lucía
- Avisos urgentes: reserva para hoy/mañana sin datos, punto de recogida sin decidir
- Acciones concretas por reserva

### IA para respuestas de clientes
- Interpreta textos libres en cualquier idioma
- Extrae: nacionalidad, edades, teléfono, experiencia, transporte, dirección de alojamiento

### Google Maps para puntos de recogida
- Geocodifica el alojamiento del cliente
- Calcula minutos andando hasta cada punto fijo de Sevilla
- Propone el más cercano si está a ≤ 10 min
- Si ninguno cumple, pasa a pendientes para que Lucía elija

### Mensajes automáticos al cliente
- Mensaje de preguntas (sección 8.1 del Word) — inglés
- Respuesta sin transporte (sección 8.2)
- Respuesta con transporte (sección 8.3)
- Se envían desde info@elacebuche.es por WhatsApp (enlace wa.me)

### Exportación a Excel (para las cuentas de Lucía)
```
python manage.py exportar_excel --mes 11 --anio 2026
```
Genera un Excel con 3 hojas: reservas del mes, resumen por plataforma, resumen mensual (con todas las columnas del Excel original: importe, cobrado, % Lucía, recogida en coche, monitores, total experiencia, comparativa por plataformas y personas).

---

## Usuarios
- **Superusuario**: `admin` / `admin1234` (puede acceder al panel admin `/admin/` y a configuración)
- Lucía y sus trabajadores entran con su propio usuario

---

## Despliegue en PythonAnywhere
Cuando estés listo para llevar la app a producción:
1. Sube el proyecto a PythonAnywhere
2. Configura `DJANGO_DEBUG=0` y `DJANGO_ALLOWED_HOSTS=tudominio.pythonanywhere.com`
3. Ejecuta `python manage.py collecttext`
4. Configura las variables de entorno en el panel de PythonAnywhere
5. Crea una tarea programada cada 3 horas: `python manage.py procesar_correos`
