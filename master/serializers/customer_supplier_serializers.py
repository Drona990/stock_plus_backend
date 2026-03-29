from rest_framework import serializers
from ..models import CustomerMaster, SupplierMaster

class BaseMasterSerializer(serializers.ModelSerializer):
    """Common logic for both Customer and Supplier Serializers"""
    
    # Image ke according fields (Mobile, PIN etc.) ko validate karne ke liye
    def validate_mobile_no(self, value):
        if not value.isdigit() or len(value) < 10:
            raise serializers.ValidationError("Valid mobile number is required.")
        return value

    def validate_email(self, value):
        if value and "@" not in value:
            raise serializers.ValidationError("Please enter a valid email address.")
        return value

    class Meta:
        # 'read_only_fields' mein humne image ke system fields ko dala hai
        read_only_fields = ['delflag', 'deldate', 'created_at']

class CustomerSerializer(BaseMasterSerializer):
    class Meta(BaseMasterSerializer.Meta):
        model = CustomerMaster
        fields = '__all__'

class SupplierSerializer(BaseMasterSerializer):
    class Meta(BaseMasterSerializer.Meta):
        model = SupplierMaster
        fields = '__all__'