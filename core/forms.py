"""Formularios propios del proyecto."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Configuracion


class LoginForm(AuthenticationForm):
    """Formulario de login con los campos estilizados con Bootstrap."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {
                "class": "form-control form-control-lg",
                "placeholder": "Tu usuario",
                "autofocus": True,
            }
        )
        self.fields["password"].widget.attrs.update(
            {
                "class": "form-control form-control-lg pe-5",
                "placeholder": "Tu contraseña",
            }
        )


class ConfiguracionForm(forms.ModelForm):
    """Formulario para que Lucía introduzca sus credenciales privadas."""

    class Meta:
        model = Configuracion
        fields = "__all__"
        widgets = {
            "email_host_password": forms.PasswordInput(render_value=True, attrs={"class": "form-control"}),
            "imap_password": forms.PasswordInput(render_value=True, attrs={"class": "form-control"}),
            "google_client_secret": forms.PasswordInput(render_value=True, attrs={"class": "form-control"}),
            "google_maps_api_key": forms.PasswordInput(render_value=True, attrs={"class": "form-control"}),
            "ia_api_key": forms.PasswordInput(render_value=True, attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if not isinstance(field.widget, forms.PasswordInput):
                if isinstance(field.widget, forms.CheckboxInput):
                    field.widget.attrs.setdefault("class", "form-check-input")
                elif isinstance(field.widget, forms.Textarea):
                    field.widget.attrs.setdefault("class", "form-control")
                else:
                    field.widget.attrs.setdefault("class", "form-control")

