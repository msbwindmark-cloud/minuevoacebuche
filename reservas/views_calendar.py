# -*- coding: utf-8 -*-
"""
Vistas de autorización OAuth para Google Calendar.

Lucia debe autenticar su cuenta de Google una sola vez para que la app
pueda crear eventos en su calendario 'Centro Ecuestre el Acebuche'.
"""

import json
import logging
import os

from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponseRedirect, HttpResponseBadRequest
from django.urls import reverse

from core.models import registrar_log

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _es_administra(user):
    return user.is_authenticated and getattr(user, 'perfil', None) and user.perfil.es_administra


@login_required
@user_passes_test(_es_administra)
def autorizar_google_calendar(request):
    """
    Inicia el flujo OAuth de Google Calendar.
    Redirige a la página de consentimiento de Google.
    """
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        logger.error('google-auth-oauthlib no instalado')
        return JsonResponse({
            'error': 'google-auth-oauthlib no instalado. Ejecuta: pip install google-auth-oauthlib google-auth google-auth-httplib2 google-api-python-client'
        }, status=500)

    client_secrets_file = getattr(settings, 'GOOGLE_CREDENTIALS_FILE', None)
    if not client_secrets_file or not os.path.exists(client_secrets_file):
        return JsonResponse({
            'error': (
                'No se encontro google_client_secrets.json en la raiz del proyecto. '
                'Descargalo de Google Cloud Console y guardalo ahi.'
            )
        }, status=400)

    flow = Flow.from_client_secrets_file(
        str(client_secrets_file),
        scopes=SCOPES,
        redirect_uri=getattr(settings, 'GOOGLE_REDIRECT_URI', ''),
    )

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
    )

    request.session['oauth_state'] = state

    return HttpResponseRedirect(authorization_url)


@login_required
@user_passes_test(_es_administra)
def oauth2callback_google_calendar(request):
    """
    Callback de Google OAuth. Guarda el token en google_token.json.
    """
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        return JsonResponse({'error': 'google-auth-oauthlib no instalado'}, status=500)

    state = request.session.pop('oauth_state', None)
    if not state:
        return HttpResponseBadRequest('Falta state de OAuth')

    client_secrets_file = getattr(settings, 'GOOGLE_CREDENTIALS_FILE', None)
    if not client_secrets_file or not os.path.exists(client_secrets_file):
        return JsonResponse({'error': 'No se encontro google_client_secrets.json'}, status=400)

    flow = Flow.from_client_secrets_file(
        str(client_secrets_file),
        scopes=SCOPES,
        state=state,
        redirect_uri=getattr(settings, 'GOOGLE_REDIRECT_URI', ''),
    )

    try:
        flow.fetch_token(authorization_response=request.build_absolute_uri())
    except Exception as exc:
        logger.error(f'Error obteniendo token OAuth: {exc}')
        return JsonResponse({'error': f'No se pudo obtener el token: {exc}'}, status=400)

    creds = flow.credentials

    token_file = getattr(settings, 'GOOGLE_TOKEN_FILE', None)
    if token_file:
        token_data = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes,
        }
        token_file.write_text(json.dumps(token_data, indent=2))
        logger.info(f'Token de Google guardado en {token_file}')

    registrar_log(
        usuario=request.user,
        accion='configuracion',
        modelo='GoogleCalendar',
        detalle='Autorizacion OAuth de Google Calendar completada por Lucia.',
        request=request,
    )

    return HttpResponseRedirect(f"{reverse('pendientes')}?calendar=autorizado")
