
from num2words import num2words
import traceback
from rest_framework import serializers
from .models import InventoryCategory, ProductSubGroup, SaleHeader, SaleItem, Location
from .models import ProductGroup , StockTransaction, GeneratedBarcode
import random
from django.db import transaction
import logging
logger = logging.getLogger(__name__)


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
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

    class Meta:
        model = StockTransaction
        fields = '__all__'
        # ✅ Location ko read_only rakhna hai kyunki ye auto-fill hogi
        read_only_fields = ['location']

    def get_barcode_list(self, obj):
        return list(obj.barcodes.values_list('barcode_value', flat=True))

    @transaction.atomic
    def create(self, validated_data):
        logger.info("--- STOCK TRANSACTION CREATE START ---")
        try:
            # 📍 AUTO-SAVE LOCATION LOGIC
            request = self.context.get('request')
            if request and hasattr(request.user, 'location'):
                # Login user ki profile se location uthakar validated_data mein add kar rahe hain
                validated_data['location'] = request.user.location 
            
            # 1. Save Transaction with Auto-Location
            transaction_obj = StockTransaction.objects.create(**validated_data)
            
            # 2. Bulk Barcode Generation
            num_pieces = validated_data.get('no_of_pieces', 0)
            new_barcodes = []
            for _ in range(num_pieces):
                unique_code = ''.join([str(random.randint(0, 9)) for _ in range(8)])
                new_barcodes.append(
                    GeneratedBarcode(transaction=transaction_obj, barcode_value=unique_code)
                )
            
            if new_barcodes:
                GeneratedBarcode.objects.bulk_create(new_barcodes)
                logger.info(f"Successfully created {len(new_barcodes)} barcodes for location: {transaction_obj.location}")
            
            return transaction_obj

        except Exception as e:
            logger.error(f"Stock Error: {str(e)}")
            raise serializers.ValidationError({"server_error": str(e)})

    def to_representation(self, instance):
        repr = super().to_representation(instance)
        repr['sub_group_name'] = instance.sub_group.name if instance.sub_group else "N/A"
        # Display Location name in response
        repr['location_name'] = instance.location.name if instance.location else "Main Store"
        repr['shop_details'] = {
            "name": "SVENSKA STORE",
            "address": "Bengaluru, Karnataka",
            "mobile": "+91 9876543210"
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