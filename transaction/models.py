from django.db import models
from master.models import CustomerMaster, SupplierMaster

# --- ABSTRACT BASE CLASSES (Common Fields) ---

class BaseTransactionHeader(models.Model):
    billno = models.BigIntegerField()
    billdate = models.DateField()
    purchase_order_no = models.CharField(max_length=100, blank=True, null=True)
    purchase_order_date = models.DateField(blank=True, null=True)
    dc_no = models.CharField(max_length=100, blank=True, null=True)
    dc_date = models.DateField(blank=True, null=True)
    no_of_package = models.CharField(max_length=50, blank=True, null=True)
    due_date = models.IntegerField(default=0) # Due Days

    # Billing Info
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    pin = models.CharField(max_length=10, blank=True, null=True)
    gst_number = models.CharField(max_length=20, blank=True, null=True)
    shipping_address = models.TextField(blank=True, null=True)

    # Financial Totals
    total_pcs = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    totalamount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00) # Taxable
    forwading_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    cgst = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    sgst = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    igst = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    round_off = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    grand_totamt = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    amtin_words = models.TextField(blank=True, null=True)

    accno = models.CharField(max_length=100, blank=True, null=True)
    delflag = models.CharField(max_length=1, default=' ')
    deldate = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True

class BaseTransactionDetail(models.Model):
    sno = models.IntegerField()
    product_name = models.CharField(max_length=255)
    uom = models.CharField(max_length=50)
    hsncode = models.CharField(max_length=50, blank=True, null=True)
    qty = models.DecimalField(max_digits=15, decimal_places=2)
    rate = models.DecimalField(max_digits=15, decimal_places=2)
    amount = models.DecimalField(max_digits=15, decimal_places=2) # Base Amount
    cgst = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    sgst = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    igst = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total = models.DecimalField(max_digits=15, decimal_places=2) # Row Total with Tax

    class Meta:
        abstract = True

# --- FINAL TABLES ---

class SalesHeader(BaseTransactionHeader):
    customer = models.ForeignKey(CustomerMaster, on_delete=models.CASCADE)

class SalesDetail(BaseTransactionDetail):
    header = models.ForeignKey(SalesHeader, related_name='details', on_delete=models.CASCADE)

class PurchaseHeader(BaseTransactionHeader):
    supplier = models.ForeignKey(SupplierMaster, on_delete=models.CASCADE)

class PurchaseDetail(BaseTransactionDetail):
    header = models.ForeignKey(PurchaseHeader, related_name='details', on_delete=models.CASCADE)