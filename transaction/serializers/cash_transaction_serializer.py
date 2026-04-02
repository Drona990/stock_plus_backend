from rest_framework import serializers
from ..models import CashTransaction

class CashTransactionSerializer(serializers.ModelSerializer):
    ledger_name = serializers.ReadOnlyField(source='ledger.name')

    class Meta:
        model = CashTransaction
        fields = '__all__'