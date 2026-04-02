from rest_framework import serializers
from ..models import Ledger
import logging

logger = logging.getLogger(__name__)

class LedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ledger
        # normalized_name ko hum exclude ya read_only rakhenge kyunki ye model.save() mein handle hota hai
        fields = '__all__'
        read_only_fields = ['normalized_name', 'delflag', 'created_at', 'updated_at']

    def validate(self, data):
        # 1. Name normalization for duplicate check
        name = data.get('name', '').strip()
        norm_name = name.lower()

        # 2. New Record Duplicate Check
        if not self.instance:
            if Ledger.objects.filter(normalized_name=norm_name).exists():
                logger.warning(f"Validation Failed: Ledger name '{name}' already exists.")
                raise serializers.ValidationError({"name": "A ledger with this name already exists."})

        # 3. Edit Mode: Name Change Protection
        if self.instance and 'name' in data:
            if self.instance.name.strip().lower() != norm_name:
                logger.error(f"Attempted to change immutable name from '{self.instance.name}' to '{name}'")
                raise serializers.ValidationError({"name": "Ledger Name cannot be modified after creation."})

        # 4. CR/DR Mutual Exclusion Validation
        # Hamesha float/Decimal mein convert karke check karein
        cr = float(data.get('opening_balance_credit', 0))
        dr = float(data.get('opening_balance_debit', 0))

        if cr > 0 and dr > 0:
            logger.warning("Validation Failed: Both CR and DR filled.")
            raise serializers.ValidationError("You cannot fill both Credit and Debit amounts.")

        return data