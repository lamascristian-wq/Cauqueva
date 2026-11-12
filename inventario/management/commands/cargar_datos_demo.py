from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from inventario.models import (
    MateriaPrima,
    Movimiento,
    TipoMovimiento,
    UnidadMedida,
    Variedad,
)


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

            unit, unit_created = self._get_unit()
            income_type, income_type_created = self._get_movement_type(
                "ingreso", 1
            )
            consumption_type, consumption_type_created = self._get_movement_type(
                "consumo", -1
            )
            movement_types = {
                "ingreso": income_type,
                "consumo": consumption_type,
            }

            products_created = 0
            varieties_created = 0
            movements_created = 0
            now = timezone.now()

            for product_data in PRODUCTS:
                product = MateriaPrima.objects.create(
                    nombre=f"{DEMO_PREFIX}{product_data['name']}",
                    descripcion="Datos ficticios de demostración; no son datos de producción.",
                    stock_minimo=product_data["minimum"],
                )
                products_created += 1

                for variety_name, quantities in product_data["varieties"]:
                    variety = Variedad.objects.create(
                        materia_prima=product,
                        nombre=variety_name,
                    )
                    varieties_created += 1

                    for index, quantity in enumerate(quantities):
                        movement_name = "ingreso" if index < 3 else "consumo"
                        movement_type = movement_types[movement_name]
                        movement_date = now - timedelta(
                            days=MOVEMENT_DAYS_AGO[index]
                        )
                        Movimiento.objects.create(
                            materia_prima=product,
                            variedad=variety,
                            unidad=unit,
                            tipo=movement_type,
                            usuario_registro="DEMO CAUQUEVA",
                            cantidad=Decimal(quantity),
                            fecha=movement_date,
                            observacion=(
                                f"{DEMO_OBSERVATION_PREFIX} "
                                f"{movement_name.capitalize()} ficticio para probar "
                                f"el stock de {product_data['name']} {variety_name}."
                            ),
                        )
                        movements_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Datos demo creados: "
                f"{products_created} productos, "
                f"{varieties_created} variedades y "
                f"{movements_created} movimientos. "
                "Registros auxiliares creados: "
                f"{int(unit_created)} unidades de medida y "
                f"{int(income_type_created) + int(consumption_type_created)} "
                "tipos de movimiento."
            )
        )

    def _check_existing_demo_data(self):
        expected_varieties = {
            f"{DEMO_PREFIX}{product['name']}": {
                variety_name for variety_name, _ in product["varieties"]
            }
            for product in PRODUCTS
        }
        product_names = list(expected_varieties)
        existing_products = MateriaPrima.objects.filter(nombre__in=product_names)
        existing_movements = Movimiento.objects.filter(
            observacion__startswith=DEMO_OBSERVATION_PREFIX
        )

        if not existing_products.exists() and not existing_movements.exists():
            return False

        existing_products_by_name = {
            product.nombre: product for product in existing_products
        }
        if set(existing_products_by_name) == set(expected_varieties):
            complete = True
            for product_name, variety_names in expected_varieties.items():
                product = existing_products_by_name[product_name]
                actual_varieties = set(
                    Variedad.objects.filter(materia_prima=product).values_list(
                        "nombre",
                        flat=True,
                    )
                )
                demo_movements = existing_movements.filter(
                    materia_prima=product
                )
                if (
                    actual_varieties != variety_names
                    or demo_movements.count() != len(variety_names) * 6
                ):
                    complete = False
                    break

            if complete and existing_movements.count() == sum(
                len(names) * 6 for names in expected_varieties.values()
            ):
                return True

        raise CommandError(
            "Se encontraron registros con nombres u observaciones reservados para "
            "la demo, pero la carga está incompleta. No se modificó ningún dato."
        )

    @staticmethod
    def _get_unit():
        # Reutiliza el catálogo existente sin cambiar sus registros.
        unit, created = UnidadMedida.objects.get_or_create(
            simbolo="kg",
            defaults={
                "nombre": "kilogramo",
                "factor_kg": Decimal("1"),
            },
        )
        if unit.factor_kg != Decimal("1"):
            raise CommandError(
                "La unidad kg existente no equivale a un kilogramo. "
                "No se crearon datos demo."
            )
        return unit, created

    @staticmethod
    def _get_movement_type(name, effect):
        movement_type, created = TipoMovimiento.objects.get_or_create(
            nombre=name,
            defaults={"efecto_predeterminado": effect},
        )
        if movement_type.efecto_predeterminado != effect:
            raise CommandError(
                f"El tipo de movimiento «{name}» tiene un efecto incompatible. "
                "No se crearon datos demo."
            )
        return movement_type, created
