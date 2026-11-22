
from django import forms
from django.utils import timezone
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Q
from decimal import Decimal
import re

from .models import MateriaPrima, MovimientoStock, Proveedor, Producto


ESTILO = (
    "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-green-600 focus:border-green-600"
)


class PrecioReferenciaSelect(forms.Select):
    """Agrega el precio de referencia a cada opción del desplegable."""

    def create_option(
        self,
        name,
        value,
        label,
        selected,
        index,
        subindex=None,
        attrs=None,
    ):
        option = super().create_option(
            name,
            value,
            label,
            selected,
            index,
            subindex=subindex,
            attrs=attrs,
        )

        if hasattr(value, "instance"):
            option["attrs"]["data-precio-referencia"] = str(
                value.instance.precio_referencia
            )

        return option


class MateriaPrimaForm(forms.ModelForm):
    cantidad_inicial = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        initial=0.00,
        min_value=0.00,
        label="Cantidad inicial (Kg)",
        widget=forms.NumberInput(attrs={
            "class": ESTILO,
            "step": "0.01",
            "placeholder": "Ej: 100.00 (opcional)"
        })
    )

    precio_unitario = forms.DecimalField(
        label="Precio por Kg ($)",
        required=False,
        min_value=Decimal("0"),
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            "class": ESTILO,
            "step": "0.01",
            "min": "0"
        }),
    )

    stock_minimo = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        min_value=Decimal("0"),
        label="Stock mínimo para alertas (Kg)",
        widget=forms.NumberInput(attrs={
            "class": ESTILO,
            "step": "0.01",
            "min": "0"
        }),
    )

    class Meta:
        model = MateriaPrima
        fields = [
            "nombre",
            "variedad",
            "precio_referencia",
            "descripcion",
            "stock_minimo"
        ]

        labels = {
            "nombre": "Nombre",
            "variedad": "Variedad",
            "unidad_medida": "Unidad de medida",
            "precio_referencia": "Precio de referencia",
            "descripcion": "Descripción",
        }

        widgets = {
            "nombre": forms.TextInput(attrs={
                "class": ESTILO,
                "placeholder": "Ej: Papa, Maíz, Apio",
                "maxlength": 100,
            }),
            "variedad": forms.TextInput(attrs={
                "class": ESTILO,
                "placeholder": "Ej: Andina (opcional)",
                "maxlength": 100,
            }),
            "unidad_medida": forms.Select(attrs={
                "class": ESTILO,
            }),
            "precio_referencia": forms.NumberInput(attrs={
                "class": ESTILO,
                "step": "0.01",
                "min": "0",
            }),
            "descripcion": forms.Textarea(attrs={
                "class": ESTILO,
                "rows": 3,
                "maxlength": 255,
            }),
        }

    def clean(self):
        datos = super().clean()

        nombre = (datos.get("nombre") or "").strip()
        variedad = (datos.get("variedad") or "").strip()

        # Evita registrar materias primas duplicadas.
        if nombre:
            repetidas = MateriaPrima.objects.filter(nombre__iexact=nombre)

            if variedad:
                repetidas = repetidas.filter(variedad__iexact=variedad)
            else:
                repetidas = repetidas.filter(
                    Q(variedad__isnull=True) | Q(variedad="")
                )

            if repetidas.exists():
                raise forms.ValidationError(
                    "Ya existe una materia prima con ese nombre y esa variedad."
                )

        # Si se registra stock inicial, el precio es obligatorio y debe ser positivo.
        cantidad_inicial = datos.get("cantidad_inicial") or Decimal("0.00")
        precio_unitario = datos.get("precio_unitario")

        if cantidad_inicial > 0:
            if precio_unitario is None or precio_unitario <= 0:
                self.add_error(
                    "precio_unitario",
                    "Debes ingresar un precio mayor que cero cuando registras stock inicial."
                )

        return datos

    def clean_stock_minimo(self):
        minimo = self.cleaned_data.get("stock_minimo")

        # Si no se informa, utiliza el valor predeterminado del modelo.
        if minimo is None:
            minimo = self.instance._meta.get_field(
                "stock_minimo"
            ).get_default()

        if minimo < 0:
            raise forms.ValidationError(
                "El stock mínimo no puede ser negativo."
            )

        return minimo


class MovimientoStockForm(forms.ModelForm):
    """Formulario para registrar y editar ingresos y consumos."""

    class Meta:
        model = MovimientoStock
        fields = [
            "materia_prima",
            "proveedor",
            "proveedor_externo",
            "cantidad",
            "precio_unitario",
            "observaciones"
        ]

        labels = {
            "materia_prima": "Materia prima",
            "proveedor": "Proveedor registrado",
            "proveedor_externo": "O proveedor externo (Manual)",
            "cantidad": "Cantidad que ingresa",
            "precio_unitario": "Precio unitario",
            "observaciones": "Observaciones",
        }

        widgets = {
            "materia_prima": PrecioReferenciaSelect(attrs={
                "class": ESTILO
            }),
            "proveedor": forms.Select(attrs={
                "class": ESTILO
            }),
            "proveedor_externo": forms.TextInput(attrs={
                "class": ESTILO,
                "placeholder": "Ej: Juan Pérez (Productor particular)"
            }),
            "cantidad": forms.NumberInput(attrs={
                "class": ESTILO,
                "step": "0.01",
                "min": "0.01"
            }),
            "precio_unitario": forms.NumberInput(attrs={
                "class": ESTILO,
                "step": "0.01",
                "min": "0.01"
            }),
            "observaciones": forms.Textarea(attrs={
                "class": ESTILO,
                "rows": 3
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Al crear un movimiento nuevo, siempre será un ingreso.
        if self.instance._state.adding:
            self.instance.tipo = "INGRESO"

        # El proveedor se valida manualmente en clean().
        self.fields["proveedor"].required = False
        self.fields["proveedor_externo"].required = False

        if self.instance.tipo == "CONSUMO":
            self.fields["cantidad"].label = "Cantidad consumida"

        self.fields["proveedor"].empty_label = "Seleccioná un proveedor"

        self.fields["materia_prima"].queryset = (
            MateriaPrima.objects.order_by("nombre", "variedad")
        )

        # Muestra la unidad y el stock actual en el desplegable.
        self.fields["materia_prima"].label_from_instance = (
            lambda m: (
                f"{m} ({m.get_unidad_medida_display()}) "
                f"· stock: {m.stock_actual:g}"
            )
        )

        self.fields["precio_unitario"].required = True

    def clean_precio_unitario(self):
        precio = self.cleaned_data.get("precio_unitario")

        # Los ingresos siempre deben tener un precio real.
        # En los consumos se permite precio cero.
        if self.instance.tipo == "INGRESO":
            if precio is None or precio <= 0:
                raise forms.ValidationError(
                    "El precio unitario tiene que ser mayor a 0."
                )

        return precio

    def clean(self):
        cleaned_data = super().clean()

        proveedor = cleaned_data.get("proveedor")
        proveedor_externo = (
            cleaned_data.get("proveedor_externo") or ""
        ).strip()

        # Los ingresos necesitan un proveedor registrado o externo.
        # Los consumos de producción no necesitan proveedor.
        if self.instance.tipo == "INGRESO":

            if not proveedor and not proveedor_externo:
                raise forms.ValidationError(
                    "Debes seleccionar un proveedor registrado "
                    "o escribir el nombre de uno externo."
                )

            if proveedor and proveedor_externo:
                raise forms.ValidationError(
                    "No puedes seleccionar un proveedor y escribir "
                    "uno externo a la vez. Usa solo un campo."
                )

        return cleaned_data


class ProduccionForm(forms.Form):
    producto = forms.ModelChoiceField(
        label="Producto",
        queryset=Producto.objects.none(),
        empty_label="Seleccioná un producto",
        widget=forms.Select(attrs={"class": ESTILO}),
    )

    cantidad = forms.IntegerField(
        label="Cantidad a producir (unidades)",
        min_value=1,
        widget=forms.NumberInput(attrs={
            "class": ESTILO,
            "min": "1",
            "step": "1"
        }),
    )

    fecha = forms.DateTimeField(
        label="Fecha y hora",
        initial=timezone.now,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "class": ESTILO
            },
            format="%Y-%m-%dT%H:%M",
        ),
    )

    observaciones = forms.CharField(
        label="Observaciones",
        required=False,
        widget=forms.Textarea(attrs={
            "class": ESTILO,
            "rows": 3,
            "placeholder": "Ej: Lote del día (opcional)"
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["producto"].queryset = (
            Producto.objects.filter(activo=True).order_by("nombre")
        )

class ConsumoManualForm(forms.Form):
    materia_prima = forms.ModelChoiceField(
        label="Materia prima",
        queryset=MateriaPrima.objects.none(),
        empty_label="Seleccioná una materia prima",
        widget=forms.Select(attrs={"class": ESTILO}),
    )

    cantidad = forms.DecimalField(
        label="Cantidad consumida",
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(attrs={
            "class": ESTILO,
            "min": "0.01",
            "step": "0.01",
        }),
    )

    fecha = forms.DateTimeField(
        label="Fecha y hora",
        initial=timezone.now,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={
                "type": "datetime-local",
                "class": ESTILO,
            },
            format="%Y-%m-%dT%H:%M",
        ),
    )

    observaciones = forms.CharField(
        label="Observaciones",
        required=False,
        widget=forms.Textarea(attrs={
            "class": ESTILO,
            "rows": 3,
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["materia_prima"].queryset = (
            MateriaPrima.objects.order_by("nombre", "variedad")
        )

        self.fields["materia_prima"].label_from_instance = (
            lambda m: (
                f"{m} ({m.get_unidad_medida_display()}) "
                f"· stock disponible: {m.stock_actual:g}"
            )
        )

    def clean(self):
        cleaned_data = super().clean()

        materia = cleaned_data.get("materia_prima")
        cantidad = cleaned_data.get("cantidad")

        if materia and cantidad is not None:
            if cantidad > materia.stock_actual:
                self.add_error(
                    "cantidad",
                    f"Stock insuficiente. Hay {materia.stock_actual:g} "
                    f"{materia.get_unidad_medida_display()} disponibles.",
                )

        return cleaned_data


class ProveedorForm(forms.ModelForm):
    materias_primas = forms.ModelMultipleChoiceField(
        queryset=MateriaPrima.objects.order_by("nombre", "variedad"),
        required=False,
        label="Materias primas que provee",
        help_text="Seleccioná las materias primas que ofrece este proveedor.",
        widget=forms.CheckboxSelectMultiple(
            attrs={"class": "rounded border-gray-300 text-green-700"}
        ),
    )

    telefono = forms.CharField(
        required=False,
        max_length=50,
        label="Teléfono",
        help_text=(
            "Ingresá el código de área y el número, sin el 0 inicial "
            "ni el 15. Ejemplo: 388 4123456."
        ),
        widget=forms.TextInput(attrs={
            "class": ESTILO,
            "type": "tel",
            "placeholder": "Ej.: 388 4123456",
            "maxlength": 50,
        }),
    )

    class Meta:
        model = Proveedor
        fields = ["nombre", "telefono", "email", "materias_primas"]

        labels = {
            "nombre": "Nombre o razón social",
            "telefono": "Teléfono",
            "email": "Correo electrónico",
        }

        widgets = {
            "nombre": forms.TextInput(attrs={
                "class": ESTILO,
                "placeholder": "Ej: Finca Los Álamos"
            }),
            "email": forms.EmailInput(attrs={
                "class": ESTILO,
                "placeholder": "Ej.: proveedor@empresa.com",
                "maxlength": 254,
            }),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()

        repetido = Proveedor.objects.filter(
            nombre__iexact=nombre
        ).exclude(pk=self.instance.pk)

        if repetido.exists():
            raise forms.ValidationError(
                "Ya existe un proveedor con ese nombre."
            )

        return nombre

    def clean_telefono(self):
        telefono = (self.cleaned_data.get("telefono") or "").strip()

        if not telefono:
            return ""

        if telefono.startswith("-"):
            raise forms.ValidationError(
                "El teléfono no puede ser negativo."
            )

        if not re.fullmatch(r"\+?[0-9\s().-]+", telefono):
            raise forms.ValidationError(
                "Ingresá solamente números, espacios, paréntesis, "
                "guiones y el signo + al comienzo."
            )

        digitos = re.sub(r"\D", "", telefono)

        formatos_validos = (
            len(digitos) == 10
            or (len(digitos) == 11 and digitos.startswith("0"))
            or (len(digitos) == 12 and digitos.startswith("54"))
            or (len(digitos) == 13 and digitos.startswith("549"))
        )

        if not formatos_validos:
            raise forms.ValidationError(
                "El teléfono no tiene una longitud válida. "
                "Ingresá el código de área y el número."
            )

        return telefono


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["username"].label = "Usuario"
        self.fields["password"].label = "Contraseña"

        self.fields["username"].widget.attrs.update({
            "class": ESTILO,
            "placeholder": "Tu usuario",
            "autofocus": True,
            "autocomplete": "username"
        })

        self.fields["password"].widget.attrs.update({
            "class": ESTILO,
            "placeholder": "Tu contraseña",
            "autocomplete": "current-password"
        })
