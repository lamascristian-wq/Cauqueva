from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from . import views

urlpatterns = [
    path('', views.panel_principal, name='panelprincipal'),
    
    # --- HISTORIAL DE MOVIMIENTOS ---
    path('historialgeneral/', views.historial_general, name='historial'),
    path('historial/exportar/', views.exportar_historial, name='exportar_historial'),
    path('historial/editar/<int:id>/', views.editar_movimiento, name='editar_movimiento'),
    
    # --- REPORTES Y GENERACIÓN DE INFORMES ---
    path("reportes/", views.reportes, name="reportes"),
    path("reportes/csv/", views.reportes_csv, name="reportes_csv"),
#documentar las rutas explicar que hace cada ruta    
    # --- MATERIAS PRIMAS E INGRESOS ---
    path('registrarmateriaprima/', views.registrar_materia_prima, name='registrar_materia_prima'),
    path('ingresos/nuevo/', views.registrar_movimiento, name='registrar_movimiento'), # <--- ESTA ERA LA RUTA FALTANTE
    path('inventariostock/', views.listar_inventario, name='inventariostock'),
    path('alertas/', views.alertas_stock, name='alertas'),
    
    # --- CONSUMO ---
    path("consumos/", views.consumos, name="consumos"),
    path("consumos/nuevo/", views.registrar_consumo, name="registrar_consumo"),
    
    # --- PROVEEDORES ---
    path("proveedores/", views.proveedores, name="proveedores"),
    path("proveedores/nuevo/", views.crear_proveedor, name="crear_proveedor"),
    path("proveedores/<int:pk>/editar/", views.editar_proveedor, name="editar_proveedor"),
    
    # --- ACCESO Y AUTENTICACIÓN ---
    path('login/', LoginView.as_view(template_name='inventario/login.html'), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
]