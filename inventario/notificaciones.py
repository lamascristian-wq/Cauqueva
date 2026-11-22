
import logging

import resend

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction


logger = logging.getLogger(__name__)


def _required_setting(name):
    valor = getattr(settings, name, "")

    if not valor or not str(valor).strip():
        raise ImproperlyConfigured(
            f"Falta configurar la variable {name}."
        )

    return valor


def enviar_alerta_stock(materia_prima):
    """Envía por Resend una alerta de stock crítico."""

    unidad = materia_prima.get_unidad_medida_display()

    mensaje = (
        "Alerta crítica de stock\n\n"
        f"La materia prima {materia_prima.nombre} alcanzó un nivel crítico.\n\n"
        f"Stock actual: {materia_prima.stock_actual:g} {unidad}\n"
        f"Stock mínimo: {materia_prima.stock_minimo:g} {unidad}\n"
    )

    resend.api_key = _required_setting("RESEND_API_KEY")

    resend.Emails.send({
        "from": _required_setting("RESEND_FROM_EMAIL"),
        "to": [_required_setting("RESEND_TO_EMAIL")],
        "subject": "Alerta crítica de stock - CAUQUEVA",
        "text": mensaje,
    })


def _enviar_alerta_pendiente(materia_prima_id, using):
    """Envía la alerta pendiente sin afectar la operación de stock."""

    from .models import MateriaPrima

    materia = (
        MateriaPrima.objects.using(using)
        .filter(pk=materia_prima_id)
        .first()
    )

    if materia is None:
        return

    # Si el stock se recuperó antes de ejecutar el callback,
    # ya no corresponde enviar el correo.
    if (
        not materia.alerta_stock_enviada
        or materia.stock_actual > materia.stock_minimo
    ):
        return

    try:
        enviar_alerta_stock(materia)

    except Exception:
        logger.exception(
            "No se pudo enviar la alerta de stock de la materia prima %s.",
            materia.pk,
        )

        # Permite volver a intentar en un movimiento posterior.
        MateriaPrima.objects.using(using).filter(
            pk=materia_prima_id,
            alerta_stock_enviada=True,
        ).update(alerta_stock_enviada=False)


def actualizar_estado_alerta_stock(materia_prima_id, using="default"):
    """
    Programa una alerta cuando la materia prima entra en estado crítico.

    Si el stock se recupera, restablece el indicador para permitir
    una nueva alerta ante una futura caída.
    """

    from .models import MateriaPrima

    materia = (
        MateriaPrima.objects.using(using)
        .filter(pk=materia_prima_id)
        .first()
    )

    if materia is None:
        return

    esta_en_estado_critico = (
        materia.stock_actual <= materia.stock_minimo
    )

    if esta_en_estado_critico and not materia.alerta_stock_enviada:

        actualizado = MateriaPrima.objects.using(using).filter(
            pk=materia_prima_id,
            alerta_stock_enviada=False,
        ).update(alerta_stock_enviada=True)

        if actualizado:
            transaction.on_commit(
                lambda: _enviar_alerta_pendiente(
                    materia_prima_id,
                    using,
                ),
                using=using,
            )

    elif not esta_en_estado_critico and materia.alerta_stock_enviada:

        MateriaPrima.objects.using(using).filter(
            pk=materia_prima_id,
            alerta_stock_enviada=True,
        ).update(alerta_stock_enviada=False)
