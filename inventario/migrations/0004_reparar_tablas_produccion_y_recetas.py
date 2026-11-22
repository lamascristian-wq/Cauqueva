
from django.db import migrations


def reparar_esquema_inventario(apps, schema_editor):
    conexion = schema_editor.connection

    modelos_a_crear = [
        "Producto",
        "IngredienteReceta",
        "Produccion",
    ]

    tablas_existentes = set(
        conexion.introspection.table_names()
    )

    # Crear las tablas que faltan, respetando las relaciones.
    for nombre_modelo in modelos_a_crear:
        modelo = apps.get_model("inventario", nombre_modelo)
        tabla = modelo._meta.db_table

        if tabla not in tablas_existentes:
            schema_editor.create_model(modelo)
            tablas_existentes.add(tabla)

    # Agregar la relación Produccion a MovimientoStock si falta.
    MovimientoStock = apps.get_model(
        "inventario",
        "MovimientoStock",
    )

    tabla_movimientos = MovimientoStock._meta.db_table
    campo_produccion = MovimientoStock._meta.get_field(
        "produccion"
    )

    with conexion.cursor() as cursor:
        columnas = {
            columna.name
            for columna in conexion.introspection.get_table_description(
                cursor,
                tabla_movimientos,
            )
        }

    if campo_produccion.column not in columnas:
        schema_editor.add_field(
            MovimientoStock,
            campo_produccion,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0003_reparar_columna_proveedor_externo"),
    ]

    operations = [
        migrations.RunPython(
            reparar_esquema_inventario,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
