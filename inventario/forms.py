from django import forms
from django.utils import timezone
from django.contrib.auth.forms import AuthenticationForm
from .models import MateriaPrima, MovimientoStock, Proveedor
from django.db.models import Q
import re

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
    class Meta:
        model = MateriaPrima
        # El precio de referencia queda disponible para sugerirlo en futuros ingresos.
        fields = ["nombre", "variedad", "unidad_medida", "precio_referencia", "descripcion"]
        labels = {
            "nombre": "Nombre",
            "variedad": "Variedad",
            "unidad_medida": "Unidad de medida",
            "precio_referencia": "Precio de referencia por unidad",
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
        if nombre:
            repetidas = MateriaPrima.objects.filter(nombre__iexact=nombre)
            if variedad:
                repetidas = repetidas.filter(variedad__iexact=variedad)
            else:
                repetidas = repetidas.filter(Q(variedad__isnull=True) | Q(variedad=""))
            if repetidas.exists():
                raise forms.ValidationError(
                    "Ya existe una materia prima con ese nombre y esa variedad."
                )
        return datos

class MovimientoStockForm(forms.ModelForm):
    """Registro de ingresos: el tipo siempre es INGRESO y suma al stock."""

    class Meta:
        model = MovimientoStock
        # Guarda el precio efectivo de la compra junto con la cantidad ingresada.
        fields = ["materia_prima", "proveedor", "cantidad", "precio_unitario", "observaciones"]
        labels = {
            "materia_prima": "Materia prima",
            "proveedor": "Proveedor / Productor",
            "cantidad": "Cantidad que ingresa",
            "precio_unitario": "Precio unitario",
            "observaciones": "Observaciones",
        }
        widgets = {
            "materia_prima": PrecioReferenciaSelect(attrs={"class": ESTILO}),
            "proveedor": forms.Select(attrs={"class": ESTILO}),
            "cantidad": forms.NumberInput(attrs={"class": ESTILO, "step": "0.01", "min": "0.01"}),
            "precio_unitario": forms.NumberInput(
                attrs={"class": ESTILO, "step": "0.01", "min": "0"}
            ),
            "observaciones": forms.Textarea(attrs={"class": ESTILO, "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance._state.adding:
            self.instance.tipo = "INGRESO"
        self.fields["proveedor"].required = self.instance.tipo == "INGRESO"
        if self.instance.tipo == "CONSUMO":
            self.fields["cantidad"].label = "Cantidad consumida"
        self.fields["proveedor"].empty_label = "Seleccioná un proveedor"
        self.fields["materia_prima"].queryset = MateriaPrima.objects.order_by(
            "nombre", "variedad"
        )
        # Muestra la unidad y el stock actual en el desplegable
        self.fields["materia_prima"].label_from_instance = (
            lambda m: f"{m} ({m.get_unidad_medida_display()}) · stock: {m.stock_actual:g}"
        )

class ConsumoForm(forms.ModelForm):
    fecha = forms.DateTimeField(
        label="Fecha y hora",
        initial=timezone.now,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": ESTILO},
            format="%Y-%m-%dT%H:%M",
        ),
    )

    class Meta:
        model = MovimientoStock
        fields = ["materia_prima", "cantidad", "fecha", "observaciones"]
        labels = {
            "materia_prima": "Materia prima",
            "cantidad": "Cantidad consumida",
            "observaciones": "Observaciones",
        }
        widgets = {
            "materia_prima": forms.Select(attrs={"class": ESTILO}),
            "cantidad": forms.NumberInput(attrs={"class": ESTILO, "step": "0.01", "min": "0.01"}),
            "observaciones": forms.Textarea(
                attrs={"class": ESTILO, "rows": 3, "placeholder": "Ej: Lote de producción del día (opcional)"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.tipo = "CONSUMO"
        self.fields["materia_prima"].queryset = self.fields["materia_prima"].queryset.order_by("nombre")


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
        self.fields["username"].widget.attrs.update(
            {"class": ESTILO, "placeholder": "Tu usuario", "autofocus": True, "autocomplete": "username"}
        )
        self.fields["password"].widget.attrs.update(
            {"class": ESTILO, "placeholder": "Tu contraseña", "autocomplete": "current-password"}
        )