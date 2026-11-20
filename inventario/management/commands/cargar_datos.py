from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from inventario.models import (
    IngredienteReceta,
    MateriaPrima,
    MovimientoStock,
    Producto,
    Proveedor,
)

# ---------------------------------------------------------------------------
# Datos de ejemplo (los teléfonos y nombres de proveedores son inventados)
# ---------------------------------------------------------------------------

USUARIOS = [
    {
        "username": "admin",
        "email": "admin@cauqueva.org",
        "password": "admin123",
        "is_staff": True,
        "is_superuser": True,
        "first_name": "Administrador",
        "last_name": "General",
    },
    {
        "username": "gerente",
        "email": "gerente@cauqueva.org",
        "password": "gerente123",
        "is_staff": True,
        "is_superuser": False,
        "first_name": "Gerente",
        "last_name": "Producción",
    },
    {
        "username": "operario",
        "email": "operario@cauqueva.org",
        "password": "operario123",
        "is_staff": False,
        "is_superuser": False,
        "first_name": "Operario",
        "last_name": "Planta",
    },
]

PROVEEDORES = [
    {
        "nombre": "Finca Los Álamos",
        "telefono": "388 4561203",
        "materias": ["papa_andina", "maiz_amarillo"],
    },
    {
        "nombre": "Cooperativa Agrícola de Tilcara",
        "telefono": "388 4887716",
        "materias": ["maiz_capia", "maiz_morado"],
    },
    {
        "nombre": "Comunidad Originaria de Purmamarca",
        "telefono": "388 4392058",
        "materias": ["quinoa", "maiz_morado"],
    },
    {
        "nombre": "Productores Unidos de Humahuaca",
        "telefono": "388 4670914",
        "materias": ["papa_andina", "quinoa", "maiz_capia"],
    },
]

# precio = $ por Kg pagado en el ingreso inicial (y precio de referencia, si el modelo lo tiene)
# stock = Kg que ingresan al cargar los datos
# proveedor = quién entregó ese stock inicial
MATERIAS_PRIMAS = {
    "papa_andina": {
        "nombre": "Papa", "variedad": "Andina", "descripcion": "Papa andina para snacks",
        "precio": Decimal("2500"), "stock": Decimal("300"), "stock_minimo": Decimal("50"),
        "proveedor": "Finca Los Álamos",
    },
    "maiz_amarillo": {
        "nombre": "Maíz", "variedad": "Amarillo", "descripcion": "Maíz amarillo para harina",
        "precio": Decimal("1500"), "stock": Decimal("200"), "stock_minimo": Decimal("50"),
        "proveedor": "Finca Los Álamos",
    },
    "maiz_capia": {
        "nombre": "Maíz", "variedad": "Capia", "descripcion": "Maíz capia para fideos y galletas",
        "precio": Decimal("4000"), "stock": Decimal("200"), "stock_minimo": Decimal("50"),
        "proveedor": "Cooperativa Agrícola de Tilcara",
    },
    "maiz_morado": {
        "nombre": "Maíz", "variedad": "Morado", "descripcion": "Maíz morado para palitos",
        "precio": Decimal("3000"), "stock": Decimal("150"), "stock_minimo": Decimal("50"),
        "proveedor": "Cooperativa Agrícola de Tilcara",
    },
    "quinoa": {
        "nombre": "Quinoa", "variedad": None, "descripcion": "Quinoa para alfajores",
        "precio": Decimal("5000"), "stock": Decimal("200"), "stock_minimo": Decimal("50"),
        "proveedor": "Comunidad Originaria de Purmamarca",
    },
}

# (nombre, precio de venta por unidad, receta: [(materia prima, Kg por unidad)])
PRODUCTOS = [
    ("Snacks de papa andina x100g", Decimal("6100"), [("papa_andina", Decimal("0.100"))]),
    ("Harina de maíz amarillo x1kg", Decimal("7980"), [("maiz_amarillo", Decimal("1.000"))]),
    ("Alfajores grandes de quinoa x150g (caja de 6 u.)", Decimal("16130"), [("quinoa", Decimal("0.150"))]),
    ("Fideos de maíz capia x300g", Decimal("7080"), [("maiz_capia", Decimal("0.300"))]),
    ("Galletas de maíz capia x100g", Decimal("3650"), [("maiz_capia", Decimal("0.100"))]),
    ("Palitos de maíz morado x100g", Decimal("5450"), [("maiz_morado", Decimal("0.100"))]),
]


class Command(BaseCommand):
    help = (
        "Carga datos iniciales de CAUQUEVA: 4 proveedores, 5 materias primas "
        "(con su stock inicial como ingresos) y 6 productos con su receta. "
        "Se puede ejecutar más de una vez sin duplicar datos."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--sin-stock",
            action="store_true",
            help="No cargar el stock inicial (deja las materias primas en 0).",
        )

    @transaction.atomic
    def handle(self, *args, **opciones):
        campos_materia = {f.name for f in MateriaPrima._meta.get_fields()}
        campos_movimiento = {f.name for f in MovimientoStock._meta.get_fields()}
        nuevos = {"proveedores": 0, "materias": 0, "ingresos": 0, "productos": 0, "recetas": 0}

        # 1. Usuarios (Admin, Gerente u Operario)
        for datos_u in USUARIOS:
            user, creado = User.objects.get_or_create(
                username=datos_u["username"],
                defaults={
                    "email": datos_u["email"],
                    "first_name": datos_u["first_name"],
                    "last_name": datos_u["last_name"],
                    "is_staff": datos_u["is_staff"],
                    "is_superuser": datos_u["is_superuser"],
                },
            )
            if creado:
                user.set_password(datos_u["password"])
                user.save()
                nuevos["usuarios"] += 1

        # 2. Proveedores
        proveedores = {}
        for datos in PROVEEDORES:
            proveedor, creado = Proveedor.objects.get_or_create(
                nombre=datos["nombre"], defaults={"telefono": datos["telefono"]}
            )
            proveedores[proveedor.nombre] = proveedor
            nuevos["proveedores"] += creado

        # 3. Materias primas (y su stock inicial como un ingreso, para que el historial cuadre)
        materias = {}
        for clave, d in MATERIAS_PRIMAS.items():
            defaults = {
                "unidad_medida": "KG",
                "descripcion": d["descripcion"],
                "stock_minimo": d["stock_minimo"],
            }
            if "precio_referencia" in campos_materia:
                defaults["precio_referencia"] = d["precio"]

            materia, creada = MateriaPrima.objects.get_or_create(
                nombre=d["nombre"], variedad=d["variedad"], defaults=defaults
            )
            materias[clave] = materia
            nuevos["materias"] += creada

            if not opciones["sin_stock"] and not materia.movimientostock_set.exists():
                ingreso = {
                    "materia_prima": materia,
                    "proveedor": proveedores[d["proveedor"]],
                    "tipo": "INGRESO",
                    "cantidad": d["stock"],
                    "observaciones": "Stock inicial (datos de ejemplo)",
                }
                if "precio_unitario" in campos_movimiento:
                    ingreso["precio_unitario"] = d["precio"]
                # El save() del movimiento suma la cantidad al stock automáticamente
                MovimientoStock.objects.create(**ingreso)
                nuevos["ingresos"] += 1

        # 4. Qué materias primas provee cada proveedor
        for datos in PROVEEDORES:
            proveedores[datos["nombre"]].materias_primas.add(
                *[materias[clave] for clave in datos["materias"]]
            )

        # 5. Productos y recetas
        for nombre, precio, receta in PRODUCTOS:
            producto, creado = Producto.objects.get_or_create(
                nombre=nombre, defaults={"precio": precio}
            )
            nuevos["productos"] += creado
            for clave, kg_por_unidad in receta:
                _, creada = IngredienteReceta.objects.get_or_create(
                    producto=producto,
                    materia_prima=materias[clave],
                    defaults={"cantidad_por_unidad": kg_por_unidad},
                )
                nuevos["recetas"] += creada

        self.stdout.write(self.style.SUCCESS(
            "Datos cargados: "
            f"{nuevos['proveedores']} proveedores, {nuevos['materias']} materias primas, "
            f"{nuevos['ingresos']} ingresos de stock inicial, {nuevos['productos']} productos, "
            f"{nuevos['recetas']} ingredientes de receta."
        ))