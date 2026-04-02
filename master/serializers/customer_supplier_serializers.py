from rest_framework import serializers
from ..models import CustomerMaster, SupplierMaster

class BaseMasterSerializer(serializers.ModelSerializer):
    """Common logic for both Customer and Supplier Serializers"""

    def validate_name(self, value):
        name = value.strip()
        
        model = self.Meta.model
        queryset = model.objects.filter(name__iexact=name, delflag=' ')
        
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
            
        if queryset.exists():
            raise serializers.ValidationError(f"A record with the name '{name}' already exists (Case-Insensitive).")
        
        return name

    def validate_mobile_no(self, value):
        if not value.isdigit() or len(value) < 10:
            raise serializers.ValidationError("Valid mobile number is required.")
        return value

    def validate_email(self, value):
        if value and "@" not in value:
            raise serializers.ValidationError("Please enter a valid email address.")
        return value

    class Meta:
        read_only_fields = ['delflag', 'deldate', 'created_at']

class CustomerSerializer(BaseMasterSerializer):
    class Meta(BaseMasterSerializer.Meta):
        model = CustomerMaster
        fields = '__all__'

class SupplierSerializer(BaseMasterSerializer):
    class Meta(BaseMasterSerializer.Meta):
        model = SupplierMaster
        fields = '__all__'