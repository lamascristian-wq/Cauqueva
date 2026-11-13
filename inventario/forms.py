from django import forms
from django.utils import timezone
from django.contrib.auth.forms import AuthenticationForm
from .models import MateriaPrima, MovimientoStock, Proveedor

ESTILO = (
    "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-green-600 focus:border-green-600"
)

class MateriaPrimaForm(forms.ModelForm):
    class Meta:
        model = MateriaPrima
        fields = ["nombre", "variedad", "unidad_medida", "descripcion"]
        labels = {
            "nombre": "Nombre",
            "variedad": "Variedad",
            "unidad_medida": "Unidad de medida",
            "descripcion": "Descripción",
        }
        widgets = {
            "nombre": forms.TextInput(attrs={"class": ESTILO, "placeholder": "Ej: Papa, Maíz, Apio"}),
            "variedad": forms.TextInput(attrs={"class": ESTILO, "placeholder": "Ej: Andina (opcional)"}),
            "unidad_medida": forms.Select(attrs={"class": ESTILO}),
            "descripcion": forms.Textarea(attrs={"class": ESTILO, "rows": 3}),
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
        fields = ["materia_prima", "proveedor", "cantidad", "observaciones"]
        labels = {
            "materia_prima": "Materia prima",
            "proveedor": "Proveedor / Productor",
            "cantidad": "Cantidad que ingresa",
            "observaciones": "Observaciones",
        }
        widgets = {
            "materia_prima": forms.Select(attrs={"class": ESTILO}),
            "proveedor": forms.Select(attrs={"class": ESTILO}),
            "cantidad": forms.NumberInput(attrs={"class": ESTILO, "step": "0.01", "min": "0.01"}),
            "observaciones": forms.Textarea(attrs={"class": ESTILO, "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.tipo = "INGRESO"
        self.fields["proveedor"].required = True
        self.fields["proveedor"].empty_label = "Seleccioná un proveedor"
        self.fields["materia_prima"].queryset = MateriaPrima.objects.order_by("nombre")
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
        # El tipo no se elige: acá todo es consumo. Se fija antes de validar
        # para que el clean() del modelo controle el stock disponible.
        self.instance.tipo = "CONSUMO"
        self.fields["materia_prima"].queryset = self.fields["materia_prima"].queryset.order_by("nombre")        
        
class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ["nombre", "telefono", "materias_primas"]
        labels = {
            "nombre": "Nombre o razón social",
            "telefono": "Teléfono",
            "materias_primas": "Materias primas que provee",
        }
        help_texts = {
            "materias_primas": "Marcá todas las que suele entregar. Podés cambiarlo más adelante.",
        }
        widgets = {
            "nombre": forms.TextInput(attrs={"class": ESTILO, "placeholder": "Ej: Finca Los Álamos"}),
            "telefono": forms.TextInput(attrs={"class": ESTILO, "placeholder": "Ej: 388 4123456 (opcional)"}),
            "materias_primas": forms.CheckboxSelectMultiple(
                attrs={"class": "h-4 w-4 rounded border-gray-300 text-green-700 focus:ring-green-600"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["materias_primas"].queryset = MateriaPrima.objects.order_by("nombre")

    def clean_nombre(self):
        nombre = self.cleaned_data["nombre"].strip()
        repetido = Proveedor.objects.filter(nombre__iexact=nombre).exclude(pk=self.instance.pk)
        if repetido.exists():
            raise forms.ValidationError("Ya existe un proveedor con ese nombre.")
        return nombre       
        
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
        