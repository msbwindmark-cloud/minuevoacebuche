"""
Middleware propio de core.

Por ahora asigna request.organizacion = None (reserva para futuro multi-tenant).
Deja la estructura lista si más adelante se quiere vender a varios centros.
"""


class OrganizacionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organizacion = None
        response = self.get_response(request)
        return response
