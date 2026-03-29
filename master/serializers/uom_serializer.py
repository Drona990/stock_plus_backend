from rest_framework import serializers
from master.models import UOMMaster


class UOMSerializer(serializers.ModelSerializer):
    class Meta:
        model = UOMMaster
        fields = '__all__'

