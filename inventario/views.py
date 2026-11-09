from django.shortcuts import render, redirect
from .models import MateriaPrima
from .forms import MateriaPrimaForm # 1. Importamos el formulario que acabamos de crear

# Tu vista anterior (no la cambiamos)
def panel_principal(request):
    lista_productos = MateriaPrima.objects.all()
    contexto = {'productos': lista_productos}
    return render(request, 'inventario/dashboard.html', contexto)

# 2. NUEVA VISTA: Para registrar productos
def registrar_producto(request):
    # Si el usuario presionó el botón de guardar (envió datos)
    if request.method == 'POST':
        formulario = MateriaPrimaForm(request.POST)
        if formulario.is_valid(): # Si no puso letras donde van números, etc.
            formulario.save()     # Guarda en la base de datos
            return redirect('dashboard') # Lo devuelve a la pantalla principal
    
    # Si el usuario recién entra a la pantalla (solo quiere ver el formulario vacío)
    else:
        formulario = MateriaPrimaForm()

    # Enviamos el formulario al diseño HTML
    contexto = {'formulario': formulario}
    return render(request, 'inventario/formulario.html', contexto)