from django.db import models

# Create your models here.
class ShopAdmin(models.Model):
    """
    Model representing a shop admin.
    """
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=100)

    def __str__(self):
        return self.username