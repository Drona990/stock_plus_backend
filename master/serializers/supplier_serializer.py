from rest_framework import serializers
from ..models import SupplierMaster

class SupplierMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierMaster
        fields = '__all__'