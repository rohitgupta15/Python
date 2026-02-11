from django.db import models


class Payment(models.Model):
    payer_name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=30, blank=True)
    reference = models.CharField(max_length=50, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-received_at']

    def __str__(self) -> str:
        return f"{self.payer_name} - {self.amount}"

# Create your models here.
