from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import MateriaPrima, Variedad, Movimiento
from .forms import MovimientoForm, MateriaPrimaForm
import csv 
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from datetime import datetime
from decimal import Decimal
from django.db.models import Q
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
        activo=True,
        materia_prima__activo=True
    ).values('id', 'nombre')

    return JsonResponse(list(variedades), safe=False)


@login_required(login_url='login')
def registrar_materia_prima(request):
    if request.method == 'POST':
        formulario = MateriaPrimaForm(request.POST)

        if formulario.is_valid():
            formulario.save()
            messages.success(
                request,
                '¡Materia prima registrada correctamente!'
            )
            return redirect('dashboard')
    else:
        formulario = MateriaPrimaForm()

    return render(
        request,
        'inventario/formulario_materia_prima.html',
        {'formulario': formulario}
    )

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

def _resumen_movimientos_informe(movimientos, fecha_inicio, fecha_fin):
    """
    Calcula los ingresos, consumos y stock al cierre del mes
    para un conjunto de movimientos.
    """
    movimientos_historicos = list(
        movimientos.filter(fecha__lt=fecha_fin)
    )

    movimientos_mes = [
        movimiento
        for movimiento in movimientos_historicos
        if movimiento.fecha >= fecha_inicio
    ]

    ingresos_mes = sum(
        movimiento.cantidad_kg
        for movimiento in movimientos_mes
        if movimiento.efecto_stock == 1
    )

    consumos_mes = sum(
        movimiento.cantidad_kg
        for movimiento in movimientos_mes
        if movimiento.efecto_stock == -1
    )

    stock_total = sum(
        movimiento.cantidad_kg * movimiento.efecto_stock
        for movimiento in movimientos_historicos
    )

    return {
        "ingresos": ingresos_mes,
        "consumos": consumos_mes,
        "stock_total": stock_total,
    }


def _generar_reporte_mensual(mes, anio):
    # Inicio del mes seleccionado.
    fecha_inicio = timezone.make_aware(datetime(anio, mes, 1))

    # Inicio del mes siguiente: funciona también para diciembre.
    if mes == 12:
        fecha_fin = timezone.make_aware(datetime(anio + 1, 1, 1))
    else:
        fecha_fin = timezone.make_aware(datetime(anio, mes + 1, 1))

    reporte = []
    materias_primas = MateriaPrima.objects.filter(activo=True)

    for mp in materias_primas:
        # Incluimos todas las variedades, incluso las inactivas.
        variedades = list(mp.variedad_set.all().order_by("nombre"))

        for var in variedades:
            movimientos = Movimiento.objects.filter(
                materia_prima=mp,
                variedad=var,
            )

            resumen = _resumen_movimientos_informe(
                movimientos,
                fecha_inicio,
                fecha_fin,
            )

            reporte.append({
                "nombre": mp.nombre,
                "variedad": var.nombre,
                **resumen,
                "unidad": "kg",
            })

        # También contemplamos movimientos sin variedad asignada.
        movimientos_sin_variedad = Movimiento.objects.filter(
            materia_prima=mp,
            variedad__isnull=True,
        )

        tiene_movimientos_sin_variedad = movimientos_sin_variedad.filter(
            fecha__lt=fecha_fin
        ).exists()

        if not variedades or tiene_movimientos_sin_variedad:
            resumen = _resumen_movimientos_informe(
                movimientos_sin_variedad,
                fecha_inicio,
                fecha_fin,
            )

            reporte.append({
                "nombre": mp.nombre,
                "variedad": "Sin variedad",
                **resumen,
                "unidad": "kg",
            })

    return reporte


# 4. Vista de Informes Mensuales (CU-07)
@login_required(login_url='login')
def generar_informe(request):
    hoy = timezone.now()
    mes_seleccionado = int(request.GET.get('mes', hoy.month))
    anio_seleccionado = int(request.GET.get('anio', hoy.year))

    reporte = _generar_reporte_mensual(
        mes_seleccionado,
        anio_seleccionado,
    )

    contexto = {
        'reporte': reporte,
        'mes_seleccionado': mes_seleccionado,
        'anio_seleccionado': anio_seleccionado,
        'anios': [hoy.year - 1, hoy.year, hoy.year + 1],
    }

    return render(request, 'inventario/informe.html', contexto)


# Exportar informe a CSV
@login_required(login_url='login')
def exportar_informe_csv(request):
    hoy = timezone.now()
    mes_seleccionado = int(request.GET.get('mes', hoy.month))
    anio_seleccionado = int(request.GET.get('anio', hoy.year))

    reporte = _generar_reporte_mensual(
        mes_seleccionado,
        anio_seleccionado,
    )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="Reporte_CAUQUEVA_'
        f'{mes_seleccionado}_{anio_seleccionado}.csv"'
    )

    # BOM para que Excel interprete correctamente los acentos.
    response.write('\ufeff'.encode('utf-8'))

    writer = csv.writer(response, delimiter=';')

    writer.writerow([
        'Producto',
        'Variedad',
        'Ingresos del Mes (kg)',
        'Consumos del Mes (kg)',
        'Stock al Cierre del Mes (kg)',
    ])

    for item in reporte:
        writer.writerow([
            item['nombre'],
            item['variedad'],
            f"{item['ingresos']:.2f}",
            f"{item['consumos']:.2f}",
            f"{item['stock_total']:.2f}",
        ])

    return response
