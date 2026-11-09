from django.db import models
from django.utils import timezone

# 1. Tabla de Materias Primas
class MateriaPrima(models.Model):
    nombre = models.CharField(max_length=100, help_text="Ej: Papa, Maíz, Apio")
    descripcion = models.CharField(max_length=255, blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Materia Prima"
        verbose_name_plural = "Materias Primas"

    def __str__(self):
        return self.nombre

# 2. Tabla de Variedades
class Variedad(models.Model):
    materia_prima = models.ForeignKey(MateriaPrima, on_delete=models.CASCADE)
    nombre = models.CharField(max_length=100, help_text="Ej: Morada, Blanca, Capia")
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Variedad"
        verbose_name_plural = "Variedades"
        # Regla de integridad: No pueden existir dos variedades con el mismo nombre para la misma papa
        unique_together = ('materia_prima', 'nombre') 

    def __str__(self):
        return f"{self.materia_prima.nombre} - {self.nombre}"

# 3. Tabla de Unidades de Medida
class UnidadMedida(models.Model):
    nombre = models.CharField(max_length=50, help_text="Ej: Kilogramo, Gramo")
    simbolo = models.CharField(max_length=10, unique=True, help_text="Ej: kg, g")
    factor_kg = models.DecimalField(max_digits=12, decimal_places=6, help_text="Equivalencia en kg (Ej: 1 para kg, 0.001 para g)")

    class Meta:
        verbose_name = "Unidad de Medida"
        verbose_name_plural = "Unidades de Medida"

    def __str__(self):
        return f"{self.nombre} ({self.simbolo})"

# 4. Tabla de Tipos de Movimiento
class TipoMovimiento(models.Model):
    # Efectos posibles: 1 (Suma) o -1 (Resta)
    EFECTOS = [
        (1, 'Suma (+1)'),
        (-1, 'Resta (-1)'),
    ]
    
    nombre = models.CharField(max_length=50, unique=True, help_text="Ej: Ingreso, Consumo, Merma")
    efecto_predeterminado = models.SmallIntegerField(choices=EFECTOS)

    class Meta:
        verbose_name = "Tipo de Movimiento"
        verbose_name_plural = "Tipos de Movimiento"

    def __str__(self):
        return f"{self.nombre} ({self.get_efecto_predeterminado_display()})"

# 5. Tabla Central de Movimientos
class Movimiento(models.Model):
    # Relaciones (Foreign Keys)
    materia_prima = models.ForeignKey(MateriaPrima, on_delete=models.PROTECT)
    variedad = models.ForeignKey(Variedad, on_delete=models.PROTECT, blank=True, null=True)
    unidad = models.ForeignKey(UnidadMedida, on_delete=models.PROTECT)
    tipo = models.ForeignKey(TipoMovimiento, on_delete=models.PROTECT)
    
    # Por ahora usaremos un campo de texto para el usuario hasta conectar el sistema de login
    usuario_registro = models.CharField(max_length=100, default="Admin") 
    
    # Datos de cantidad
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)
    cantidad_kg = models.DecimalField(max_digits=12, decimal_places=3, editable=False) # Se calculará solo
    efecto_stock = models.SmallIntegerField(editable=False) # Se tomará del tipo de movimiento
    
    # Datos de registro
    fecha = models.DateTimeField(default=timezone.now)
    observacion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Movimiento"
        verbose_name_plural = "Movimientos"
        ordering = ['-fecha'] # Ordenar del más reciente al más antiguo

    def save(self, *args, **kwargs):
        # ANTES de guardar en la base de datos, calculamos la cantidad en KG y el efecto automáticamente
        if self.unidad:
            self.cantidad_kg = self.cantidad * self.unidad.factor_kg
        if self.tipo:
            self.efecto_stock = self.tipo.efecto_predeterminado
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tipo.nombre} de {self.cantidad} {self.unidad.simbolo} de {self.materia_prima.nombre}"