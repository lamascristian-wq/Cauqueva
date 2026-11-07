from django.contrib import admin
from .models import MateriaPrima

@admin.register(MateriaPrima)
class MateriaPrimaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'variedad', 'unidad_medida', 'stock_actual', 'stock_minimo')
    search_fields = ('nombre', 'variedad')
    list_filter = ('unidad_medida',) 
# Register your models here.
