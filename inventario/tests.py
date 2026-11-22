
from decimal import Decimal
from unittest.mock import patch
from django.test import override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import ProveedorForm
from .models import MateriaPrima, MovimientoStock, Proveedor


class SidebarRoleMenuTests(TestCase):
    def obtener_sidebar(self, is_staff):
        usuario = get_user_model().objects.create_user(
            username="gerente" if is_staff else "operario",
            password="test-password",
            is_staff=is_staff,
        )
        cliente = Client()
        cliente.force_login(usuario)
        respuesta = cliente.get(reverse("registrar_movimiento"))
        self.assertEqual(respuesta.status_code, 200)

        contenido = respuesta.content.decode()
        return contenido.split("<nav ", 1)[1].split("</nav>", 1)[0]

    def test_operator_sees_only_operational_links_in_required_order(self):
        sidebar = self.obtener_sidebar(is_staff=False)
        opciones = [
            "Registro de Ingresos",
            "Consumo y Salidas",
            "Historial de Movimientos",
        ]

        posiciones = [sidebar.index(opcion) for opcion in opciones]
        self.assertEqual(posiciones, sorted(posiciones))
        self.assertEqual(sidebar.count("<a href="), 3)
        self.assertNotIn("Panel Principal", sidebar)
        self.assertNotIn("Reportes", sidebar)
        self.assertNotIn("Materias Primas", sidebar)
        self.assertNotIn("Proveedores", sidebar)

    def test_manager_sees_full_menu_in_required_order(self):
        sidebar = self.obtener_sidebar(is_staff=True)
        opciones = [
            "Panel Principal",
            "Consumo y Salidas",
            "Reportes",
            "Materias Primas",
            "Proveedores",
            "Registro de Ingresos",
            "Historial de Movimientos",
        ]

        posiciones = [sidebar.index(opcion) for opcion in opciones]
        self.assertEqual(posiciones, sorted(posiciones))
        self.assertEqual(sidebar.count("<a href="), 7)


class MovimientoStockTests(TestCase):
    def setUp(self):
        self.papa = MateriaPrima.objects.create(
            nombre="Papa",
            variedad="Andina",
            stock_minimo=Decimal("10.00"),
        )
        self.maiz = MateriaPrima.objects.create(
            nombre="Maíz",
            variedad="Blanco",
            stock_minimo=Decimal("10.00"),
        )

    def crear_movimiento(self, materia, tipo, cantidad, proveedor=None):
        return MovimientoStock.objects.create(
            materia_prima=materia,
            proveedor=proveedor,
            tipo=tipo,
            cantidad=Decimal(str(cantidad)),
        )

    def test_income_changes_stock_once(self):
        self.crear_movimiento(self.papa, "INGRESO", "12.50")

        self.papa.refresh_from_db()
        self.assertEqual(self.papa.stock_actual, Decimal("12.50"))

    def test_movement_total_cost_uses_recorded_unit_price(self):
        movimiento = MovimientoStock.objects.create(
            materia_prima=self.papa,
            tipo="INGRESO",
            cantidad=Decimal("3.50"),
            precio_unitario=Decimal("12.40"),
        )

        self.assertEqual(movimiento.costo_total, Decimal("43.4000"))

    def test_edit_reverses_old_delta_and_applies_new_delta(self):
        movimiento = self.crear_movimiento(self.papa, "INGRESO", "20")
        self.crear_movimiento(self.maiz, "INGRESO", "10")

        movimiento.materia_prima = self.maiz
        movimiento.tipo = "CONSUMO"
        movimiento.cantidad = Decimal("5")
        movimiento.save()

        self.papa.refresh_from_db()
        self.maiz.refresh_from_db()
        self.assertEqual(self.papa.stock_actual, Decimal("0.00"))
        self.assertEqual(self.maiz.stock_actual, Decimal("5.00"))

    def test_insufficient_consumption_rolls_back_movement_and_stock(self):
        self.crear_movimiento(self.papa, "INGRESO", "5")

        with self.assertRaises(ValidationError):
            self.crear_movimiento(self.papa, "CONSUMO", "6")

        self.papa.refresh_from_db()
        self.assertEqual(self.papa.stock_actual, Decimal("5.00"))
        self.assertEqual(MovimientoStock.objects.count(), 1)

    def test_queryset_delete_reverses_stock_delta(self):
        ingreso = self.crear_movimiento(self.papa, "INGRESO", "20")
        consumo = self.crear_movimiento(self.papa, "CONSUMO", "5")

        MovimientoStock.objects.filter(pk=consumo.pk).delete()
        self.papa.refresh_from_db()
        self.assertEqual(self.papa.stock_actual, Decimal("20.00"))

        MovimientoStock.objects.filter(pk=ingreso.pk).delete()
        self.papa.refresh_from_db()
        self.assertEqual(self.papa.stock_actual, Decimal("0.00"))

    def test_editing_consumption_keeps_its_type_and_reconciles_stock(self):
        self.crear_movimiento(self.papa, "INGRESO", "10")
        consumo = self.crear_movimiento(self.papa, "CONSUMO", "4")
        user = get_user_model().objects.create_user(
            username="gerente",
            password="test-password",
            is_staff=True,
        )
        client = Client()
        client.force_login(user)

        response = client.post(
            reverse("editar_movimiento", kwargs={"id": consumo.pk}),
            {
                "materia_prima": self.papa.pk,
                "proveedor": "",
                "cantidad": "7",
                "precio_unitario": "0.00",
                "observaciones": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        consumo.refresh_from_db()
        self.papa.refresh_from_db()
        self.assertEqual(consumo.tipo, "CONSUMO")
        self.assertEqual(consumo.cantidad, Decimal("7"))
        self.assertEqual(self.papa.stock_actual, Decimal("3.00"))

    def test_failed_edit_rolls_back_movement_and_stock(self):
        self.crear_movimiento(self.papa, "INGRESO", "10")
        consumo = self.crear_movimiento(self.papa, "CONSUMO", "4")
        user = get_user_model().objects.create_user(
            username="gerente",
            password="test-password",
            is_staff=True,
        )
        client = Client()
        client.force_login(user)

        response = client.post(
            reverse("editar_movimiento", kwargs={"id": consumo.pk}),
            {
                "materia_prima": self.papa.pk,
                "proveedor": "",
                "cantidad": "11",
                "precio_unitario": "0.00",
                "observaciones": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        consumo.refresh_from_db()
        self.papa.refresh_from_db()
        self.assertEqual(consumo.cantidad, Decimal("4"))
        self.assertEqual(self.papa.stock_actual, Decimal("6.00"))

    def test_income_view_does_not_double_stock(self):
        proveedor = Proveedor.objects.create(nombre="Finca de prueba")
        user = get_user_model().objects.create_user(
            username="operario",
            password="test-password",
        )
        client = Client()
        client.force_login(user)

        response = client.post(
            reverse("registrar_movimiento"),
            {
                "materia_prima": self.papa.pk,
                "proveedor": proveedor.pk,
                "cantidad": "12.50",
                "precio_unitario": "2.75",
                "observaciones": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.papa.refresh_from_db()
        self.assertEqual(self.papa.stock_actual, Decimal("12.50"))
        movimiento = MovimientoStock.objects.get(materia_prima=self.papa)
        self.assertEqual(movimiento.precio_unitario, Decimal("2.75"))
        self.assertEqual(movimiento.costo_total, Decimal("34.3750"))

    def test_income_form_exposes_reference_price_for_autocomplete(self):
        self.papa.precio_referencia = Decimal("3.25")
        self.papa.save(update_fields=["precio_referencia"])
        user = get_user_model().objects.create_user(
            username="operario-autocomplete",
            password="test-password",
        )
        client = Client()
        client.force_login(user)

        response = client.get(reverse("registrar_movimiento"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-precio-referencia="3.25"')
        self.assertContains(response, 'id="id_precio_unitario"')


class ProveedorFormTests(TestCase):
    def test_form_saves_selected_materias_primas(self):
        materia = MateriaPrima.objects.create(
            nombre="Quinoa",
            variedad="Real",
        )
        formulario = ProveedorForm(
            data={
                "nombre": "Cooperativa de prueba",
                "telefono": "",
                "materias_primas": [str(materia.pk)],
            }
        )

        self.assertTrue(formulario.is_valid(), formulario.errors)
        proveedor = formulario.save()
        self.assertQuerySetEqual(
            proveedor.materias_primas.all(),
            [materia],
            transform=lambda item: item,
        )

    def test_supplier_form_renders_empty_materia_link(self):
        user = get_user_model().objects.create_user(
            username="gerente",
            password="test-password",
            is_staff=True,
        )
        client = Client()
        client.force_login(user)

        response = client.get(reverse("crear_proveedor"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("registrar_materia_prima"))

    def test_alertas_template_resolves_replenish_link(self):
        MateriaPrima.objects.create(
            nombre="Tomate",
            variedad="Perita",
            stock_minimo=Decimal("10.00"),
        )
        user = get_user_model().objects.create_user(
            username="operario",
            password="test-password",
        )
        client = Client()
        client.force_login(user)

        response = client.get(reverse("alertas"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("registrar_movimiento"))

    def test_new_materia_redirects_to_inventory(self):
        user = get_user_model().objects.create_user(
            username="operario",
            password="test-password",
        )
        client = Client()
        client.force_login(user)

        response = client.post(
            reverse("registrar_materia_prima"),
            {
                "nombre": "Arveja",
                "variedad": "",
                "unidad_medida": "KG",
                "precio_referencia": "2.50",
                "descripcion": "",
            },
        )

        self.assertRedirects(response, reverse("inventariostock"), fetch_redirect_response=False)
        materia = MateriaPrima.objects.get(nombre="Arveja")
        self.assertEqual(materia.precio_referencia, Decimal("2.50"))

@override_settings(
    RESEND_API_KEY="re_test_123",
    RESEND_FROM_EMAIL="CAUQUEVA <alertas@ejemplo.com>",
    RESEND_TO_EMAIL="gerente@ejemplo.com",
)
class NotificacionesStockTests(TestCase):
    def setUp(self):
        self.materia = MateriaPrima.objects.create(
            nombre="Papa",
            variedad="Andina",
            stock_actual=Decimal("0.00"),
            stock_minimo=Decimal("10.00"),
        )

    def crear_movimiento(self, tipo, cantidad):
        return MovimientoStock.objects.create(
            materia_prima=self.materia,
            tipo=tipo,
            cantidad=Decimal(str(cantidad)),
        )

    @patch("inventario.notificaciones.resend.Emails.send")
    def test_envia_alerta_al_llegar_al_stock_critico(self, enviar):
        self.crear_movimiento("INGRESO", "12")

        with self.captureOnCommitCallbacks(execute=True):
            self.crear_movimiento("CONSUMO", "3")

        self.materia.refresh_from_db()

        self.assertEqual(self.materia.stock_actual, Decimal("9.00"))
        self.assertTrue(self.materia.alerta_stock_enviada)
        enviar.assert_called_once()

        datos_correo = enviar.call_args.args[0]

        self.assertEqual(
            datos_correo["to"],
            ["gerente@ejemplo.com"],
        )
        self.assertEqual(
            datos_correo["subject"],
            "Alerta crítica de stock - CAUQUEVA",
        )
        self.assertIn("Papa", datos_correo["text"])
        self.assertIn("9", datos_correo["text"])
        self.assertIn("10", datos_correo["text"])
        self.assertIn("Kilogramos", datos_correo["text"])

    @patch("inventario.notificaciones.resend.Emails.send")
    def test_no_repite_alerta_mientras_el_stock_sigue_critico(
        self,
        enviar,
    ):
        self.crear_movimiento("INGRESO", "12")

        with self.captureOnCommitCallbacks(execute=True):
            self.crear_movimiento("CONSUMO", "3")

        with self.captureOnCommitCallbacks(execute=True):
            self.crear_movimiento("CONSUMO", "1")

        self.materia.refresh_from_db()

        self.assertEqual(self.materia.stock_actual, Decimal("8.00"))
        self.assertTrue(self.materia.alerta_stock_enviada)
        enviar.assert_called_once()

    @patch("inventario.notificaciones.resend.Emails.send")
    def test_permite_nueva_alerta_despues_de_recuperar_stock(
        self,
        enviar,
    ):
        self.crear_movimiento("INGRESO", "12")

        with self.captureOnCommitCallbacks(execute=True):
            self.crear_movimiento("CONSUMO", "3")

        with self.captureOnCommitCallbacks(execute=True):
            self.crear_movimiento("INGRESO", "5")

        self.materia.refresh_from_db()
        self.assertEqual(self.materia.stock_actual, Decimal("14.00"))
        self.assertFalse(self.materia.alerta_stock_enviada)

        with self.captureOnCommitCallbacks(execute=True):
            self.crear_movimiento("CONSUMO", "5")

        self.materia.refresh_from_db()

        self.assertEqual(self.materia.stock_actual, Decimal("9.00"))
        self.assertTrue(self.materia.alerta_stock_enviada)
        self.assertEqual(enviar.call_count, 2)

    @patch("inventario.notificaciones.resend.Emails.send")
    def test_fallo_de_resend_no_interrumpe_el_movimiento(
        self,
        enviar,
    ):
        enviar.side_effect = RuntimeError("Error simulado de Resend")

        self.crear_movimiento("INGRESO", "12")

        with self.captureOnCommitCallbacks(execute=True):
            self.crear_movimiento("CONSUMO", "3")

        self.materia.refresh_from_db()

        self.assertEqual(self.materia.stock_actual, Decimal("9.00"))
        self.assertFalse(self.materia.alerta_stock_enviada)
        enviar.assert_called_once()
