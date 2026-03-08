###from django.db import models

# Create your models here.
###from django.db import models

##class Vehicle(models.Model):
###    number_plate = models.CharField(max_length=20, unique=True)
#    owner_name = models.CharField(max_length=100)
#    vehicle_type = models.CharField(max_length=50)
#    registration_date = models.DateField()
    
#    def __str__(self):
#        return self.number_plate


from django.db import models

class Vehicle(models.Model):
    plate_number = models.CharField(max_length=15, unique=True)
    owner_name = models.CharField(max_length=100)
    vehicle_type = models.CharField(max_length=50)
    registration_date = models.DateField()

    
    def __str__(self):
        return f"{self.plate_number} - {self.owner_name}"
