from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from inventario.models import MateriaPrima, MovimientoStock, Proveedor


MATERIAS_PRIMAS = (
    {
        "nombre": "Papa",
        "variedad": "Andina",
        "unidad": "KG",
        "descripcion": "Papa andina para producción y comercialización.",
        "minimo": 50,
        "ingreso": 180,
        "consumo": 35,
        "proveedor": "Cooperativa Cauqueva Ltda.",
    },
    {
        "nombre": "Papa",
        "variedad": "Morada",
        "unidad": "KG",
        "descripcion": "Papa morada de cultivo regional.",
        "minimo": 30,
        "ingreso": 100,
        "consumo": 80,
        "proveedor": "Finca Los Álamos",
    },
    {
        "nombre": "Maíz",
        "variedad": "Blanco",
        "unidad": "KG",
        "descripcion": "Maíz blanco de grano seco.",
        "minimo": 50,
        "ingreso": 250,
        "consumo": 40,
        "proveedor": "Cooperativa Cauqueva Ltda.",
    },
    {
        "nombre": "Maíz",
        "variedad": "Amarillo",
        "unidad": "KG",
        "descripcion": "Maíz amarillo de grano seco.",
        "minimo": 50,
        "ingreso": 160,
        "consumo": 115,
        "proveedor": "Productores del Interfluvio",
    },
    {
        "nombre": "Quinoa",
        "variedad": "Real",
        "unidad": "KG",
        "descripcion": "Quinoa real seleccionada de los valles andinos.",
        "minimo": 40,
        "ingreso": 120,
        "consumo": 25,
        "proveedor": "Agroandina S.R.L.",
    },
    {
        "nombre": "Quinoa",
        "variedad": "Blanca",
        "unidad": "KG",
        "descripcion": "Quinoa blanca seleccionada.",
        "minimo": 35,
        "ingreso": 110,
        "consumo": 20,
        "proveedor": "Cooperativa Cauqueva Ltda.",
    },
    {
        "nombre": "Oca",
        "variedad": "Andina",
        "unidad": "KG",
        "descripcion": "Tubérculo andino fresco.",
        "minimo": 25,
        "ingreso": 90,
        "consumo": 70,
        "proveedor": "Feria de Purmamarca",
    },
    {
        "nombre": "Amaranto",
        "variedad": "Grano",
        "unidad": "KG",
        "descripcion": "Amaranto en grano para elaboración de alimentos.",
        "minimo": 20,
        "ingreso": 75,
        "consumo": 10,
        "proveedor": "Agroandina S.R.L.",
    },
    {
        "nombre": "Poroto",
        "variedad": "Pallar",
        "unidad": "KG",
        "descripcion": "Poroto pallar seco.",
        "minimo": 40,
        "ingreso": 140,
        "consumo": 100,
        "proveedor": "Productores del Interfluvio",
    },
    {
        "nombre": "Poroto",
        "variedad": "Negro",
        "unidad": "KG",
        "descripcion": "Poroto negro seco.",
        "minimo": 30,
        "ingreso": 100,
        "consumo": 0,
        "proveedor": "Productores del Interfluvio",
    },
    {
        "nombre": "Zapallo",
        "variedad": "Anco",
        "unidad": "KG",
        "descripcion": "Zapallo anco fresco.",
        "minimo": 30,
        "ingreso": 110,
        "consumo": 20,
        "proveedor": "Feria de Purmamarca",
    },
    {
        "nombre": "Cebolla",
        "variedad": "Morada",
        "unidad": "KG",
        "descripcion": "Cebolla morada para consumo y elaboración.",
        "minimo": 40,
        "ingreso": 160,
        "consumo": 130,
        "proveedor": "Finca Los Álamos",
    },
    {
        "nombre": "Zanahoria",
        "variedad": "Andina",
        "unidad": "KG",
        "descripcion": "Zanahoria fresca de producción regional.",
        "minimo": 30,
        "ingreso": 100,
        "consumo": 15,
        "proveedor": "Finca Los Álamos",
    },
)

PROVEEDORES = (
    (
        "Cooperativa Cauqueva Ltda.",
        "388 000 1001",
        (("Papa", "Andina"), ("Maíz", "Blanco"), ("Quinoa", "Blanca"), ("Quinoa", "Real")),
    ),
    (
        "Finca Los Álamos",
        "388 000 1002",
        (("Papa", "Morada"), ("Cebolla", "Morada"), ("Zanahoria", "Andina")),
    ),
    (
        "Productores del Interfluvio",
        "388 000 1003",
        (("Maíz", "Amarillo"), ("Poroto", "Pallar"), ("Poroto", "Negro")),
    ),
    (
        "Agroandina S.R.L.",
        "388 000 1004",
        (("Quinoa", "Real"), ("Amaranto", "Grano")),
    ),
    (
        "Feria de Purmamarca",
        "388 000 1005",
        (("Oca", "Andina"), ("Zapallo", "Anco"), ("Papa", "Morada")),
    ),
)


class Command(BaseCommand):
    help = (
        "Reemplaza materias primas, proveedores y movimientos por datos de "
        "demostración relacionados entre sí."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--forzar",
            action="store_true",
            help="Confirma el borrado de los datos existentes en la base de desarrollo.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "La carga está bloqueada porque DEBUG no está activado."
            )
        if not options["forzar"]:
            raise CommandError(
                "Este comando elimina movimientos, proveedores y materias primas. "
                "Ejecutalo en desarrollo con --forzar."
            )

        ahora = timezone.now()
        with transaction.atomic():
            movimientos_eliminados, _ = MovimientoStock.objects.all().delete()
            proveedores_eliminados, _ = Proveedor.objects.all().delete()
            materias_eliminadas, _ = MateriaPrima.objects.all().delete()

            materias_por_clave = {}
            for datos in MATERIAS_PRIMAS:
                clave = (datos["nombre"], datos["variedad"])
                materia = MateriaPrima.objects.create(
                    nombre=datos["nombre"],
                    variedad=datos["variedad"],
                    unidad_medida=datos["unidad"],
                    descripcion=datos["descripcion"],
                    stock_actual=Decimal("0"),
                    stock_minimo=Decimal(datos["minimo"]),
                )
                materias_por_clave[clave] = materia

            proveedores_por_nombre = {}
            for nombre, telefono, claves_materias in PROVEEDORES:
                proveedor = Proveedor.objects.create(
                    nombre=nombre,
                    telefono=telefono,
                )
                proveedor.materias_primas.add(
                    *(materias_por_clave[clave] for clave in claves_materias)
                )
                proveedores_por_nombre[nombre] = proveedor

            movimientos_creados = 0
            for indice, datos in enumerate(MATERIAS_PRIMAS):
                materia = materias_por_clave[(datos["nombre"], datos["variedad"])]
                proveedor = proveedores_por_nombre[datos["proveedor"]]
                MovimientoStock.objects.create(
                    materia_prima=materia,
                    proveedor=proveedor,
                    tipo="INGRESO",
                    cantidad=Decimal(datos["ingreso"]),
                    fecha=ahora - timedelta(days=45 - (indice % 20)),
                    observaciones="Ingreso histórico ficticio para datos de demostración.",
                )
                movimientos_creados += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Ingreso creado: {materia} ({datos['ingreso']} "
                        f"{materia.get_unidad_medida_display()}) de {proveedor.nombre}."
                    )
                )

            consumos_creados = 0
            for indice, datos in enumerate(MATERIAS_PRIMAS):
                if not datos["consumo"]:
                    continue
                materia = materias_por_clave[(datos["nombre"], datos["variedad"])]
                MovimientoStock.objects.create(
                    materia_prima=materia,
                    proveedor=None,
                    tipo="CONSUMO",
                    cantidad=Decimal(datos["consumo"]),
                    fecha=ahora - timedelta(days=1 + (indice % 10)),
                    observaciones="Consumo reciente ficticio para datos de demostración.",
                )
                consumos_creados += 1
                movimientos_creados += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Carga completa: "
                f"{len(PROVEEDORES)} proveedores, "
                f"{len(MATERIAS_PRIMAS)} materias primas y "
                f"{movimientos_creados} movimientos "
                f"({len(MATERIAS_PRIMAS)} ingresos y {consumos_creados} consumos)."
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "Registros anteriores eliminados: "
                f"{proveedores_eliminados} proveedores, "
                f"{materias_eliminadas} materias primas y "
                f"{movimientos_eliminados} movimientos."
            )
        )
