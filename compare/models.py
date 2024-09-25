from django.db import models

class Supermarket(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100)  # Optional: If you want to track different store locations
    
    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100)  # e.g., Dairy, Meat, Produce, etc.

    def __str__(self):
        return self.name

class Price(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    supermarket = models.ForeignKey(Supermarket, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    date = models.DateField()  # Optional: Track when this price was available
    
    def __str__(self):
        return f'{self.product.name} - {self.supermarket.name} - {self.price}'

class Offer(models.Model):
    price = models.ForeignKey(Price, on_delete=models.CASCADE)
    discount = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    details = models.TextField(null=True, blank=True)  # Description of the offer

    def __str__(self):
        return f'Offer for {self.price.product.name} at {self.price.supermarket.name}'
