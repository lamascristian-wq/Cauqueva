from django.contrib import admin
from .models import MateriaPrima

@admin.register(MateriaPrima)
class MateriaPrimaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'stock_actual', 'stock_minimo') 
    search_fields = ('nombre',) 
# Register your models here.
