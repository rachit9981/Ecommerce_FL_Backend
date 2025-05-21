from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount = models.CharField(max_length=10, null=True, blank=True)
    rating = models.FloatField(null=True, blank=True)
    reviews = models.IntegerField(null=True, blank=True)
    stock = models.IntegerField()
    variant = models.JSONField(default=dict)
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

class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled')
    )
    
    user_id = models.IntegerField()  # Foreign key to user model
    order_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    shipping_address = models.TextField()
    billing_address = models.TextField()
    payment_method = models.CharField(max_length=50)
    payment_status = models.CharField(max_length=20, default='pending')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    tracking_number = models.CharField(max_length=100, null=True, blank=True)
    
    def __str__(self):
        return f"Order #{self.id} - {self.status}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Price at time of purchase
    
    def __str__(self):
        return f"{self.quantity}x {self.product.name} in Order #{self.order.id}"
    
    @property
    def subtotal(self):
        return self.price * self.quantity

class Wishlist(models.Model):
    user_id = models.IntegerField()  # Foreign key to user model
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    date_added = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user_id', 'product')  # Prevent duplicate wishlist entries
    
    def __str__(self):
        return f"Wishlist item for user {self.user_id} - {self.product.name}"

class Cart(models.Model):
    user_id = models.IntegerField()  # Foreign key to user model
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Cart #{self.id} - User {self.user_id}"
    
    @property
    def total(self):
        cart_items = self.items.all()
        return sum(item.subtotal for item in cart_items)
    
    @property
    def item_count(self):
        cart_items = self.items.all()
        return sum(item.quantity for item in cart_items)


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    date_added = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('cart', 'product')  # Prevent duplicate cart items
    
    def __str__(self):
        return f"{self.quantity}x {self.product.name} in Cart #{self.cart.id}"
    
    @property
    def subtotal(self):
        return self.product.price * self.quantity
