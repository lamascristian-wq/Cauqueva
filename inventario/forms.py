from django import forms
from .models import Movimiento

class MovimientoForm(forms.ModelForm):
    class Meta:
        model = Movimiento
        fields = ['materia_prima', 'variedad', 'unidad', 'tipo', 'cantidad', 'observacion']
        widgets = {
            'materia_prima': forms.Select(attrs={'class': 'form-select'}),
            'variedad': forms.Select(attrs={'class': 'form-select'}),
            'unidad': forms.Select(attrs={'class': 'form-select'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control'}),
            'observacion': forms.TextInput(attrs={'class': 'form-control'}),
        }

    # Esta función intercepta los datos antes de guardarlos en la base de datos
    def clean(self):
        # 1. Recuperamos los datos que el usuario escribió
        cleaned_data = super().clean()
        materia = cleaned_data.get('materia_prima')
        variedad = cleaned_data.get('variedad')
        unidad = cleaned_data.get('unidad')
        tipo = cleaned_data.get('tipo')
        cantidad = cleaned_data.get('cantidad')

        # 2. Si todos los datos requeridos están presentes, verificamos el stock
        if materia and unidad and tipo and cantidad:
            
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