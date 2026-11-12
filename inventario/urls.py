from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from . import views

urlpatterns = [
    path('', views.panel_principal, name='dashboard'),
    path('nuevo/', views.registrar_producto, name='nuevo_producto'),
    path('nueva-materia-prima/', views.registrar_materia_prima, name='nueva_materia_prima'),
    path('obtener-variedades/', views.obtener_variedades, name='obtener_variedades'),
    path('historial/<int:id>/', views.historial_producto, name='historial_producto'),
    path('informes/', views.generar_informe, name='informes'),
    path('informes/exportar/', views.exportar_informe_csv, name='exportar_informe'),
    
    # NUEVAS RUTAS DE ACCESO PARA TODO EL PERSONAL
    path('login/', LoginView.as_view(template_name='inventario/login.html'), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
]