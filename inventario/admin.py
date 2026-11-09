from django.contrib import admin
from .models import MateriaPrima, Variedad, UnidadMedida, TipoMovimiento, Movimiento

# Registramos todas las tablas para poder gestionarlas desde el panel azul
admin.site.register(MateriaPrima)
admin.site.register(Variedad)
admin.site.register(UnidadMedida)
admin.site.register(TipoMovimiento)
admin.site.register(Movimiento)