from django.urls import path
from . import views

urlpatterns = [
    path('', views.panel_principal, name='dashboard'),
    
    # Agregamos la ruta para el nuevo formulario
    path('nuevo/', views.registrar_producto, name='nuevo_producto'),
]