from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .management.commands.cargar_datos_demo import (
    DEMO_OBSERVATION_PREFIX,
    DEMO_PREFIX,
)
from .models import (
    MateriaPrima,
    Movimiento,
    TipoMovimiento,
    UnidadMedida,
    Variedad,
)
from .forms import MateriaPrimaForm, MovimientoForm


class CargarDatosDemoTests(TestCase):
    def setUp(self):
        self.unit = UnidadMedida.objects.create(
            nombre="kilogramo",
            simbolo="kg",
            factor_kg=Decimal("1"),
        )
        self.income_type = TipoMovimiento.objects.create(
            nombre="ingreso",
            efecto_predeterminado=1,
        )
        self.consumption_type = TipoMovimiento.objects.create(
            nombre="consumo",
            efecto_predeterminado=-1,
        )
        self.existing_product = MateriaPrima.objects.create(
            nombre="Producto preexistente",
            stock_minimo=Decimal("10"),
        )
        self.existing_variety = Variedad.objects.create(
            materia_prima=self.existing_product,
            nombre="Lote existente",
        )
        self.existing_movement = Movimiento.objects.create(
            materia_prima=self.existing_product,
            variedad=self.existing_variety,
            unidad=self.unit,
            tipo=self.income_type,
            cantidad=Decimal("500"),
            observacion="Registro preexistente",
        )

    def load_demo(self):
        output = StringIO()
        with override_settings(DEBUG=True):
            call_command(
                "cargar_datos_demo",
                confirmar_entorno_demo=True,
                stdout=output,
            )
        return output.getvalue()

    def test_creates_coherent_stock_and_preserves_existing_records(self):
        output = self.load_demo()

        self.assertIn("3 productos, 6 variedades y 36 movimientos", output)
        self.assertEqual(MateriaPrima.objects.count(), 4)
        self.assertEqual(Variedad.objects.count(), 7)
        self.assertEqual(Movimiento.objects.count(), 37)
        self.existing_movement.refresh_from_db()
        self.assertEqual(self.existing_movement.cantidad_kg, Decimal("500.000"))
        self.assertEqual(self.existing_movement.observacion, "Registro preexistente")

        expected_stocks = {
            ("DEMO - Papa andina", "Morada"): Decimal("155.000"),
            ("DEMO - Papa andina", "Colorada"): Decimal("45.000"),
            ("DEMO - Papa andina", "Amarilla"): Decimal("125.000"),
            ("DEMO - Maíz", "Amarillo"): Decimal("100.000"),
            ("DEMO - Maíz", "Blanco"): Decimal("20.000"),
            ("DEMO - Poroto", "Pallar"): Decimal("15.000"),
        }
        for (product_name, variety_name), expected_stock in expected_stocks.items():
            product = MateriaPrima.objects.get(nombre=product_name)
            variety = Variedad.objects.get(
                materia_prima=product,
                nombre=variety_name,
            )
            stock = sum(
                movement.cantidad_kg * movement.efecto_stock
                for movement in Movimiento.objects.filter(variedad=variety)
            )
            self.assertEqual(stock, expected_stock)

    def test_repeated_run_does_not_duplicate_demo_records(self):
        self.load_demo()
        output = self.load_demo()

        self.assertIn("ya están cargados", output)
        self.assertEqual(
            MateriaPrima.objects.filter(nombre__startswith=DEMO_PREFIX).count(),
            3,
        )
        self.assertEqual(
            Movimiento.objects.filter(
                observacion__startswith=DEMO_OBSERVATION_PREFIX
            ).count(),
            36,
        )

    def test_requires_explicit_confirmation(self):
        with self.assertRaises(CommandError):
            call_command("cargar_datos_demo", stdout=StringIO())
        self.assertFalse(
            MateriaPrima.objects.filter(nombre__startswith=DEMO_PREFIX).exists()
        )

    @override_settings(DEBUG=False)
    def test_refuses_to_load_when_debug_is_disabled(self):
        with self.assertRaises(CommandError):
            call_command(
                "cargar_datos_demo",
                confirmar_entorno_demo=True,
                stdout=StringIO(),
            )
        self.assertFalse(
            MateriaPrima.objects.filter(nombre__startswith=DEMO_PREFIX).exists()
        )

    def test_dashboard_history_report_and_csv_show_demo_data(self):
        self.load_demo()
        user = get_user_model().objects.create_user(username="demo-test-user")
        client = Client()
        client.force_login(user)

        dashboard = client.get(reverse("dashboard"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "DEMO - Papa andina")
        dashboard_products = dashboard.context["productos"]
        critical_products = {
            (product["nombre"], product["variedad"])
            for product in dashboard_products
            if product["alerta"]
        }
        self.assertIn(("DEMO - Maíz", "Blanco"), critical_products)
        self.assertIn(("DEMO - Poroto", "Pallar"), critical_products)
        self.assertNotIn(("DEMO - Papa andina", "Colorada"), critical_products)

        demo_potato = MateriaPrima.objects.get(nombre="DEMO - Papa andina")
        demo_variety = Variedad.objects.get(
            materia_prima=demo_potato,
            nombre="Morada",
        )
        history = client.get(
            reverse("historial_producto", args=[demo_potato.id])
        )
        self.assertEqual(history.status_code, 200)
        self.assertEqual(
            history.context["movimientos"].filter(variedad=demo_variety).count(),
            6,
        )

        sample_movement = Movimiento.objects.filter(
            variedad=demo_variety,
            observacion__startswith=DEMO_OBSERVATION_PREFIX,
        ).first()
        report_params = {
            "mes": sample_movement.fecha.month,
            "anio": sample_movement.fecha.year,
        }
        report = client.get(reverse("informes"), report_params)
        self.assertEqual(report.status_code, 200)
        report_row = next(
            row
            for row in report.context["reporte"]
            if row["nombre"] == "DEMO - Papa andina"
            and row["variedad"] == "Morada"
        )
        month_movements = Movimiento.objects.filter(
            variedad=demo_variety,
            fecha__year=report_params["anio"],
            fecha__month=report_params["mes"],
        )
        expected_income = sum(
            movement.cantidad_kg
            for movement in month_movements
            if movement.efecto_stock == 1
        )
        expected_consumption = sum(
            movement.cantidad_kg
            for movement in month_movements
            if movement.efecto_stock == -1
        )
        self.assertEqual(report_row["ingresos"], expected_income)
        self.assertEqual(report_row["consumos"], expected_consumption)
        self.assertEqual(report_row["stock_total"], Decimal("155.000"))

        csv_response = client.get(
            reverse("exportar_informe"),
            report_params,
        )
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(csv_response["Content-Type"], "text/csv")
        self.assertIn(b"DEMO - Papa andina", csv_response.content)

class MateriaPrimaFormTests(TestCase):

    def test_rechaza_nombres_duplicados_sin_distinguir_mayusculas(self):
        MateriaPrima.objects.create(
            nombre="Quinoa",
            stock_minimo=Decimal("10")
        )

        formulario = MateriaPrimaForm(data={
            "nombre": "QUINOA",
            "descripcion": "",
            "stock_minimo": "10",
        })

        self.assertFalse(formulario.is_valid())
        self.assertIn(
            "Ya existe una materia prima con ese nombre.",
            formulario.errors["nombre"]
        )

    def test_rechaza_stock_minimo_negativo(self):
        formulario = MateriaPrimaForm(data={
            "nombre": "Producto de prueba",
            "descripcion": "",
            "stock_minimo": "-5",
        })

        self.assertFalse(formulario.is_valid())
        self.assertIn(
            "El stock mínimo no puede ser negativo.",
            formulario.errors["stock_minimo"]
        )
class MovimientoFormTests(TestCase):

    def setUp(self):
        self.materia_activa = MateriaPrima.objects.create(
            nombre="Materia activa",
            activo=True
        )

        self.materia_inactiva = MateriaPrima.objects.create(
            nombre="Materia inactiva",
            activo=False
        )

        self.variedad_activa = Variedad.objects.create(
            materia_prima=self.materia_activa,
            nombre="Variedad activa",
            activo=True
        )

        self.variedad_inactiva = Variedad.objects.create(
            materia_prima=self.materia_activa,
            nombre="Variedad inactiva",
            activo=False
        )

        self.variedad_materia_inactiva = Variedad.objects.create(
            materia_prima=self.materia_inactiva,
            nombre="Variedad de materia inactiva",
            activo=True
        )

    def test_solo_muestra_materias_primas_activas(self):
        formulario = MovimientoForm()

        materias = set(
            formulario.fields["materia_prima"].queryset.values_list(
                "id", flat=True
            )
        )
        self.assertEqual(materias, {self.materia_activa.id})

    def test_solo_muestra_variedades_activas_de_materias_activas(self):
        formulario = MovimientoForm()

        variedades = set(
            formulario.fields["variedad"].queryset.values_list(
                "id", flat=True
            )
        )
        self.assertEqual(variedades, {self.variedad_activa.id})
