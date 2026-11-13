from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class LoginRequeridoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            libres = [reverse("login"), "/admin/"]
            if not any(request.path.startswith(p) for p in libres):
                return redirect(f"{settings.LOGIN_URL}?next={request.path}")
        return self.get_response(request)