from django.contrib import admin
from .models import MateriaPrima, MovimientoStock,Proveedor, Producto, IngredienteReceta

# Registramos todas las tablas para poder gestionarlas desde el panel azul
admin.site.register(MateriaPrima)
admin.site.register(MovimientoStock)

@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin): #puede que salga problema de unfold
    list_display = ('nombre', 'telefono')
    
class IngredienteInline(admin.TabularInline):
    model = IngredienteReceta
    extra = 1

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    inlines = [IngredienteInline]
    list_display = ("nombre", "precio", "activo")
