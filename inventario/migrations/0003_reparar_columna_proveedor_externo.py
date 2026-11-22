
from django.db import migrations


def agregar_columna_si_falta(apps, schema_editor):
    MovimientoStock = apps.get_model("inventario", "MovimientoStock")

    tabla = MovimientoStock._meta.db_table
    campo = MovimientoStock._meta.get_field("proveedor_externo")
    conexion = schema_editor.connection

    with conexion.cursor() as cursor:
        columnas = {
            columna.name
            for columna in conexion.introspection.get_table_description(
                cursor,
                tabla,
            )
        }

    if campo.column not in columnas:
        schema_editor.add_field(MovimientoStock, campo)


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0002_materiaprima_alerta_stock_enviada"),
    ]

    operations = [
        migrations.RunPython(
            agregar_columna_si_falta,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
