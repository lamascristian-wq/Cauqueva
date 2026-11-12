from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import MateriaPrima, Variedad, Movimiento
from .forms import MovimientoForm
import csv 
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
# Función auxiliar para comprobar si el usuario es "Gerente" (Staff)
def es_gerente(user):
    return user.is_staff

# 1. Vista del Panel Principal
@login_required(login_url='login')
def panel_principal(request):
    materias_primas = MateriaPrima.objects.filter(activo=True)
    resumen = []
    for mp in materias_primas:
        variedades = mp.variedad_set.filter(activo=True)
        if variedades.exists():
            for var in variedades:
                movimientos = Movimiento.objects.filter(materia_prima=mp, variedad=var)
                stock = sum(m.cantidad_kg * m.efecto_stock for m in movimientos)
                # NUEVO: Comparamos si el stock está por debajo o igual al mínimo
                alerta = stock <= mp.stock_minimo
                resumen.append({'id_materia': mp.id, 'nombre': mp.nombre, 'variedad': var.nombre, 'stock': stock, 'unidad': 'kg', 'stock_minimo': mp.stock_minimo, 'alerta': alerta})
        else:
            movimientos = Movimiento.objects.filter(materia_prima=mp, variedad__isnull=True)
            stock = sum(m.cantidad_kg * m.efecto_stock for m in movimientos)
            # NUEVO: Comparamos si el stock está por debajo o igual al mínimo
            alerta = stock <= mp.stock_minimo
            resumen.append({'id_materia': mp.id, 'nombre': mp.nombre, 'variedad': 'Sin variedad', 'stock': stock, 'unidad': 'kg', 'stock_minimo': mp.stock_minimo, 'alerta': alerta})
    return render(request, 'inventario/dashboard.html', {'productos': resumen})

@login_required(login_url='login')
def obtener_variedades(request):
    materia_id = request.GET.get('materia_id')

    variedades = Variedad.objects.filter(
        materia_prima_id=materia_id,
        activo=True
    ).values('id', 'nombre')

    return JsonResponse(list(variedades), safe=False)

# 2. Vista para Registrar un Movimiento
@login_required(login_url='login')
def registrar_producto(request):
    if request.method == 'POST':
        formulario = MovimientoForm(request.POST)
        if formulario.is_valid():
            formulario.save()
            messages.success(request, '¡Movimiento registrado correctamente!')
            return redirect('dashboard')
    else:
        formulario = MovimientoForm()
    return render(request, 'inventario/formulario.html', {'formulario': formulario})

# 3. Vista del Historial (CU-08)
@login_required(login_url='login')
def historial_producto(request, id):
    materia = get_object_or_404(MateriaPrima, id=id)
    movimientos = Movimiento.objects.filter(materia_prima=materia)
    return render(request, 'inventario/historial.html', {'materia': materia, 'movimientos': movimientos})

# 4. Vista de Informes Mensuales (CU-07)
@login_required(login_url='login')
def generar_informe(request):
    hoy = timezone.now()
    mes_seleccionado = int(request.GET.get('mes', hoy.month))
    anio_seleccionado = int(request.GET.get('anio', hoy.year))
    materias_primas = MateriaPrima.objects.filter(activo=True)
    reporte = []
    
    for mp in materias_primas:
        variedades = mp.variedad_set.filter(activo=True)
        if variedades.exists():
            for var in variedades:
                movs_historicos = Movimiento.objects.filter(materia_prima=mp, variedad=var)
                stock_total = sum(m.cantidad_kg * m.efecto_stock for m in movs_historicos)
                movs_mes = movs_historicos.filter(fecha__year=anio_seleccionado, fecha__month=mes_seleccionado)
                ingresos_mes = sum(m.cantidad_kg for m in movs_mes if m.efecto_stock == 1)
                consumos_mes = sum(m.cantidad_kg for m in movs_mes if m.efecto_stock == -1)
                reporte.append({'nombre': mp.nombre, 'variedad': var.nombre, 'ingresos': ingresos_mes, 'consumos': consumos_mes, 'stock_total': stock_total, 'unidad': 'kg'})
        else:
            movs_historicos = Movimiento.objects.filter(materia_prima=mp, variedad__isnull=True)
            stock_total = sum(m.cantidad_kg * m.efecto_stock for m in movs_historicos)
            movs_mes = movs_historicos.filter(fecha__year=anio_seleccionado, fecha__month=mes_seleccionado)
            ingresos_mes = sum(m.cantidad_kg for m in movs_mes if m.efecto_stock == 1)
            consumos_mes = sum(m.cantidad_kg for m in movs_mes if m.efecto_stock == -1)
            reporte.append({'nombre': mp.nombre, 'variedad': 'Sin variedad', 'ingresos': ingresos_mes, 'consumos': consumos_mes, 'stock_total': stock_total, 'unidad': 'kg'})
            
    contexto = {'reporte': reporte, 'mes_seleccionado': mes_seleccionado, 'anio_seleccionado': anio_seleccionado, 'anios': [hoy.year - 1, hoy.year, hoy.year + 1]}
    return render(request, 'inventario/informe.html', contexto)
# NUEVA VISTA: Exportar Informe a Excel/CSV
@login_required(login_url='login')
def exportar_informe_csv(request):
    hoy = timezone.now()
    mes_seleccionado = int(request.GET.get('mes', hoy.month))
    anio_seleccionado = int(request.GET.get('anio', hoy.year))

    # Preparamos el archivo de respuesta
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Reporte_CAUQUEVA_{mes_seleccionado}_{anio_seleccionado}.csv"'
    # Añadimos codificación UTF-8 con BOM para que Excel lea bien los acentos
    response.write(u'\ufeff'.encode('utf8')) 
    
    writer = csv.writer(response, delimiter=';') # Usamos punto y coma para el Excel en español
    writer.writerow(['Producto', 'Variedad', 'Ingresos del Mes (kg)', 'Consumos del Mes (kg)', 'Stock Final (kg)'])

    materias_primas = MateriaPrima.objects.filter(activo=True)
    
    for mp in materias_primas:
        variedades = mp.variedad_set.filter(activo=True)
        if variedades.exists():
            for var in variedades:
                movs_historicos = Movimiento.objects.filter(materia_prima=mp, variedad=var)
                stock_total = sum(m.cantidad_kg * m.efecto_stock for m in movs_historicos)
                movs_mes = movs_historicos.filter(fecha__year=anio_seleccionado, fecha__month=mes_seleccionado)
                ingresos_mes = sum(m.cantidad_kg for m in movs_mes if m.efecto_stock == 1)
                consumos_mes = sum(m.cantidad_kg for m in movs_mes if m.efecto_stock == -1)
                
                writer.writerow([mp.nombre, var.nombre, f"{ingresos_mes:.2f}", f"{consumos_mes:.2f}", f"{stock_total:.2f}"])
        else:
            movs_historicos = Movimiento.objects.filter(materia_prima=mp, variedad__isnull=True)
            stock_total = sum(m.cantidad_kg * m.efecto_stock for m in movs_historicos)
            movs_mes = movs_historicos.filter(fecha__year=anio_seleccionado, fecha__month=mes_seleccionado)
            ingresos_mes = sum(m.cantidad_kg for m in movs_mes if m.efecto_stock == 1)
            consumos_mes = sum(m.cantidad_kg for m in movs_mes if m.efecto_stock == -1)
            
            writer.writerow([mp.nombre, 'Sin variedad', f"{ingresos_mes:.2f}", f"{consumos_mes:.2f}", f"{stock_total:.2f}"])

    return response