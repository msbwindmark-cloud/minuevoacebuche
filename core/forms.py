"""Formularios propios del proyecto."""

from django.contrib.auth.forms import AuthenticationForm


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
