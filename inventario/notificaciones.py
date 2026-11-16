from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class NotificationDeliveryError(Exception):
    """Raised when one or more stock-alert notification channels fail."""


def _required_setting(name):
    value = getattr(settings, name, "")
    if not value:
        raise ImproperlyConfigured(f"Falta configurar la variable {name}.")
    return value


def enviar_alerta_stock(materia_prima):
    unidad = materia_prima.get_unidad_medida_display()
    mensaje = (
        f"Alerta Crítica: El stock de {materia_prima.nombre} ha caído a "
        f"{materia_prima.stock_actual:g} {unidad} "
        f"(Mínimo: {materia_prima.stock_minimo:g})"
    )
    errores = []

    try:
        import resend

        resend.api_key = _required_setting("RESEND_API_KEY")
        resend.Emails.send(
            {
                "from": _required_setting("RESEND_FROM_EMAIL"),
                "to": [_required_setting("RESEND_TO_EMAIL")],
                "subject": "Alerta crítica de stock",
                "text": mensaje,
            }
        )
    except Exception as error:
        errores.append(("Resend", error))

    try:
        from twilio.rest import Client

        cliente = Client(
            _required_setting("TWILIO_ACCOUNT_SID"),
            _required_setting("TWILIO_AUTH_TOKEN"),
        )
        cliente.messages.create(
            body=mensaje,
            from_=_required_setting("TWILIO_WHATSAPP_FROM"),
            to=_required_setting("TWILIO_WHATSAPP_TO"),
        )
    except Exception as error:
        errores.append(("Twilio", error))

    if errores:
        canales = ", ".join(nombre for nombre, _ in errores)
        raise NotificationDeliveryError(
            f"No se pudieron enviar las alertas por: {canales}."
        ) from errores[0][1]
