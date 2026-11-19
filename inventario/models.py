from django.db import models, router, transaction
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.db.models import F
from decimal import Decimal, ROUND_HALF_UP

class Proveedor(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(max_length=254, blank=True, verbose_name="Correo electrónico",)
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
    proveedor_externo = models.CharField(
        max_length=150, blank=True, null=True,
        help_text="Nombre de un proveedor que no está registrado en el sistema",
    )
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
    produccion = models.ForeignKey(
        "Produccion", on_delete=models.PROTECT, null=True, blank=True, related_name="consumos"
    )
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

class Producto(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    precio = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)],
        verbose_name="Precio de venta por unidad",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class IngredienteReceta(models.Model):
    """Cuánta materia prima (en Kg) gasta UNA unidad del producto."""
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="ingredientes")
    materia_prima = models.ForeignKey(MateriaPrima, on_delete=models.PROTECT)
    cantidad_por_unidad = models.DecimalField(
        max_digits=8, decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
        verbose_name="Kg de materia prima por unidad",
    )

    class Meta:
        unique_together = ("producto", "materia_prima")

    def __str__(self):
        return f"{self.producto}: {self.cantidad_por_unidad:g} Kg de {self.materia_prima}"


class Produccion(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="producciones")
    cantidad = models.PositiveIntegerField(
        validators=[MinValueValidator(1)], verbose_name="Cantidad producida"
    )
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)  # precio al momento de producir
    fecha = models.DateTimeField(default=timezone.now)
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "Producción"
        verbose_name_plural = "Producciones"

    def __str__(self):
        return f"{self.cantidad} × {self.producto}"

    @property
    def total(self):
        return (self.precio_unitario * self.cantidad).quantize(Decimal("0.01"))

    @classmethod
    def registrar(cls, producto, cantidad, fecha=None, observaciones=""):
        """Crea la producción y descuenta la materia prima de la receta.
        Todo o nada: si falta stock de algo, no se guarda nada."""
        ingredientes = list(producto.ingredientes.all())
        if not ingredientes:
            raise ValidationError(f"«{producto}» todavía no tiene una receta cargada.")

        with transaction.atomic():
            materias = {
                m.pk: m for m in MateriaPrima.objects.select_for_update().filter(
                    pk__in=[i.materia_prima_id for i in ingredientes]
                )
            }
            necesidades, faltantes = [], []
            for ing in ingredientes:
                materia = materias[ing.materia_prima_id]
                necesario = (ing.cantidad_por_unidad * cantidad).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                necesario = max(necesario, Decimal("0.01"))
                if necesario > materia.stock_actual:
                    faltantes.append(
                        f"Stock insuficiente de {materia}: se necesitan {necesario:g} Kg "
                        f"y hay {materia.stock_actual:g} Kg."
                    )
                necesidades.append((materia, necesario))
            if faltantes:
                raise ValidationError(faltantes)

            produccion = cls.objects.create(
                producto=producto, cantidad=cantidad, precio_unitario=producto.precio,
                fecha=fecha or timezone.now(), observaciones=observaciones or None,
            )
            for materia, necesario in necesidades:
                # El save() del movimiento descuenta el stock automáticamente
                MovimientoStock.objects.create(
                    materia_prima=materia, tipo="CONSUMO", cantidad=necesario,
                    fecha=produccion.fecha, produccion=produccion,
                    observaciones=f"Producción #{produccion.pk}: {cantidad} × {producto.nombre}",
                )
        return produccion, [m for m, _ in necesidades]
