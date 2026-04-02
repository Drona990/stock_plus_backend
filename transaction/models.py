from django.db import models
from master.models import CustomerMaster, SupplierMaster
from django.utils import timezone
import string
import random

# --- ABSTRACT BASE CLASSES (Common Fields) ---

def generate_bill_no():
    prefix = "INV"
    year = timezone.now().year
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}-{year}-{random_str}"

class BaseTransactionHeader(models.Model):
    billno = models.CharField(
        max_length=50, 
        unique=True, 
        default=generate_bill_no, 
        editable=False
    )
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



#---------------------------------***----------------------------------------------------

class BaseLedger(models.Model):
    # Image ke exact fields
    tranno = models.AutoField(primary_key=True)               # TRANNO (Auto Increment)
    trdate = models.DateField(default=timezone.now)           # TRDATE (Today's Date)
    invtype = models.CharField(max_length=20)
    invno = models.CharField(max_length=50) 
    invdate = models.DateField()                          # INVDATE (Bill Date)
    inname = models.CharField(max_length=255)                 # INNAME (Party Name)
    inaddress = models.TextField(blank=True, null=True)       # INADDRESS (Party Address)
    invgst = models.CharField(max_length=20, blank=True, null=True) # INVGST (Party GST)
    
    # Accounting (Debit/Credit)
    trcr = models.DecimalField(max_digits=15, decimal_places=2, default=0.00) # TRCR
    trdr = models.DecimalField(max_digits=15, decimal_places=2, default=0.00) # TRDR
    ctype = models.CharField(max_length=10)                   # CTYPE (To / By)
    
    # Flags
    delflag = models.CharField(max_length=1, default=' ')     # DELFLAG
    deldate = models.DateField(null=True, blank=True)         # DELDATE

    class Meta:
        abstract = True

# --- FINAL SEPARATE TABLES ---

class SalesLedger(BaseLedger):
    class Meta:
        verbose_name = "Sales Ledger"
        verbose_name_plural = "Sales Ledgers"

class PurchaseLedger(BaseLedger):
    class Meta:
        verbose_name = "Purchase Ledger"
        verbose_name_plural = "Purchase Ledgers"



#---------------------------------***----------------------------------------------------


class CashTransaction(models.Model):
    VOUCHER_TYPES = (
        ('RECEIPT', 'Receipt'),
        ('PAYMENT', 'Payment'),
    )

    # Auto-incrementing Voucher Number
    voucher_no = models.AutoField(primary_key=True)
    
    # Sahi tarika date default set karne ka
    date = models.DateField(default=timezone.now) 
    
    # Ledger ke sath connection
    ledger = models.ForeignKey(
        'master.Ledger', 
        on_delete=models.PROTECT, 
        related_name='transactions'
    )
    
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    voucher_type = models.CharField(max_length=10, choices=VOUCHER_TYPES)
    narration = models.TextField(blank=True, null=True)
    
    # Audit Fields
    created_at = models.DateTimeField(auto_now_add=True)
    # Isse pata chalega kisne entry ki
    created_by = models.CharField(max_length=100, default='ADMIN', editable=False)

    class Meta:
        ordering = ['-date', '-voucher_no']
        verbose_name = "Cash Transaction"
        verbose_name_plural = "Cash Transactions"

    def __str__(self):
        return f"{self.voucher_type} #{self.voucher_no} - {self.ledger.name}"