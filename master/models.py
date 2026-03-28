from django.db import models
from django.utils import timezone

class CustomerMaster(models.Model):
    MOP_CHOICES = [
        ('CASH', 'Cash'),
        ('CREDIT', 'Credit'),
        ('RTGS', 'RTGS'),
        ('NEFT', 'NEFT'),
    ]
    
    STATE_CHOICES = [
        ('STATE', 'State'),
        ('INTERSTATE', 'Interstate'),
    ]

    # --- Basic Info ---
    customer_name = models.CharField(max_length=255)
    address = models.TextField()
    mobile = models.CharField(max_length=15)
    gst_no = models.CharField(max_length=20, unique=True)
    
    # --- Shipping Details ---
    shipping_name = models.CharField(max_length=255)
    shipping_address = models.TextField()
    shipping_gst_no = models.CharField(max_length=20, blank=True, null=True)

    # --- Accounts & Ledger ---
    mop = models.CharField(max_length=10, choices=MOP_CHOICES, default='CASH')
    state_type = models.CharField(max_length=15, choices=STATE_CHOICES, default='STATE')
    opening_cr = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    opening_dr = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    ledger_name = models.CharField(max_length=255, default='SALES / DEFAULT')

    # --- System Fields ---
    batch_no = models.CharField(max_length=50, unique=True) # Right side field in UI
    created_at = models.DateTimeField(auto_now_add=True)
    del_flag = models.CharField(max_length=1, default=' ') # ' ' for Active, 'D' for Deleted
    del_date = models.DateField(null=True, blank=True)
    created_by = models.CharField(max_length=50) # Supervisor/Manager/Staff

    def __str__(self):
        return f"{self.customer_name} - {self.batch_no}"
    



class SupplierMaster(models.Model):
    # Basic Info
    supplier_name = models.CharField(max_length=255)
    address = models.TextField()
    mobile = models.CharField(max_length=15)
    gst_no = models.CharField(max_length=20, unique=True)
    
    # Financial & Bank Details
    pan_no = models.CharField(max_length=15, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    account_no = models.CharField(max_length=50, blank=True, null=True)
    ifsc_code = models.CharField(max_length=20, blank=True, null=True)
    credit_days = models.IntegerField(default=30)
    
    # Ledger
    opening_cr = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    opening_dr = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    mop = models.CharField(max_length=20, default='CASH')
    
    # System
    batch_no = models.CharField(max_length=50)
    del_flag = models.CharField(max_length=1, default=' ')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=50, default='ADMIN')

    def __str__(self):
        return self.supplier_name