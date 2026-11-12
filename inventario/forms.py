from django import forms
from .models import Movimiento

class MovimientoForm(forms.ModelForm):
    class Meta:
        model = Movimiento
        fields = ['materia_prima', 'variedad', 'unidad', 'tipo', 'cantidad', 'observacion']
        widgets = {
            'materia_prima': forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_materia_prima',
            }),
            'variedad': forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_variedad',
            }),
            'unidad': forms.Select(attrs={'class': 'form-select'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': 'any',}),
            'observacion': forms.TextInput(attrs={'class': 'form-control'}),
        }


    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        unidad = self.cleaned_data.get('unidad')

        if cantidad is not None and unidad is not None:
            cantidad_en_kg = cantidad * unidad.factor_kg

            if cantidad_en_kg < 1:
                raise forms.ValidationError(
                    "La cantidad mínima por movimiento es 1 kg. "
                    "Revisá la cantidad y la unidad seleccionada."
                )

        return cantidad
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['cantidad'].error_messages['max_decimal_places'] = (
            "La cantidad admite como máximo 3 decimales."
        )

    # Esta función intercepta los datos antes de guardarlos en la base de datos
    def clean(self):
        # 1. Recuperamos los datos que el usuario escribió
        cleaned_data = super().clean()
        materia = cleaned_data.get('materia_prima')
        variedad = cleaned_data.get('variedad')
        unidad = cleaned_data.get('unidad')
        tipo = cleaned_data.get('tipo')
        cantidad = cleaned_data.get('cantidad')

        # Comprobar que la variedad pertenezca a la materia prima
        if materia and variedad:
            if variedad.materia_prima_id != materia.id:
                self.add_error(
                    'variedad',
                    'La variedad seleccionada no pertenece a la materia prima elegida.'
                )

        # 2. Si todos los datos requeridos están presentes, verificamos el stock
        if materia and unidad and tipo and cantidad and not self.has_error('variedad'):
            
            # Solo validamos si es un movimiento de salida (efecto -1)
            if tipo.efecto_predeterminado == -1:
                cantidad_a_restar = cantidad * unidad.factor_kg
                
                # Calculamos el stock actual de esa materia/variedad específica
                if variedad:
                    movs = Movimiento.objects.filter(materia_prima=materia, variedad=variedad)
                else:
                    movs = Movimiento.objects.filter(materia_prima=materia, variedad__isnull=True)
                    
                stock_actual = sum(m.cantidad_kg * m.efecto_stock for m in movs)

                # 3. Si intentan restar más de lo que hay, bloqueamos con un error
                if cantidad_a_restar > stock_actual:
                    # self.add_error muestra el mensaje rojo debajo del campo específico
                    self.add_error(
                        'cantidad', 
                        f"Stock insuficiente. Tienes {stock_actual:.2f} kg disponibles, pero intentas registrar una salida de {cantidad_a_restar:.2f} kg."
                    )
        
        return cleaned_data