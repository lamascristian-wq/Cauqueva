from django import forms
from .models import MateriaPrima

class MateriaPrimaForm(forms.ModelForm):
    class Meta:
        model = MateriaPrima
        # Indicamos qué campos queremos que llene el trabajador
        fields = ['nombre', 'variedad', 'unidad_medida', 'stock_actual', 'stock_minimo']
        
        # Le agregamos las clases 'form-control' de Bootstrap para que se vean bonitos
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Papa Oca'}),
            'variedad': forms.TextInput(attrs={'class': 'form-control'}),
            'unidad_medida': forms.Select(attrs={'class': 'form-select'}),
            'stock_actual': forms.NumberInput(attrs={'class': 'form-control'}),
            'stock_minimo': forms.NumberInput(attrs={'class': 'form-control'}),
        }