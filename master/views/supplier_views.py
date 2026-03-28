from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from master.serializers.supplier_serializer import SupplierMasterSerializer
from ..models import SupplierMaster

class SupplierMasterViewSet(viewsets.ModelViewSet):
    queryset = SupplierMaster.objects.filter(del_flag=' ').order_by('-created_at')
    serializer_class = SupplierMasterSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['supplier_name', 'mobile', 'gst_no']
    filterset_fields = ['batch_no', 'mop']