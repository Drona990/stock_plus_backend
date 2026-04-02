from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from core.permissions import IsAccountActive, IsAdminOrSuperuser
from master.serializers.customer_supplier_serializers import CustomerSerializer, SupplierSerializer
from ..models import CustomerMaster, Ledger, SupplierMaster
import logging
logger = logging.getLogger(__name__)

class BaseMasterViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrSuperuser,IsAccountActive]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'mobile_no', 'gst_number', 'city', 'email', 'batch_number']
    filterset_fields = ['city', 'batch_number', 'created_by']
    ordering_fields = ['created_at', 'name', 'opening_balance_cr']
    ordering = ['-created_at']

    # --- LOGGING CREATE ---
    def create(self, request, *args, **kwargs):
        logger.info(f"➡️ Incoming POST Request Data: {request.data}")
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"❌ VALIDATION FAILED: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        self.perform_create(serializer)
        logger.info(f"✅ Record Created Successfully: {serializer.data.get('name')}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # --- LOGGING UPDATE ---
    def update(self, request, *args, **kwargs):
        logger.info(f"➡️ Incoming PUT Request Data: {request.data}")
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        if not serializer.is_valid():
            logger.error(f"❌ UPDATE VALIDATION FAILED: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delflag = 'D'
        instance.deldate = timezone.now().date()
        instance.save()
        return Response({"success": True}, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        created_by_val = self.request.user.username if self.request.user.is_authenticated else 'ADMIN'
        serializer.save(created_by=created_by_val)


class CustomerMasterViewSet(BaseMasterViewSet):
    queryset = CustomerMaster.objects.filter(delflag=' ').order_by('-created_at')
    serializer_class = CustomerSerializer

    def perform_create(self, serializer):
        created_by_val = self.request.user.username if self.request.user.is_authenticated else 'ADMIN'
        customer = serializer.save(created_by=created_by_val)

        Ledger.objects.create(
            name=customer.name,
            group="SALES",    
            head="SALES",   
            group_wise="SALES",
            opening_balance_credit=customer.opening_balance_cr,
            opening_balance_debit=customer.opening_balance_dr,
            delflag=' '
        )

    # 2. Update hone par Ledger balance sync (YE ZAROORI HAI)
    def perform_update(self, serializer):
        customer = serializer.save()
        # Ledger table mein same name wale record ka balance update karo
        Ledger.objects.filter(name=customer.name).update(
            opening_balance_credit=customer.opening_balance_cr,
            opening_balance_debit=customer.opening_balance_dr
        )

    

# --- Final Supplier ViewSet ---
class SupplierMasterViewSet(BaseMasterViewSet):
    queryset = SupplierMaster.objects.filter(delflag=' ').order_by('-created_at')
    serializer_class = SupplierSerializer

    def perform_create(self, serializer):
        created_by_val = self.request.user.username if self.request.user.is_authenticated else 'ADMIN'
        supplier = serializer.save(created_by=created_by_val)

        Ledger.objects.create(
            name=supplier.name,
            group="PURCHASE",
            head="PURCHASE",         
            group_wise="PURCHASE",
            opening_balance_credit=supplier.opening_balance_cr,
            opening_balance_debit=supplier.opening_balance_dr,
            delflag=' '
        )

    # 2. Update hone par Ledger balance sync
    def perform_update(self, serializer):
        supplier = serializer.save()
        # Supplier ka balance ledger mein update karo
        Ledger.objects.filter(name=supplier.name).update(
            opening_balance_credit=supplier.opening_balance_cr,
            opening_balance_debit=supplier.opening_balance_dr
        )
    