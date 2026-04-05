from rest_framework import serializers
from decimal import Decimal
from django.db import transaction as db_transaction  # 👈 Iska naam badal diya confusion dur karne ke liye
from ..models import JournalItem, JournalVoucher  # 👈 .models use karo agar usi app mein ho

class JournalItemSerializer(serializers.ModelSerializer):
    ledger_name = serializers.ReadOnlyField(source='ledger.name')

    class Meta:
        model = JournalItem
        fields = ['id', 'ledger', 'ledger_name', 'amount', 'type']

class JournalVoucherSerializer(serializers.ModelSerializer):
    items = JournalItemSerializer(many=True)

    class Meta:
        model = JournalVoucher
        fields = ['id', 'voucher_no', 'date', 'narration', 'items', 'created_at']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        
        # --- 1. Total Calculate Karo ---
        total_debit = sum(Decimal(str(item['amount'])) for item in items_data if item['type'] == 'DEBIT')
        total_credit = sum(Decimal(str(item['amount'])) for item in items_data if item['type'] == 'CREDIT')

        # --- 2. Accounting Validation (DR == CR) ---
        if total_debit != total_credit:
            raise serializers.ValidationError({
                "error": f"Total Debit (₹{total_debit:.2f}) and Total Credit (₹{total_credit:.2f}) must be equal!"
            })

        if total_debit <= 0:
            raise serializers.ValidationError({"error": "Amount must be greater than zero!"})

        # --- 3. Database Atomic Block ---
        # db_transaction.atomic ka matlab hai: "Ya toh sab save hoga, ya kuch bhi nahi"
        try:
            with db_transaction.atomic():
                # Voucher Header Create Karo
                voucher = JournalVoucher.objects.create(**validated_data)
                
                # Saari Rows (Items) Create Karo
                for item_data in items_data:
                    JournalItem.objects.create(voucher=voucher, **item_data)
                
                return voucher
        except Exception as e:
            raise serializers.ValidationError({"error": f"Database Error: {str(e)}"})