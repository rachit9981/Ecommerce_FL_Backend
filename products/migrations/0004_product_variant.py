# Generated by Django 5.1.4 on 2025-05-26 06:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0003_cart_order_orderitem_cartitem_wishlist'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='variant',
            field=models.JSONField(default=dict),
        ),
    ]
