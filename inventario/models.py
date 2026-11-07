from django.db import models

# Create your models here.
class MateriaPrima(models.Model):
    UNIDADES = [
        ('KG', 'Kilogramos'),
        ('TN', 'Toneladas'),
        ('UN', 'Unidades'),
    ]

    nombre = models.CharField(max_length=100, help_text="Ej: Maíz Culli, Papa Oca, Quinoa")
    variedad = models.CharField(max_length=100, blank=True, null=True, help_text="Ej: Morado, Imilla, Amarilla")
    unidad_medida = models.CharField(max_length=2, choices=UNIDADES, default='KG')
    stock_actual = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2, default=10.00, help_text="Punto para alerta de desabastecimiento")

    class Meta:
        verbose_name = "Materia Prima"
        verbose_name_plural = "Materias Primas"

    def __str__(self):
        return f"{self.nombre} ({self.get_unidad_medida_display()})"