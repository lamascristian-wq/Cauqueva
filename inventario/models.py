from django.db import models

# Create your models here.
class MateriaPrima(models.Model):
    maizCulli = models.CharField(max_length=100) # ej: 
    stock_actual = models.DecimalField(max_digits=10, decimal_places=2) 
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2) 

    def __str__(self):
        return self.maizCulli