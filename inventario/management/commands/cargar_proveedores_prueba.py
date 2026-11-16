import random

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventario.models import MateriaPrima, Proveedor


PROVEEDORES_DE_PRUEBA = (
    ("Finca El Sol", "388 000 0001"),
    ("Cooperativa Norte", "388 000 0002"),
    ("Productor Independiente", "388 000 0003"),
    ("Huerta Quebrada de Humahuaca", "388 000 0004"),
    ("Asociación de Productores del Valle", "388 000 0005"),
)


class Command(BaseCommand):
    help = "Reemplaza los proveedores existentes por proveedores ficticios de prueba."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmar-entorno-demo",
            action="store_true",
            help="Confirma que esta base de desarrollo puede reemplazar sus proveedores.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "La carga de proveedores de prueba está bloqueada porque DEBUG no está activado."
            )
        if not options["confirmar_entorno_demo"]:
            raise CommandError(
                "Este comando elimina todos los proveedores existentes. "
                "Ejecutalo en desarrollo con --confirmar-entorno-demo."
            )

        materias_primas = list(MateriaPrima.objects.all())
        if not materias_primas:
            raise CommandError(
                "No hay materias primas para asignar. No se eliminó ningún proveedor."
            )

        with transaction.atomic():
            Proveedor.objects.all().delete()

            for nombre, telefono in PROVEEDORES_DE_PRUEBA:
                proveedor = Proveedor.objects.create(
                    nombre=nombre,
                    telefono=telefono,
                )
                cantidad = random.randint(1, min(3, len(materias_primas)))
                proveedor.materias_primas.add(
                    *random.sample(materias_primas, cantidad)
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Proveedor creado: {proveedor.nombre} ({proveedor.telefono}); "
                        f"{cantidad} materias primas asignadas."
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Carga completada: {len(PROVEEDORES_DE_PRUEBA)} proveedores de prueba."
            )
        )
