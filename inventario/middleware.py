
from urllib.parse import urlencode

from django.shortcuts import redirect
from django.urls import reverse


class LoginRequeridoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            login_path = reverse("login")

            # Comparamos las rutas ignorando la barra final.
            ruta_actual = request.path_info.rstrip("/") or "/"
            ruta_login = login_path.rstrip("/") or "/"

            es_login = ruta_actual == ruta_login
            es_admin = request.path_info.startswith("/admin/")

            if not es_login and not es_admin:
                parametros = urlencode({
                    "next": request.get_full_path()
                })
                return redirect(f"{login_path}?{parametros}")

        return self.get_response(request)
