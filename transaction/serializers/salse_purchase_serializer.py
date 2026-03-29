from rest_framework import serializers
from django.db import transaction
from ..models import SalesHeader, SalesDetail, PurchaseHeader, PurchaseDetail

# --- DETAIL SERIALIZERS ---
class SalesDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesDetail
        exclude = ['header'] # Header hum create method mein pass karenge

class PurchaseDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseDetail
        exclude = ['header']

# --- HEADER SERIALIZERS ---

class SalesHeaderSerializer(serializers.ModelSerializer):
    details = SalesDetailSerializer(many=True)

    class Meta:
        model = SalesHeader
        fields = '__all__'

    def create(self, validated_data):
        details_data = validated_data.pop('details')
        try:
            with transaction.atomic():
                header = SalesHeader.objects.create(**validated_data)
                for detail in details_data:
                    SalesDetail.objects.create(header=header, **detail)
                return header
        except Exception as e:
            print(f"💥 DATABASE ERROR: {str(e)}") # Terminal check karein
            raise serializers.ValidationError({"error": str(e)})

class PurchaseHeaderSerializer(serializers.ModelSerializer):
    details = PurchaseDetailSerializer(many=True)

    class Meta:
        model = PurchaseHeader
        fields = '__all__'

    def create(self, validated_data):
        details_data = validated_data.pop('details')
        try:
            with transaction.atomic():
                header = PurchaseHeader.objects.create(**validated_data)
                for detail in details_data:
                    PurchaseDetail.objects.create(header=header, **detail)
                return header
        except Exception as e:
            print(f"💥 DATABASE ERROR: {str(e)}")
            raise serializers.ValidationError({"error": str(e)})