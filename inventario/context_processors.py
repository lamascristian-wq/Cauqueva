from .models import MateriaPrima
from django.db.models import F

def notificaciones_stock(request):
    # Si el usuario no está logueado, no mostramos nada
    if not request.user.is_authenticated:
        return {}

    alertas = MateriaPrima.objects.filter(
        stock_actual__lte=F("stock_minimo")
    ).order_by("nombre", "variedad")
    return {
        "total_alertas": alertas.count(),
        "alertas_recientes": alertas[:5],
    }