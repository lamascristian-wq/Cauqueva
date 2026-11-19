from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventario.models import MateriaPrima


MATERIAS_PRIMAS = (
    ("Papa", "Andina", "KG", "Papa andina para producción.", 50),
    ("Papa", "Morada", "KG", "Papa morada de cultivo regional.", 30),
    ("Papa", "Oca", "KG", "Oca andina para producción.", 25),
    ("Papa", "Verde", "KG", "Papa de variedad verde.", 20),
    ("Maíz", "Blanco", "KG", "Maíz blanco de grano seco.", 50),
    ("Maíz", "Amarillo", "KG", "Maíz amarillo de grano seco.", 50),
    ("Maíz", "Morado", "KG", "Maíz morado andino.", 30),
    ("Maíz", "Capia", "KG", "Maíz capia para preparaciones regionales.", 30),
    ("Quinoa", "Real", "KG", "Quinoa real seleccionada.", 50),
    ("Quinoa", "Blanca", "KG", "Quinoa blanca seleccionada.", 40),
    ("Quinoa", "Roja", "KG", "Quinoa roja seleccionada.", 30),
    ("Poroto", "Pallar", "KG", "Poroto pallar seco.", 50),
    ("Poroto", "Negro", "KG", "Poroto negro seco.", 40),
    ("Amaranto", "Grano", "KG", "Amaranto en grano.", 25),
)


class Command(BaseCommand):
    help = (
        "Reemplaza todas las materias primas por datos de demostracion CAUQUEVA. "
        "Tambien elimina sus movimientos asociados."
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
                "La carga está bloqueada porque DEBUG no está activado."
            )
        if not options["confirmar_entorno_demo"]:
            raise CommandError(
                "Este comando elimina todas las materias primas y sus movimientos. "
                "Ejecutalo en desarrollo con --confirmar-entorno-demo."
            )

        with transaction.atomic():
            eliminadas, _ = MateriaPrima.objects.all().delete()
            creadas = 0

            for nombre, variedad, unidad, descripcion, stock_minimo in MATERIAS_PRIMAS:
                materia = MateriaPrima.objects.create(
                    nombre=nombre,
                    variedad=variedad,
                    unidad_medida=unidad,
                    descripcion=descripcion,
                    stock_actual=Decimal("0"),
                    stock_minimo=Decimal(stock_minimo),
                )
                creadas += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Materia prima creada: {materia} (stock minimo: "
                        f"{materia.stock_minimo:g} {materia.get_unidad_medida_display()})"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Carga finalizada: {creadas} materias primas creadas; "
                f"{eliminadas} registros eliminados."
            )
        )
