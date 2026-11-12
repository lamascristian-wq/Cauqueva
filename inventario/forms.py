from django import forms
from django.utils import timezone
from django.contrib.auth.forms import AuthenticationForm
from .models import MateriaPrima, MovimientoStock, Proveedor

ESTILO = (
    "w-full rounded-lg border border-gray-300 px-3 py-2 text-sm "
    "focus:outline-none focus:ring-2 focus:ring-green-600 focus:border-green-600"
)

class MateriaPrimaForm(forms.ModelForm):
    stock_inicial = forms.DecimalField(
        label="Stock inicial",
        required=False,
        initial=0,
        min_value=0,
        max_digits=10,
        decimal_places=2,
        help_text="Cantidad que hay hoy en el depósito. Si no hay nada, dejalo en 0.",
        widget=forms.NumberInput(attrs={"class": ESTILO, "step": "0.01", "min": "0"}),
    )

    class Meta:
        model = MateriaPrima
        fields = ["nombre", "variedad", "unidad_medida", "descripcion", "stock_minimo"]
        labels = {
            "nombre": "Nombre",
            "variedad": "Variedad",
            "unidad_medida": "Unidad de medida",
            "descripcion": "Descripción",
            "stock_minimo": "Stock mínimo",
        }
        help_texts = {
            "stock_minimo": "Por debajo de esta cantidad se genera una alerta crítica.",
        }
        widgets = {
            "nombre": forms.TextInput(attrs={"class": ESTILO, "placeholder": "Ej: Papa, Maíz, Apio"}),
            "variedad": forms.TextInput(attrs={"class": ESTILO, "placeholder": "Ej: Andina (opcional)"}),
            "unidad_medida": forms.Select(attrs={"class": ESTILO}),
            "descripcion": forms.Textarea(attrs={"class": ESTILO, "rows": 3}),
            "stock_minimo": forms.NumberInput(attrs={"class": ESTILO, "step": "0.01", "min": "0"}),
        }

    def clean(self):
        datos = super().clean()
        nombre = (datos.get("nombre") or "").strip()
        variedad = (datos.get("variedad") or "").strip()
        if nombre:
            repetida = MateriaPrima.objects.filter(
                nombre__iexact=nombre, variedad__iexact=variedad
            ).exists()
            if repetida:
                raise forms.ValidationError(
                    "Ya existe una materia prima con ese nombre y esa variedad."
                )
        return datos

class MovimientoStockForm(forms.ModelForm):
    class Meta:
        model = MovimientoStock
        fields = ['materia_prima', 'tipo', 'cantidad', 'proveedor', 'observaciones']
        labels = {
            'materia_prima': 'Materia Prima a Registrar',
            'tipo': 'Tipo de Operación',
            'cantidad': 'Cantidad (Kg)',
            'proveedor': 'Proveedor / Productor (Solo para Ingresos)',
            'observaciones': 'Observaciones Adicionales',
        }
        widgets = {
            'materia_prima': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:ring-green-500 focus:border-green-500'}),
            'tipo': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:ring-green-500 focus:border-green-500'}),
            'cantidad': forms.NumberInput(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:ring-green-500 focus:border-green-500'}),
            'proveedor': forms.Select(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:ring-green-500 focus:border-green-500'}),
            'observaciones': forms.Textarea(attrs={'class': 'w-full p-2 border border-gray-300 rounded focus:ring-green-500 focus:border-green-500', 'rows': 3}),
        }

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
        fields = ["nombre", "telefono"]
        labels = {"nombre": "Nombre o razón social", "telefono": "Teléfono"}
        widgets = {
            "nombre": forms.TextInput(attrs={"class": ESTILO, "placeholder": "Ej: Finca Los Álamos"}),
            "telefono": forms.TextInput(attrs={"class": ESTILO, "placeholder": "Ej: 388 4123456 (opcional)"}),
        }

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
        