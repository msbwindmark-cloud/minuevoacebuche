from django import template
from urllib.parse import quote

register = template.Library()


@register.filter
def whatsapp_url(telefono):
    """Devuelve un enlace wa.me con mensaje predeterminado si hay teléfono."""
    if not telefono:
        return "#"
    mensaje = "Hola, me escribes desde Centro Ecuestre El Acebuche sobre tu reserva de ruta a caballo."
    return f"https://wa.me/{telefono}?text={quote(mensaje)}"
