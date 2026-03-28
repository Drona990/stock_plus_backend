from rest_framework import viewsets, status, filters
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from core.permissions import IsAccountActive, IsAdminOrSuperuser
from ..models import CustomerMaster
from ..serializers.customer_serializers import CustomerMasterSerializer

class CustomerMasterViewSet(viewsets.ModelViewSet):
    # Sirf active records dikhayenge (del_flag is space)
    queryset = CustomerMaster.objects.filter(del_flag=' ').order_by('-created_at')
    serializer_class = CustomerMasterSerializer
    permission_classes = [IsAdminOrSuperuser, IsAccountActive]

    # --- FILTERING & SEARCHING ---
    filter_backends = [
        DjangoFilterBackend, 
        filters.SearchFilter, 
        filters.OrderingFilter
    ]
    
    # Exact match filters (Example: /api/customers/?mop=CASH)
    filterset_fields = ['mop', 'state_type', 'batch_no', 'created_by']
    
    # Search filters (Example: /api/customers/?search=Drona)
    search_fields = ['customer_name', 'mobile', 'gst_no', 'batch_no']
    
    # Ordering (Example: /api/customers/?ordering=-created_at)
    ordering_fields = ['created_at', 'customer_name', 'opening_cr']
    ordering = ['-created_at'] # Default: Naye customers pehle dikhenge

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.del_flag = 'D'
        instance.del_date = timezone.now().date()
        instance.save()
        return Response(
            {"success": True, "message": "Customer moved to recycle bin (Soft Deleted)."}, 
            status=status.HTTP_200_OK 
        )

    # --- OPTIONAL: User Role Auto-Assignment ---
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user.role if hasattr(self.request.user, 'role') else 'STAFF')