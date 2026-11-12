from django.contrib import admin
from .models import MateriaPrima, MovimientoStock,Proveedor

# Registramos todas las tablas para poder gestionarlas desde el panel azul
admin.site.register(MateriaPrima)
admin.site.register(MovimientoStock)

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin): #puede que salga problema de unfold
    list_display = ('nombre', 'telefono')