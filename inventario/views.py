from django.shortcuts import render, redirect, get_object_or_404
from .models import MateriaPrima, Movimiento
from .forms import MovimientoForm

def panel_principal(request):
    materias_primas = MateriaPrima.objects.filter(activo=True)
    resumen = []
    for mp in materias_primas:
        variedades = mp.variedad_set.filter(activo=True)
        if variedades.exists():
            for var in variedades:
                movimientos = Movimiento.objects.filter(materia_prima=mp, variedad=var)
                stock = sum(m.cantidad_kg * m.efecto_stock for m in movimientos)
                resumen.append({
                    'id_materia': mp.id, # NUEVO: Enviamos el ID para el botón
                    'nombre': mp.nombre,
                    'variedad': var.nombre,
                    'stock': stock,
                    'unidad': 'kg'
                })
        else:
            movimientos = Movimiento.objects.filter(materia_prima=mp, variedad__isnull=True)
            stock = sum(m.cantidad_kg * m.efecto_stock for m in movimientos)
            resumen.append({
                'id_materia': mp.id, # NUEVO: Enviamos el ID para el botón
                'nombre': mp.nombre,
                'variedad': 'Sin variedad',
                'stock': stock,
                'unidad': 'kg'
            })
    return render(request, 'inventario/dashboard.html', {'productos': resumen})

def registrar_producto(request):
    if request.method == 'POST':
        formulario = MovimientoForm(request.POST)
        if formulario.is_valid():
            formulario.save()
            return redirect('dashboard')
    else:
        formulario = MovimientoForm()
    return render(request, 'inventario/formulario.html', {'formulario': formulario})

# NUEVA VISTA: Mostrará la lista de movimientos de un producto específico
def historial_producto(request, id):
    materia = get_object_or_404(MateriaPrima, id=id)
    # Buscamos todos los movimientos de esta materia prima (Django los ordenará por fecha automáticamente gracias al modelo)
    movimientos = Movimiento.objects.filter(materia_prima=materia)
    return render(request, 'inventario/historial.html', {'materia': materia, 'movimientos': movimientos})