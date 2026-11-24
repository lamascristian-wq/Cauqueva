from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from inventario.models import (
    IngredienteReceta,
    MateriaPrima,
    MovimientoStock,
    Produccion,
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
        "email":"alamos@gmail.com",
        "materias": ["papa_andina", "maiz_amarillo"],
    },
    {
        "nombre": "Cooperativa Agrícola de Tilcara",
        "telefono": "388 4887716",
        "email":"tilcara@gmail.com",
        "materias": ["maiz_capia", "maiz_morado"],
    },
    {
        "nombre": "Comunidad Originaria de Purmamarca",
        "telefono": "388 4392058",
        "email":"purmamarca@gmail.com",
        "materias": ["quinoa", "maiz_morado"],
    },
    {
        "nombre": "Productores Unidos de Humahuaca",
        "telefono": "388 4670914",
        "email":"huamahuaca@gmail.com",
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

# ---------------------------------------------------------------------------
# Historial de ejemplo para darle vida a los gráficos y reportes
# ---------------------------------------------------------------------------

# Los datos históricos llevan esta marca en "observaciones" para no duplicarse
# si el comando se ejecuta más de una vez.
MARCA = "[Demo]"

# El stock inicial se fecha antes que todo el historial, así los reportes
# mensuales nunca muestran consumos en meses donde todavía no había stock.
DIAS_STOCK_INICIAL = 160

# Ingresos extra de materia prima (clave, Kg, hace cuántos días, observación)
INGRESOS_HISTORICOS = [
    ("papa_andina", Decimal("100"), 150, "Reposición de lote anterior"),
    ("maiz_amarillo", Decimal("80"), 80, "Ingreso por compra programada"),
    ("quinoa", Decimal("90"), 55, "Lote recibido de Purmamarca"),
    ("maiz_morado", Decimal("50"), 20, "Ingreso directo de cooperativa"),
]

# Producciones (= ventas). Cada una descuenta la materia prima de su receta,
# igual que cuando se registra desde la pantalla de Producción.
# (hace cuántos días, producto, unidades producidas, observación)
PRODUCCIONES_HISTORICAS = [
    (145, "Snacks de papa andina x100g", 450, "Lote snacks #101"),                 # 45 Kg de papa
    (140, "Harina de maíz amarillo x1kg", 30, "Molienda de harina"),               # 30 Kg de maíz amarillo
    (115, "Fideos de maíz capia x300g", 160, "Elaboración de fideos"),             # 48 Kg de capia
    (110, "Alfajores grandes de quinoa x150g (caja de 6 u.)", 230, "Alfajores"),   # 34,5 Kg de quinoa
    (105, "Palitos de maíz morado x100g", 250, "Extrusión de palitos"),            # 25 Kg de maíz morado
    (85, "Snacks de papa andina x100g", 700, "Producción intensiva de snacks"),    # 70 Kg de papa
    (75, "Harina de maíz amarillo x1kg", 60, "Molienda mensual"),                  # 60 Kg de maíz amarillo
    (50, "Alfajores grandes de quinoa x150g (caja de 6 u.)", 260, "Alfajores"),    # 39 Kg de quinoa
    (45, "Fideos de maíz capia x300g", 150, "Fideos lote #202"),                   # 45 Kg de capia
    (25, "Snacks de papa andina x100g", 800, "Lote mensual de snacks"),            # 80 Kg de papa
    (15, "Palitos de maíz morado x100g", 300, "Palitos morados"),                  # 30 Kg de maíz morado
    (5, "Snacks de papa andina x100g", 350, "Producción de la semana"),            # 35 Kg de papa
    (2, "Harina de maíz amarillo x1kg", 25, "Molienda reciente"),                  # 25 Kg de maíz amarillo
]


class Command(BaseCommand):
    help = (
        "Carga datos iniciales de CAUQUEVA: usuarios, 4 proveedores, 5 materias primas "
        "(con su stock inicial como ingresos), 6 productos con su receta y un historial "
        "de ingresos y producciones. Se puede ejecutar más de una vez sin duplicar datos."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--sin-stock",
            action="store_true",
            help="No cargar stock inicial ni historial (deja las materias primas en 0).",
        )

    @transaction.atomic
    def handle(self, *args, **opciones):
        campos_materia = {f.name for f in MateriaPrima._meta.get_fields()}
        campos_movimiento = {f.name for f in MovimientoStock._meta.get_fields()}
        ahora = timezone.now()

        nuevos = {
            "usuarios": 0,
            "proveedores": 0,
            "materias": 0,
            "stock_inicial": 0,
            "ingresos_hist": 0,
            "producciones_hist": 0,
            "productos": 0,
            "recetas": 0,
        }

        # 1. Usuarios (admin, gerente y operario)
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
            email_val = datos.get("email", "")
            telefono_val = datos.get("telefono", "")

            proveedor, creado = Proveedor.objects.get_or_create(
                nombre=datos["nombre"],
                defaults={
                    "telefono": telefono_val,
                    "email": email_val,  # <-- Se agrega el email en los defaults
                },
            )

            # Si el proveedor ya existía en la BDD pero no tenía email, lo actualiza
            if not creado:
                actualizar = False
                if email_val and not proveedor.email:
                    proveedor.email = email_val
                    actualizar = True
                if telefono_val and not proveedor.telefono:
                    proveedor.telefono = telefono_val
                    actualizar = True
                if actualizar:
                    proveedor.save()

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
                mov = MovimientoStock.objects.create(**ingreso)
                MovimientoStock.objects.filter(pk=mov.pk).update(
                    fecha=ahora - timedelta(days=DIAS_STOCK_INICIAL)
                )
                nuevos["stock_inicial"] += 1

        # 4. Qué materias primas provee cada proveedor
        for datos in PROVEEDORES:
            proveedores[datos["nombre"]].materias_primas.add(
                *[materias[clave] for clave in datos["materias"]]
            )

        # 5. Productos y recetas
        productos = {}
        for nombre, precio, receta in PRODUCTOS:
            producto, creado = Producto.objects.get_or_create(
                nombre=nombre, defaults={"precio": precio}
            )
            productos[nombre] = producto
            nuevos["productos"] += creado
            for clave, kg_por_unidad in receta:
                _, creada = IngredienteReceta.objects.get_or_create(
                    producto=producto,
                    materia_prima=materias[clave],
                    defaults={"cantidad_por_unidad": kg_por_unidad},
                )
                nuevos["recetas"] += creada

        # 6. Historial de ejemplo: ingresos y producciones repartidos en los últimos meses
        ya_cargado = (
            MovimientoStock.objects.filter(observaciones__startswith=MARCA).exists()
            or Produccion.objects.filter(observaciones__startswith=MARCA).exists()
        )
        if not opciones["sin_stock"] and not ya_cargado:
            # 6a. Primero todos los ingresos, así siempre hay stock para producir
            for clave, cantidad, dias, obs in INGRESOS_HISTORICOS:
                datos_ingreso = {
                    "materia_prima": materias[clave],
                    "proveedor": proveedores[MATERIAS_PRIMAS[clave]["proveedor"]],
                    "tipo": "INGRESO",
                    "cantidad": cantidad,
                    "observaciones": f"{MARCA} {obs}",
                }
                if "precio_unitario" in campos_movimiento:
                    datos_ingreso["precio_unitario"] = MATERIAS_PRIMAS[clave]["precio"]
                mov = MovimientoStock.objects.create(**datos_ingreso)
                MovimientoStock.objects.filter(pk=mov.pk).update(fecha=ahora - timedelta(days=dias))
                nuevos["ingresos_hist"] += 1

            # 6b. Producciones reales: crean la Produccion y sus consumos vinculados
            for dias, nombre_producto, unidades, obs in PRODUCCIONES_HISTORICAS:
                producto = productos[nombre_producto]
                fecha = ahora - timedelta(days=dias)
                prod = Produccion.registrar(
                    producto, unidades, fecha=fecha, observaciones=f"{MARCA} {obs}"
                )
                if not isinstance(prod, Produccion):
                    prod = Produccion.objects.filter(producto=producto).latest("id")
                # Aseguramos la fecha histórica en la producción y en sus consumos
                Produccion.objects.filter(pk=prod.pk).update(fecha=fecha)
                MovimientoStock.objects.filter(produccion=prod).update(fecha=fecha)
                nuevos["producciones_hist"] += 1

        self.stdout.write(self.style.SUCCESS(
            "Datos cargados: "
            f"{nuevos['usuarios']} usuarios, {nuevos['proveedores']} proveedores, "
            f"{nuevos['materias']} materias primas, {nuevos['stock_inicial']} ingresos de stock inicial, "
            f"{nuevos['productos']} productos, {nuevos['recetas']} ingredientes de receta, "
            f"{nuevos['ingresos_hist']} ingresos históricos y "
            f"{nuevos['producciones_hist']} producciones históricas."
        ))