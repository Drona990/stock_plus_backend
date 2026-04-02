from rest_framework import serializers
from django.db import transaction
from ..models import (
    SalesHeader, SalesDetail, SalesLedger, 
    PurchaseHeader, PurchaseDetail, PurchaseLedger
)

class SalesDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesDetail
        exclude = ['header']

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
        read_only_fields = ['billno'] # Auto-generate hoga

    def create(self, validated_data):
        details_data = validated_data.pop('details')
        try:
            with transaction.atomic():
                # 1. Save Sales Bill
                header = SalesHeader.objects.create(**validated_data)
                
                # 2. Save Details
                for detail in details_data:
                    SalesDetail.objects.create(header=header, **detail)

                # 3. Save to SalesLedger (CTYPE: To)
                SalesLedger.objects.create(
                    invtype="SALES",
                    invno=header.billno,
                    invdate=header.billdate,
                    inname=header.name,
                    inaddress=header.address,
                    invgst=header.gst_number,
                    trcr=0.00,
                    trdr=header.grand_totamt,
                    ctype="To" # Client Requirement
                )
                return header
        except Exception as e:
            raise serializers.ValidationError({"error": f"Sales Error: {str(e)}"})

class PurchaseHeaderSerializer(serializers.ModelSerializer):
    details = PurchaseDetailSerializer(many=True)

    class Meta:
        model = PurchaseHeader
        fields = '__all__'
        read_only_fields = ['billno']

    def create(self, validated_data):
        details_data = validated_data.pop('details')
        try:
            with transaction.atomic():
                # 1. Save Purchase Bill
                header = PurchaseHeader.objects.create(**validated_data)
                
                # 2. Save Details
                for detail in details_data:
                    PurchaseDetail.objects.create(header=header, **detail)

                # 3. Save to PurchaseLedger (CTYPE: By)
                PurchaseLedger.objects.create(
                    invtype="PURCHASE",
                    invno=header.billno,
                    invdate=header.billdate,
                    inname=header.name,
                    inaddress=header.address,
                    invgst=header.gst_number,
                    trcr=header.grand_totamt,
                    trdr=0.00,
                    ctype="By" # Client Requirement
                )
                return header
        except Exception as e:
            raise serializers.ValidationError({"error": f"Purchase Error: {str(e)}"})