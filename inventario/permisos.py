from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

GERENTE = "Gerente"
INVENTARIO = "Inventario"

# Qué grupos pueden entrar a cada sección. Acá se cambia quién ve qué.
PERMISOS = {
    "panel": {GERENTE},
    "materias_primas": {GERENTE, INVENTARIO},
    "ingresos": {GERENTE, INVENTARIO},
    "consumos": {GERENTE, INVENTARIO},
    "proveedores": {GERENTE},
    "historial": {GERENTE},
    "reportes": {GERENTE},
}

# Adónde se manda a cada persona al iniciar sesión (primera sección que pueda ver)
PORTADA = [
    ("panel", "panelprincipal"),
    ("materias_primas", "inventariostock"),
    ("consumos", "consumos"),
]


def puede(user, seccion):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    grupos = set(user.groups.values_list("name", flat=True))
    return bool(grupos & PERMISOS.get(seccion, set()))


def seccion_requerida(seccion):
    """Reemplaza a @login_required: pide sesión y además permiso para la sección."""
    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not puede(request.user, seccion):
                raise PermissionDenied
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador


def menu_permisos(request):
    """Deja disponible `puede.<seccion>` en todos los templates."""
    return {"puede": {s: puede(request.user, s) for s in PERMISOS}}