from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class Permiso(models.Model):

    modulo      = models.CharField(max_length=50)
    accion      = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('modulo', 'accion')
        db_table = 'permisos'

    def __str__(self):
        return f"{self.modulo} - {self.accion}"


class Rol(models.Model):
    nombre      = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activo      = models.BooleanField(default=True)
    
 
    permisos    = models.ManyToManyField(Permiso, blank=True, db_table='rol_permiso')

    class Meta:
        db_table = 'roles'

    def __str__(self):
        return self.nombre


class Usuario(AbstractUser):
    activo        = models.BooleanField(default=True)
    ultimo_acceso = models.DateTimeField(null=True, blank=True)
    
    roles         = models.ManyToManyField(Rol, blank=True, db_table='usuario_rol')

    class Meta:
        db_table = 'usuarios'

    def tiene_rol(self, nombre_rol):
        return self.roles.filter(nombre=nombre_rol).exists()

    def tiene_permiso(self, modulo, accion):

        return self.roles.filter(
            permisos__modulo=modulo,
            permisos__accion=accion
        ).exists()

    def __str__(self):
        return self.username