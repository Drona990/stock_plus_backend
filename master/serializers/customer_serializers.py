from rest_framework import serializers
from ..models import CustomerMaster

class CustomerMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerMaster
        fields = '__all__'
        read_only_fields = ['del_flag', 'del_date', 'created_at'] # Inhe user manually edit na kar sake

    def validate_mobile(self, value):
        if not value.isdigit() or len(value) < 10:
            raise serializers.ValidationError("Valid 10-digit mobile number is required.")
        return value