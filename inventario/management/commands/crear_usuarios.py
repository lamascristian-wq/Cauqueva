from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from inventario.management.commands.cargar_datos import USUARIOS


class Command(BaseCommand):
    help = (
        "Crea solo los usuarios iniciales (admin, gerente y operario), sin cargar "
        "datos de ejemplo. Si un usuario ya existe, no lo modifica."
    )

    def handle(self, *args, **opciones):
        for datos in USUARIOS:
            user, creado = User.objects.get_or_create(
                username=datos["username"],
                defaults={
                    "email": datos["email"],
                    "first_name": datos["first_name"],
                    "last_name": datos["last_name"],
                    "is_staff": datos["is_staff"],
                    "is_superuser": datos["is_superuser"],
                },
            )
            if creado:
                user.set_password(datos["password"])
                user.save()
            estado = "creado" if creado else "ya existía"
            self.stdout.write(f"{datos['username']}: {estado}")
