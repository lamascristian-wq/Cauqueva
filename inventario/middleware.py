
from urllib.parse import urlencode

from django.shortcuts import redirect
from django.urls import reverse

    
class LoginRequeridoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Si el usuario NO está logueado
        if not request.user.is_authenticated:
            # Y está intentando entrar a cualquier lugar que NO sea el login
            if not request.path.startswith('/login'):
                return redirect('login') # Lo mandamos al login
        
        response = self.get_response(request)
        return response