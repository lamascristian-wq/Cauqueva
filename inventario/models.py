from django.db import models,transaction
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.db.models import F

class Proveedor(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    materias_primas = models.ManyToManyField(
        "MateriaPrima",
        blank=True,
        related_name="proveedores",
        verbose_name="Materias primas que provee",
    )

    def __str__(self):
        return self.nombre

#Tabla de Materias Primas
class MateriaPrima(models.Model):
    UNIDADES = [
        ('KG', 'Kilogramos'),
        ('TN', 'Toneladas'),
        ('UN', 'Unidades'),
    ]
    nombre = models.CharField(max_length=100)
    unidad_medida = models.CharField(max_length=2, choices=UNIDADES, default='KG')
    descripcion = models.CharField(max_length=255, blank=True, null=True)
    stock_actual = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0.00)])
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2, default=50.00, verbose_name="Stock Mínimo (kg)")
    variedad = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = "Materia Prima"
        verbose_name_plural = "Materias Primas"

    def __str__(self):
        variedad_str = f" - {self.variedad}" if self.variedad else ""
        return f"{self.nombre}{variedad_str}"


class MovimientoStock(models.Model):
    TIPO_CHOICES = [
        ('INGRESO', 'Ingreso de Materia Prima'),
        ('CONSUMO', 'Consumo en Producción'),
    ]
    materia_prima = models.ForeignKey(MateriaPrima, on_delete=models.CASCADE)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)
    # RESTRICCIONES
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    fecha = models.DateTimeField(default=timezone.now)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Movimiento de Stock"
        verbose_name_plural = "Historial de Movimientos"
        ordering = ['-fecha'] # Ordena automáticamente del más nuevo al más viejo

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.materia_prima} ({self.cantidad} {self.materia_prima.unidad_medida})"

    def clean(self):
        # No permitir consumir más de lo que hay en stock
        if self.tipo == 'CONSUMO' and self.materia_prima_id and self.pk is None:
            if self.cantidad is not None and self.cantidad > self.materia_prima.stock_actual:
                raise ValidationError(
                    f"Stock insuficiente: hay {self.materia_prima.stock_actual} "
                    f"{self.materia_prima.unidad_medida} disponibles."
                )

    def _delta(self):
        return self.cantidad if self.tipo == 'INGRESO' else -self.cantidad

    def save(self, *args, **kwargs):
        es_nuevo = self.pk is None

        with transaction.atomic():
            super().save(*args, **kwargs)

            if es_nuevo:
                MateriaPrima.objects.filter(pk=self.materia_prima_id).update(
                    stock_actual=F('stock_actual') + self._delta()
                )

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            MateriaPrima.objects.filter(pk=self.materia_prima_id).update(
                stock_actual=F('stock_actual') - self._delta()
            )
            super().delete(*args, **kwargs)
