from django.db import models, router, transaction
from django.db.models.signals import pre_delete
from django.dispatch import receiver
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
    # Precio estimado usado como sugerencia al registrar un ingreso.
    precio_referencia = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0.00)],
        verbose_name="Precio de referencia",
    )
    
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
    # Conserva el precio efectivamente informado para cada movimiento.
    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0.00)],
        verbose_name="Precio unitario",
    )
    fecha = models.DateTimeField(default=timezone.now)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Movimiento de Stock"
        verbose_name_plural = "Historial de Movimientos"
        ordering = ['-fecha'] # Ordena automáticamente del más nuevo al más viejo

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.materia_prima} ({self.cantidad} {self.materia_prima.unidad_medida})"

    @property
    def costo_total(self):
        """Calcula el costo del movimiento con el precio unitario registrado."""
        return self.cantidad * self.precio_unitario
    
    def clean(self):
        # No permitir consumir más de lo que hay en stock
        if self.tipo == 'CONSUMO' and self.materia_prima_id and self.pk is None:
            if self.cantidad is not None and self.cantidad > self.materia_prima.stock_actual:
                raise ValidationError(
                    f"Stock insuficiente: hay {self.materia_prima.stock_actual} "
                    f"{self.materia_prima.unidad_medida} disponibles."
                )

    def _delta(self):
        return self._stock_delta(self.tipo, self.cantidad)

    @staticmethod
    def _stock_delta(tipo, cantidad):
        if cantidad is None or cantidad <= 0:
            raise ValidationError({"cantidad": "La cantidad debe ser mayor que cero."})
        if tipo == "INGRESO":
            return cantidad
        if tipo == "CONSUMO":
            return -cantidad
        raise ValidationError({"tipo": "El tipo de movimiento no es válido."})

    @staticmethod
    def _aplicar_delta_stock(materia_prima_id, tipo, cantidad, using):
        MovimientoStock._stock_delta(tipo, cantidad)
        materias = MateriaPrima.objects.using(using).filter(pk=materia_prima_id)
        if tipo == "INGRESO":
            materias.update(stock_actual=F("stock_actual") + cantidad)
            return

        actualizadas = materias.filter(stock_actual__gte=cantidad).update(
            stock_actual=F("stock_actual") - cantidad
        )
        if not actualizadas:
            raise ValidationError(
                {"cantidad": "Stock insuficiente para registrar este consumo."}
            )

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            kwargs["update_fields"] = update_fields

        stock_fields = {"materia_prima", "materia_prima_id", "tipo", "cantidad"}
        with transaction.atomic(using=using):
            anterior = None
            if self.pk is not None:
                anterior = (
                    type(self).objects.using(using)
                    .select_for_update()
                    .filter(pk=self.pk)
                    .first()
                )

            if (
                anterior is not None
                and update_fields is not None
                and not stock_fields.intersection(update_fields)
            ):
                return super().save(*args, **kwargs)

            if anterior is not None and update_fields is not None:
                materia_prima_id = (
                    self.materia_prima_id
                    if {"materia_prima", "materia_prima_id"}.intersection(update_fields)
                    else anterior.materia_prima_id
                )
                tipo = self.tipo if "tipo" in update_fields else anterior.tipo
                cantidad = self.cantidad if "cantidad" in update_fields else anterior.cantidad
            else:
                materia_prima_id = self.materia_prima_id
                tipo = self.tipo
                cantidad = self.cantidad

            self._stock_delta(tipo, cantidad)
            ids_materias = {materia_prima_id}
            if anterior is not None:
                ids_materias.add(anterior.materia_prima_id)
            list(
                MateriaPrima.objects.using(using)
                .select_for_update()
                .filter(pk__in=ids_materias)
                .order_by("pk")
            )

            if anterior is not None:
                MateriaPrima.objects.using(using).filter(
                    pk=anterior.materia_prima_id
                ).update(stock_actual=F("stock_actual") - anterior._delta())

            super().save(*args, **kwargs)
            self._aplicar_delta_stock(materia_prima_id, tipo, cantidad, using)


@receiver(pre_delete, sender=MovimientoStock)
def revertir_stock_al_eliminar_movimiento(sender, instance, using, **kwargs):
    MateriaPrima.objects.using(using).filter(
        pk=instance.materia_prima_id
    ).update(stock_actual=F("stock_actual") - instance._delta())