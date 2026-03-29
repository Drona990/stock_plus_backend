from django.db import models
from django.utils import timezone

class BaseMaster(models.Model):
    # --- Primary ---
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True) # Optional
    mobile_no = models.CharField(max_length=15)
    city = models.CharField(max_length=100, blank=True, null=True)
    pin_code = models.CharField(max_length=10, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    gst_number = models.CharField(max_length=20, blank=True, null=True) # Optional
    
    # --- Banking (Naya Section) ---
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    account_no = models.CharField(max_length=50, blank=True, null=True)
    ifsc_code = models.CharField(max_length=20, blank=True, null=True)
    pan_no = models.CharField(max_length=15, blank=True, null=True)
    credit_days = models.IntegerField(default=30)

    # --- Ledger ---
    opening_balance_cr = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    opening_balance_dr = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    
    # --- Shipping (Optional) ---
    shipping_name = models.CharField(max_length=255, blank=True, null=True)
    shipping_address = models.TextField(blank=True, null=True)
    shipping_mobile_no = models.CharField(max_length=15, blank=True, null=True)
    shipping_city = models.CharField(max_length=100, blank=True, null=True)
    shipping_pin_code = models.CharField(max_length=10, blank=True, null=True)
    shipping_gst_no = models.CharField(max_length=20, blank=True, null=True)

    # --- System ---
    batch_number = models.CharField(max_length=50)
    mop = models.CharField(max_length=20, default='CASH')
    delflag = models.CharField(max_length=1, default=' ')
    deldate = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50, default='ADMIN')

    class Meta: abstract = True


class CustomerMaster(BaseMaster):
    customer_no = models.AutoField(primary_key=True) # Image: 131, 132...

    def __str__(self):
        return f"{self.name} ({self.customer_no})"

class SupplierMaster(BaseMaster):
    supplier_no = models.AutoField(primary_key=True)

    def __str__(self):
        return f"{self.name} ({self.supplier_no})"
    


class UOMMaster(models.Model):
    uom_name = models.CharField(max_length=50, unique=True) # e.g., PCS, KGS
    description = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.uom_name

    
#.........................................***......................................
#.........................................***......................................
