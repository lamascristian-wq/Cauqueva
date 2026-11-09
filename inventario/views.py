from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import MateriaPrima, Movimiento
from .forms import MovimientoForm

# 1. Vista del Panel Principal
def panel_principal(request):
    materias_primas = MateriaPrima.objects.filter(activo=True)
    resumen = []
    for mp in materias_primas:
        variedades = mp.variedad_set.filter(activo=True)
        if variedades.exists():
            for var in variedades:
                movimientos = Movimiento.objects.filter(materia_prima=mp, variedad=var)
                stock = sum(m.cantidad_kg * m.efecto_stock for m in movimientos)
                resumen.append({'id_materia': mp.id, 'nombre': mp.nombre, 'variedad': var.nombre, 'stock': stock, 'unidad': 'kg'})
        else:
            movimientos = Movimiento.objects.filter(materia_prima=mp, variedad__isnull=True)
            stock = sum(m.cantidad_kg * m.efecto_stock for m in movimientos)
            resumen.append({'id_materia': mp.id, 'nombre': mp.nombre, 'variedad': 'Sin variedad', 'stock': stock, 'unidad': 'kg'})
    return render(request, 'inventario/dashboard.html', {'productos': resumen})

# 2. Vista para Registrar un Movimiento
def registrar_producto(request):
    if request.method == 'POST':
        formulario = MovimientoForm(request.POST)
        if formulario.is_valid():
            formulario.save()
            return redirect('dashboard')
    else:
        formulario = MovimientoForm()
    return render(request, 'inventario/formulario.html', {'formulario': formulario})

# 3. Vista del Historial (CU-08)
def historial_producto(request, id):
    materia = get_object_or_404(MateriaPrima, id=id)
    movimientos = Movimiento.objects.filter(materia_prima=materia)
    return render(request, 'inventario/historial.html', {'materia': materia, 'movimientos': movimientos})

# 4. Vista de Informes Mensuales (CU-07)
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