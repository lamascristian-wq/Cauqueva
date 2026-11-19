from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from inventario.models import MateriaPrima, MovimientoStock

DEMO_PREFIX = "DEMO - "
DEMO_OBSERVATION_PREFIX = "[DEMO CAUQUEVA]"

# Cada variedad tiene tres ingresos y tres consumos, ordenados por antigüedad.
PRODUCTS = (
    {
        "name": "Papa andina",
        "minimum": Decimal("40"),
        "varieties": (
            ("Morada", (120, 40, 25, 15, 10, 5)),
            ("Colorada", (45, 25, 10, 15, 10, 10)),
            ("Amarilla", (100, 35, 20, 15, 10, 5)),
        ),
    },
    {
        "name": "Maíz",
        "minimum": Decimal("25"),
        "varieties": (
            ("Amarillo", (80, 30, 15, 10, 10, 5)),
            ("Blanco", (35, 10, 5, 15, 10, 5)),
        ),
    },
    {
        "name": "Poroto",
        "minimum": Decimal("20"),
        "varieties": (
            ("Pallar", (20, 10, 5, 10, 8, 2)),
        ),
    },
)
MOVEMENT_DAYS_AGO = (175, 145, 115, 85, 55, 5)


class Command(BaseCommand):
    help = (
        "Agrega productos y movimientos ficticios para probar CAUQUEVA. "
        "Solo usar en una base de desarrollo."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmar-entorno-demo",
            action="store_true",
            help="Confirma que esta base es de desarrollo y puede recibir datos ficticios.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "La carga demo está bloqueada porque DEBUG no está activado."
            )
        if not options["confirmar_entorno_demo"]:
            raise CommandError(
                "Para proteger los datos existentes, ejecutá este comando solo en "
                "desarrollo y agregá --confirmar-entorno-demo."
            )

        with transaction.atomic():
            if self._check_existing_demo_data():
                self.stdout.write(
                    self.style.WARNING(
                        "Los datos demo ya están cargados. No se creó ningún registro nuevo."
                    )
                )
                return

            products_created = 0
            movements_created = 0
            now = timezone.now()

            for product_data in PRODUCTS:
                for variety_name, quantities in product_data["varieties"]:
                    # Se crea un registro de MateriaPrima por cada variedad en la nueva estructura
                    product = MateriaPrima.objects.create(
                        nombre=f"{DEMO_PREFIX}{product_data['name']}",
                        variedad=variety_name,
                        unidad_medida="KG",
                        descripcion="Datos ficticios de demostración; no son datos de producción.",
                        stock_minimo=product_data["minimum"],
                        stock_actual=Decimal("0.00")
                    )
                    products_created += 1

                    for index, quantity in enumerate(quantities):
                        movement_name = "INGRESO" if index < 3 else "CONSUMO"
                        movement_date = now - timedelta(
                            days=MOVEMENT_DAYS_AGO[index]
                        )
                        
                        mov = MovimientoStock(
                            materia_prima=product,
                            tipo=movement_name,
                            cantidad=Decimal(quantity),
                            observaciones=(
                                f"{DEMO_OBSERVATION_PREFIX} "
                                f"{movement_name.capitalize()} ficticio para probar "
                                f"el stock de {product_data['name']} {variety_name}."
                            ),
                        )
                        mov.save() # Calcula el stock automáticamente según la lógica del modelo
                        
                        # Actualizamos la fecha post-save para evitar que timezone.now() la sobrescriba
                        MovimientoStock.objects.filter(pk=mov.pk).update(fecha=movement_date)
                        movements_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Datos demo creados: "
                f"{products_created} materias primas (incluyendo variedades) y "
                f"{movements_created} movimientos. "
                "El stock actual se calculó automáticamente."
            )
        )

    def _check_existing_demo_data(self):
        expected_names = [f"{DEMO_PREFIX}{product['name']}" for product in PRODUCTS]
        existing_products = MateriaPrima.objects.filter(nombre__in=expected_names)
        existing_movements = MovimientoStock.objects.filter(
            observaciones__startswith=DEMO_OBSERVATION_PREFIX
        )

        if not existing_products.exists() and not existing_movements.exists():
            return False

        if existing_products.exists() or existing_movements.exists():
            raise CommandError(
                "Se encontraron registros con nombres u observaciones reservados para "
                "la demo. Para evitar duplicados, no se modificó ningún dato."
            )
        
        return True