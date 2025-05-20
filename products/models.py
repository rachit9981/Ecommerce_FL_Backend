from django.db import models

# Create your models here.

class Product(models.Model):
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount = models.CharField(max_length=10, null=True, blank=True)
    rating = models.FloatField(null=True, blank=True)
    reviews = models.IntegerField(null=True, blank=True)
    stock = models.IntegerField()
    category = models.CharField(max_length=255)
    brand = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    images = models.JSONField(default=list)
    features = models.JSONField(default=list)
    specifications = models.JSONField(default=dict)

    def __str__(self):
        return self.name

class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_reviews')
    title = models.CharField(max_length=255,blank=True, null=True)
    user_name = models.CharField(max_length=255)
    rating = models.FloatField()
    comment = models.TextField()
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.user_name} - {self.product.name}"
