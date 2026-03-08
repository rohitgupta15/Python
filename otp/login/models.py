from django.db import models

# Create your models here.

class Receipe(models.Model):
    receipe_name = models.CharField(max_length=100)
    receipe_desc = models.TextField()
    receipe_img = models.ImageField(upload_to="receipe")
    


class Reg(models.Model):
    first = models.TextField(max_length=100)
    last = models.TextField(max_length=100)
    email = models.EmailField(max_length=50)
    password = models.CharField(max_length=20)
    contact = models.IntegerField()
    gender = models.CharField(max_length=50)