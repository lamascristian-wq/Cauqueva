from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from . import views

urlpatterns = [
    path('', views.panel_principal, name='panelprincipal'),
#    path('nuevo/', views.registrar_producto, name='nuevo_producto'),
    path('historialgeneral/', views.historial_general, name='historial'),
    #reportes y generacion de informes
    path("reportes/", views.reportes, name="reportes"),
    path("reportes/csv/", views.reportes_csv, name="reportes_csv"),
    #materias primas
    path('registrarmateriaprima/', views.registrar_materia_prima, name='registrar_materia_prima'),
    path('inventariostock/', views.listar_inventario, name='inventariostock'),
    path('alertas/', views.alertas_stock, name='alertas'),
    #consumo
    path("consumos/", views.consumos, name="consumos"),
    path("consumos/nuevo/", views.registrar_consumo, name="registrar_consumo"),
    #proveedores
    path("proveedores/", views.proveedores, name="proveedores"),
    path("proveedores/nuevo/", views.crear_proveedor, name="crear_proveedor"),
    path("proveedores/<int:pk>/editar/", views.editar_proveedor, name="editar_proveedor"),
    # NUEVAS RUTAS DE ACCESO PARA TODO EL PERSONAL
    path('login/', LoginView.as_view(template_name='inventario/login.html'), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
]