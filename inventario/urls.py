from django.urls import path
from . import views

urlpatterns = [
    path('', views.panel_principal, name='dashboard'),
    path('nuevo/', views.registrar_producto, name='nuevo_producto'),
    
    # NUEVA RUTA para el historial
    path('historial/<int:id>/', views.historial_producto, name='historial_producto'),
    path('informes/', views.generar_informe, name='informes'),
    path('informes/exportar/', views.exportar_informe_csv, name='exportar_informe'),
]