from django.shortcuts import render, redirect, get_object_or_404
from .models import MateriaPrima
from .forms import MateriaPrimaForm

def panel_principal(request):
    lista_productos = MateriaPrima.objects.all()
    contexto = {'productos': lista_productos}
    return render(request, 'inventario/dashboard.html', contexto)

def registrar_producto(request):
    if request.method == 'POST':
        formulario = MateriaPrimaForm(request.POST)
        if formulario.is_valid():
            formulario.save()
            return redirect('dashboard')
    else:
        formulario = MateriaPrimaForm()
    return render(request, 'inventario/formulario.html', {'formulario': formulario})

# NUEVA VISTA: Para editar un producto existente
def editar_producto(request, id):
    # 1. Buscamos el producto exacto usando su número de identificación (ID)
    producto = get_object_or_404(MateriaPrima, id=id)
    
    if request.method == 'POST':
        # 2. Le pasamos los datos nuevos, pero le decimos que sobreescriba el producto existente (instance=producto)
        formulario = MateriaPrimaForm(request.POST, instance=producto)
        if formulario.is_valid():
            formulario.save()
            return redirect('dashboard')
    else:
        # 3. Si recién entra, cargamos el formulario lleno con los datos actuales del producto
        formulario = MateriaPrimaForm(instance=producto)

    # Reutilizamos el mismo diseño HTML
    contexto = {'formulario': formulario}
    return render(request, 'inventario/formulario.html', contexto)
# NUEVA VISTA: Para eliminar un producto
def eliminar_producto(request, id):
    # 1. Buscamos el producto que se quiere borrar
    producto = get_object_or_404(MateriaPrima, id=id)
    
    # 2. Si el usuario presiona el botón rojo de confirmación (POST)
    if request.method == 'POST':
        producto.delete()            # Lo borramos definitivamente de la base de datos
        return redirect('dashboard') # Lo devolvemos al inicio
    
    # 3. Si solo hizo clic en "Eliminar" desde la tabla, le mostramos la pantalla de confirmación
    contexto = {'producto': producto}
    return render(request, 'inventario/eliminar.html', contexto)