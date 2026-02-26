from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator

class Location(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "Locations"
        ordering = ['name']

    def __str__(self):
        return self.name


class InventoryCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name_plural = "Inventory Categories"

    def __str__(self):
        return self.name
    

class ProductGroup(models.Model):
    # Group Name (Image ke hisaab se)
    name = models.CharField(max_length=100, unique=True)
    
    # HSN Code
    hsn_code = models.CharField(max_length=20, blank=True, null=True)
    
    # Updated Tax Fields (SGST instead of KGST)
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    igst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Product Groups"

    def __str__(self):
        return self.name
    

class ProductSubGroup(models.Model):
    group = models.ForeignKey(
        'ProductGroup', 
        on_delete=models.CASCADE, 
        related_name='subgroups'
    )
    
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name_plural = "Sub Masters"
        unique_together = ('group', 'name')

    def __str__(self):
        return f"{self.group.name} - {self.name}"
    



class StockTransaction(models.Model):
    group = models.ForeignKey('ProductGroup', on_delete=models.PROTECT)
    sub_group = models.ForeignKey('ProductSubGroup', on_delete=models.PROTECT)
    location = models.ForeignKey('Location', on_delete=models.PROTECT, null=True, blank=True)
    
    # Stock Details
    no_of_pieces = models.IntegerField() 
    pcs_per_unit = models.IntegerField(default=1)  # e.g., 1 (for single) or 2 (for pair)
    
    price_with_gst = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    sgst_rate = models.DecimalField(max_digits=5, decimal_places=2)
    cgst_rate = models.DecimalField(max_digits=5, decimal_places=2)
    igst_rate = models.DecimalField(max_digits=5, decimal_places=2)
    hsn_code = models.CharField(max_length=20)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Batch {self.id} - {self.sub_group.name}"

class GeneratedBarcode(models.Model):
    transaction = models.ForeignKey(StockTransaction, related_name='barcodes', on_delete=models.CASCADE)
    barcode_value = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.barcode_value
    

class SaleHeader(models.Model):
    bill_no = models.CharField(max_length=50, unique=True)
    bill_date = models.DateTimeField(auto_now_add=True)
    sold_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='sales'
    )
    
    location = models.ForeignKey(
        'inventory.Location', 
        on_delete=models.PROTECT, 
        null=True, 
        related_name='sales'
    )
    customer_name = models.CharField(max_length=100, default="CASH")
    customer_mobile = models.CharField(max_length=15, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_mode = models.CharField(max_length=20, default="CASH")
    freight_charge = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00, 
        null=True, 
        blank=True
    )

    def __str__(self):
        return f"Bill {self.bill_no} - {self.customer_name}"

class SaleItem(models.Model):
    sale = models.ForeignKey(SaleHeader, related_name='items', on_delete=models.CASCADE)
    barcode = models.OneToOneField('GeneratedBarcode', on_delete=models.PROTECT) 
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    cgst_amt = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    sgst_amt = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    igst_amt = models.DecimalField(max_digits=10, decimal_places=2, default=0)