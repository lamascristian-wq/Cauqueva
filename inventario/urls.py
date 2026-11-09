from django.urls import path
from . import views

urlpatterns = [
    path('', views.panel_principal, name='dashboard'),
    path('nuevo/', views.registrar_producto, name='nuevo_producto'),
    
    # NUEVA RUTA: Recibe un número entero (<int:id>) para saber qué producto editar
    path('editar/<int:id>/', views.editar_producto, name='editar_producto'),
    path('eliminar/<int:id>/', views.eliminar_producto, name='eliminar_producto'),
]