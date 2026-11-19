import random
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventario.models import MateriaPrima


MATERIAS_PRIMAS_DEMO = (
    ("Papa", "Andina", "KG", "Papa andina para producción."),
    ("Papa", "Morada", "KG", "Papa morada de cultivo regional."),
    ("Maíz", "Amarillo", "KG", "Maíz amarillo de grano seco."),
    ("Maíz", "Blanco", "KG", "Maíz blanco de grano seco."),
    ("Quinoa", "Real", "KG", "Quinoa seleccionada."),
    ("Apio", "Verde", "KG", "Apio fresco."),
    ("Zanahoria", "Nantes", "KG", "Zanahoria fresca."),
    ("Cebolla", "Morada", "KG", "Cebolla morada."),
    ("Tomate", "Perita", "KG", "Tomate variedad perita."),
    ("Zapallo", "Anco", "KG", "Zapallo anco."),
    ("Poroto", "Pallar", "KG", "Poroto pallar seco."),
    ("Pimiento", "Morrón", "UN", "Pimiento morrón fresco."),
)


class Command(BaseCommand):
    help = (
        "Reemplaza todas las materias primas por datos ficticios de demostración. "
        "También elimina sus movimientos asociados."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmar-entorno-demo",
            action="store_true",
            help="Confirma que esta base puede borrar materias primas y movimientos asociados.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "La carga demo está bloqueada porque DEBUG no está activado."
            )
        if not options["confirmar_entorno_demo"]:
            raise CommandError(
                "Este comando elimina todas las materias primas y sus movimientos. "
                "Ejecutalo en desarrollo con --confirmar-entorno-demo."
            )

        with transaction.atomic():
            eliminadas, _ = MateriaPrima.objects.all().delete()
            creadas = 0

            for nombre, variedad, unidad, descripcion in MATERIAS_PRIMAS_DEMO:
                materia = MateriaPrima.objects.create(
                    nombre=nombre,
                    variedad=variedad,
                    unidad_medida=unidad,
                    descripcion=descripcion,
                    stock_actual=Decimal("0"),
                    stock_minimo=Decimal(random.randint(10, 50)),
                )
                creadas += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Materia prima creada: {materia} "
                        f"(mínimo: {materia.stock_minimo:g} {materia.get_unidad_medida_display()})"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Carga completada: {creadas} materias primas creadas; "
                f"{eliminadas} registros eliminados."
            )
        )
