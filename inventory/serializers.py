
from num2words import num2words
import traceback
from rest_framework import serializers
from .models import InventoryCategory, ItemLocation, ProductSubGroup, SaleHeader, SaleItem, Location
from .models import ProductGroup , StockTransaction, GeneratedBarcode
import random
from django.db import transaction
import logging
logger = logging.getLogger(__name__)


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'name']


class ItemLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemLocation
        fields = ['id', 'name']


class InventoryCategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(source='inventory_products.count', read_only=True)

    class Meta:
        model = InventoryCategory
        fields = ['id', 'name', 'description', 'product_count']


class ProductGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductGroup
        fields = ['id', 'name', 'hsn_code', 'sgst_rate', 'cgst_rate', 'igst_rate', 'description']

class ProductSubGroupSerializer(serializers.ModelSerializer):
    group_name = serializers.ReadOnlyField(source='group.name')
    class Meta:
        model = ProductSubGroup
        fields = ['id', 'group', 'group_name', 'name']

class GeneratedBarcodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedBarcode
        fields = ['id', 'barcode_value', 'is_active']

# ==========================================================================
# 2. STOCK SERIALIZERS
# ==========================================================================

class StockTransactionSerializer(serializers.ModelSerializer):
    barcode_list = serializers.SerializerMethodField()
    formatted_date = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %I:%M %p", read_only=True)

    class Meta:
        model = StockTransaction
        fields = '__all__'
        read_only_fields = ['location']

    def get_barcode_list(self, obj):
        # Sirf wahi barcodes jo shop mein baki hain
        return list(obj.barcodes.filter(is_active=True).values_list('barcode_value', flat=True))

    def _generate_barcodes(self, transaction_obj, count):
        new_barcodes = []
        for _ in range(count):
            unique_code = ''.join([str(random.randint(0, 9)) for _ in range(8)])
            new_barcodes.append(
                GeneratedBarcode(transaction=transaction_obj, barcode_value=unique_code, is_active=True)
            )
        if new_barcodes:
            GeneratedBarcode.objects.bulk_create(new_barcodes)

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request.user, 'location'):
            validated_data['location'] = request.user.location 
        
        transaction_obj = StockTransaction.objects.create(**validated_data)
        num_pieces = validated_data.get('no_of_pieces', 0)
        self._generate_barcodes(transaction_obj, num_pieces)
        return transaction_obj

    @transaction.atomic
    def update(self, instance, validated_data):
        # 🛡️ SMART UPDATE: Sold items ko safe rakh kar baki manage karna
        new_pieces_input = validated_data.get('no_of_pieces', instance.no_of_pieces)
        
        active_barcodes = instance.barcodes.filter(is_active=True)
        sold_barcodes_count = instance.barcodes.filter(is_active=False).count()
        current_active_count = active_barcodes.count()

        # User ne jo total pieces likhe hain, wo sold items se kam nahi ho sakte
        if new_pieces_input < sold_barcodes_count:
            raise serializers.ValidationError({
                "error": f"Quantity {sold_barcodes_count} se kam nahi ho sakti kyunki itne items sell ho chuke hain."
            })

        # Naye active pieces jo hume maintain karne hain
        target_active_count = new_pieces_input - sold_barcodes_count

        if target_active_count > current_active_count:
            # Extra pieces add karne hain
            diff = target_active_count - current_active_count
            self._generate_barcodes(instance, diff)
        elif target_active_count < current_active_count:
            # Unsold pieces kam karne hain
            to_remove = current_active_count - target_active_count
            ids_to_delete = active_barcodes.order_by('-id').values_list('id', flat=True)[:to_remove]
            GeneratedBarcode.objects.filter(id__in=ids_to_delete).delete()

        return super().update(instance, validated_data)

    def to_representation(self, instance):
        repr = super().to_representation(instance)
        # 💡 UI PERSISTENCE: Field mein wahi dikhega jo bacha hua (Active) hai
        repr['no_of_pieces'] = instance.barcodes.filter(is_active=True).count()
        repr['sub_group_name'] = instance.sub_group.name if instance.sub_group else "N/A"
        repr['location_name'] = instance.location.name if instance.location else "Main Store"
        repr['item_location_name'] = instance.item_location.name if instance.item_location else "No Rack"
        repr['shop_details'] = {
            "name": "SVENSKA STORE",
            "address": "Bengaluru, Karnataka",
            "mobile": "+91 0000000000"
        }
        return repr


# ==========================================================================
# 3. SALES SERIALIZERS (FIXED & CLEANED)
# ==========================================================================

class SaleItemSerializer(serializers.ModelSerializer):
    barcode = serializers.PrimaryKeyRelatedField(queryset=GeneratedBarcode.objects.all())
    barcode_number = serializers.ReadOnlyField(source='barcode.barcode_value')
    item_name = serializers.ReadOnlyField(source='barcode.transaction.group.name') 

    class Meta:
        model = SaleItem
        fields = ['barcode', 'barcode_number', 'item_name', 'rate', 'cgst_amt', 'sgst_amt', 'igst_amt']

class SaleHeaderSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    amount_in_words = serializers.SerializerMethodField()
    sold_by_name = serializers.ReadOnlyField(source='sold_by.name')
    location_name = serializers.ReadOnlyField(source='location.name')

    class Meta:
        model = SaleHeader
        fields = [
            'bill_no', 'bill_date', 'customer_name', 'customer_mobile', 
            'total_amount', 'discount', 'payment_mode', 'freight_charge', 
            'items', 'amount_in_words', 'sold_by_name', 'location_name' # ✅ Added missing fields
        ]
        read_only_fields = ['bill_no', 'bill_date', 'sold_by', 'location']

    def get_amount_in_words(self, obj):
        # Yahan num2words ka logic sahi hai
        return f"{obj.total_amount} Rupees Only"

    @transaction.atomic
    def create(self, validated_data):
        try:
            items_data = validated_data.pop('items')
            
            # 1. Bill Number Auto-generation
            last_bill = SaleHeader.objects.all().order_by('id').last()
            new_id = (last_bill.id + 1) if last_bill else 1
            validated_data['bill_no'] = f"INV/2026/{new_id:05d}"
            
            # 2. Sale Header Create
            sale = SaleHeader.objects.create(**validated_data)
            
            # 3. Items Processing & Stock Deactivation
            for item_data in items_data:
                barcode_obj = item_data['barcode']
                
                # Double Safety Check
                if not barcode_obj.is_active:
                    raise serializers.ValidationError(f"Barcode {barcode_obj.barcode_value} already sold.")
                
                # Create Sale Item
                SaleItem.objects.create(sale=sale, **item_data)
                
                # ✅ DEACTIVATE BARCODE (Stock Minus)
                barcode_obj.is_active = False
                barcode_obj.save()
            
            return sale

        except Exception as e:
            logger.error(f"🔥 SALE CRASH: {traceback.format_exc()}")
            raise serializers.ValidationError({"error": str(e)})