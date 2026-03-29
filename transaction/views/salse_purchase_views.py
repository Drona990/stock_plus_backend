from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from core.permissions import IsAccountActive, IsAdminOrSuperuser
from transaction.serializers.salse_purchase_serializer import PurchaseHeaderSerializer, SalesHeaderSerializer
from ..models import SalesHeader, PurchaseHeader

from rest_framework.response import Response
from rest_framework import status


class SalesViewSet(viewsets.ModelViewSet):
    queryset = SalesHeader.objects.filter(delflag=' ').order_by('-created_at')
    serializer_class = SalesHeaderSerializer
    permission_classes =[IsAdminOrSuperuser,IsAccountActive]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            try:
                self.perform_create(serializer)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                print(f"💥 SERVER ERROR: {str(e)}")
                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            print(f"❌ VALIDATION ERROR: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PurchaseViewSet(viewsets.ModelViewSet):
    queryset = PurchaseHeader.objects.filter(delflag=' ').order_by('-created_at')
    serializer_class = PurchaseHeaderSerializer
    permission_classes =[IsAdminOrSuperuser,IsAccountActive]


    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            try:
                self.perform_create(serializer)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            except Exception as e:
                print(f"💥 SERVER ERROR: {str(e)}")
                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            print(f"❌ VALIDATION ERROR: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)