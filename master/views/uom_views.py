from core.permissions import IsAccountActive, IsAdminOrSuperuser
from master.models import UOMMaster
from master.serializers.uom_serializer import UOMSerializer
from rest_framework import viewsets, status, filters



class UOMViewSet(viewsets.ModelViewSet):
    queryset = UOMMaster.objects.all()
    serializer_class = UOMSerializer
    permission_classes = [IsAdminOrSuperuser,IsAccountActive]