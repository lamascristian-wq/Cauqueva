
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import (
    MateriaPrimaForm,
    MovimientoStockForm,
    ConsumoForm,
    ProveedorForm,
)
from .models import MateriaPrima, MovimientoStock, Proveedor


class MateriaPrimaFormTests(TestCase):

    def test_crea_materia_prima_correctamente(self):
        formulario = MateriaPrimaForm(data={
            "nombre": "Papa",
            "variedad": "Andina",
            "unidad_medida": "KG",
            "descripcion": "Papa para producción",
        })

        self.assertTrue(formulario.is_valid(), formulario.errors)

        materia = formulario.save()

        self.assertEqual(materia.nombre, "Papa")
        self.assertEqual(materia.variedad, "Andina")
        self.assertEqual(materia.stock_actual, Decimal("0.00"))

    def test_rechaza_materia_prima_duplicada(self):
        MateriaPrima.objects.create(
            nombre="Quinoa",
            variedad="Real",
        )

        formulario = MateriaPrimaForm(data={
            "nombre": "QUINOA",
            "variedad": "REAL",
            "unidad_medida": "KG",
            "descripcion": "",
        })

        self.assertFalse(formulario.is_valid())
        self.assertIn(
            "Ya existe una materia prima con ese nombre y esa variedad.",
            formulario.non_field_errors(),
        )


class ProveedorFormTests(TestCase):

    def test_crea_proveedor_correctamente(self):
        formulario = ProveedorForm(data={
            "nombre": "Finca Norte",
            "telefono": "3884123456",
        })

        self.assertTrue(formulario.is_valid(), formulario.errors)

        proveedor = formulario.save()

        self.assertEqual(proveedor.nombre, "Finca Norte")
        self.assertEqual(proveedor.telefono, "3884123456")

    def test_rechaza_proveedor_duplicado_sin_distinguir_mayusculas(self):
        Proveedor.objects.create(nombre="Finca Norte")

        formulario = ProveedorForm(data={
            "nombre": "FINCA NORTE",
            "telefono": "",
        })

        self.assertFalse(formulario.is_valid())
        self.assertIn(
            "Ya existe un proveedor con ese nombre.",
            formulario.errors["nombre"],
        )


class MovimientoStockTests(TestCase):

    def setUp(self):
        self.materia = MateriaPrima.objects.create(
            nombre="Papa",
            variedad="Andina",
        )

        self.proveedor = Proveedor.objects.create(
            nombre="Finca Norte",
            telefono="3884123456",
        )

    def crear_ingreso(self, cantidad="10.00"):
        return MovimientoStock.objects.create(
            materia_prima=self.materia,
            tipo="INGRESO",
            cantidad=Decimal(cantidad),
            observaciones="Ingreso de prueba",
        )

    def crear_formulario_consumo(self, cantidad):
        fecha = timezone.localtime(timezone.now()).strftime(
            "%Y-%m-%dT%H:%M"
        )

        return ConsumoForm(data={
            "materia_prima": self.materia.pk,
            "cantidad": cantidad,
            "fecha": fecha,
            "observaciones": "Consumo de prueba",
        })

    def test_registrar_ingreso_aumenta_el_stock(self):
        formulario = MovimientoStockForm(data={
            "materia_prima": self.materia.pk,
            "proveedor": self.proveedor.pk,
            "cantidad": "10.00",
            "observaciones": "Ingreso inicial",
        })

        self.assertTrue(formulario.is_valid(), formulario.errors)

        movimiento = formulario.save()
        self.materia.refresh_from_db()

        self.assertEqual(movimiento.tipo, "INGRESO")
        self.assertEqual(self.materia.stock_actual, Decimal("10.00"))

    def test_registrar_consumo_disminuye_el_stock(self):
        self.crear_ingreso("10.00")

        formulario = self.crear_formulario_consumo("3.00")

        self.assertTrue(formulario.is_valid(), formulario.errors)

        movimiento = formulario.save()
        self.materia.refresh_from_db()

        self.assertEqual(movimiento.tipo, "CONSUMO")
        self.assertEqual(self.materia.stock_actual, Decimal("7.00"))

    def test_rechaza_consumo_superior_al_stock(self):
        self.crear_ingreso("10.00")

        formulario = self.crear_formulario_consumo("15.00")

        self.assertFalse(formulario.is_valid())
        self.assertTrue(formulario.non_field_errors())

        self.materia.refresh_from_db()
        self.assertEqual(self.materia.stock_actual, Decimal("10.00"))

    def test_eliminar_movimiento_revierte_el_stock(self):
        self.crear_ingreso("10.00")

        formulario = self.crear_formulario_consumo("3.00")
        self.assertTrue(formulario.is_valid(), formulario.errors)

        consumo = formulario.save()

        self.materia.refresh_from_db()
        self.assertEqual(self.materia.stock_actual, Decimal("7.00"))

        consumo.delete()

        self.materia.refresh_from_db()
        self.assertEqual(self.materia.stock_actual, Decimal("10.00"))


class InventarioViewsTests(TestCase):

    def setUp(self):
        usuario = get_user_model().objects.create_user(
            username="usuario_prueba",
            password="clave_prueba_123",
        )
        self.client.force_login(usuario)

    def test_inventario_muestra_materias_primas(self):
        MateriaPrima.objects.create(
            nombre="Maiz",
            variedad="Amarillo",
        )

        respuesta = self.client.get(reverse("inventariostock"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Maiz")

    def test_registrar_materia_prima_guarda_el_registro(self):
        respuesta = self.client.post(
            reverse("registrar_materia_prima"),
            {
                "nombre": "Poroto",
                "variedad": "Pallar",
                "unidad_medida": "KG",
                "descripcion": "Poroto para producción",
            },
        )

        self.assertEqual(respuesta.status_code, 302)

        self.assertTrue(
            MateriaPrima.objects.filter(
                nombre="Poroto",
                variedad="Pallar",
            ).exists()
        )

    def test_registro_de_ingresos_requiere_inicio_de_sesion(self):
        self.client.logout()

        respuesta = self.client.get(reverse("registrar_movimiento"))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("login"), respuesta.url)
