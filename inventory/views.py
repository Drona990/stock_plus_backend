from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from core.permissions import IsAdminOrSuperuser
from .models import GeneratedBarcode, ProductGroup, SaleHeader, SaleItem, StockTransaction, Location
from .serializers import ProductGroupSerializer, SaleHeaderSerializer, StockTransactionSerializer, LocationSerializer
from .models import InventoryCategory,ProductSubGroup
from django.db.models import Sum, Count, F, Q, Value, Case, When, CharField
from datetime import datetime
import traceback
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from django.db import transaction


from .serializers import (
    InventoryCategorySerializer, ProductSubGroupSerializer
    
)


class InventoryBaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrSuperuser]

class LocationViewSet(InventoryBaseViewSet):
    queryset = Location.objects.all().order_by('name')
    serializer_class = LocationSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

class InventoryCategoryViewSet(InventoryBaseViewSet):
    queryset = InventoryCategory.objects.all().order_by('name')
    serializer_class = InventoryCategorySerializer
    search_fields = ['name']


class ProductGroupViewSet(viewsets.ModelViewSet):
    queryset = ProductGroup.objects.all().order_by('name')
    serializer_class = ProductGroupSerializer
    permission_classes = [IsAdminOrSuperuser]
    
    # Filtering setup
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'hsn_code'] 


class ProductSubGroupViewSet(viewsets.ModelViewSet):
    queryset = ProductSubGroup.objects.all().order_by('group__name', 'name')
    serializer_class = ProductSubGroupSerializer
    permission_classes = [IsAdminOrSuperuser]
    
    # Filtering setup
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    # Taaki aap kisi specific group ke saare sub-names filter kar sakein
    filterset_fields = ['group'] 
    search_fields = ['name', 'group__name']



class StockTransactionViewSet(viewsets.ModelViewSet):
    queryset = StockTransaction.objects.all().order_by('-created_at')
    serializer_class = StockTransactionSerializer
    permission_classes = [IsAuthenticated] # Ensure user is logged in

    def get_serializer_context(self):
        # ✅ Request object ko context mein bhej rahe hain
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
            return Response({
                "message": "Stock added and Barcodes generated successfully!",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SalesViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = SaleHeader.objects.all().order_by('-bill_date')
    serializer_class = SaleHeaderSerializer

    def create(self, request, *args, **kwargs):
        print(f"📥 [POST] Sale by: {request.user.username}")
        
        serializer = self.get_serializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            # ✅ Injecting Context-aware data (User & Location)
            user_location = getattr(request.user, 'location', None)
            
            sale_instance = serializer.save(
                sold_by=request.user, 
                location=user_location
            )
            
            # Return full data for Flutter PDF
            return Response({
                "status": "success",
                "message": "Bill generated successfully",
                "data": SaleHeaderSerializer(sale_instance).data
            }, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def lookup_barcode(self, request):
        barcode_value = request.query_params.get('code')
        try:
            barcode = GeneratedBarcode.objects.select_related(
                'transaction', 'transaction__group'
            ).get(barcode_value=barcode_value, is_active=True)
            
            t = barcode.transaction
            return Response({
                "barcode_id": barcode.id,
                "group_name": t.group.name,
                "rate": float(t.price_with_gst),
                "cgst_rate": float(t.cgst_rate),
                "sgst_rate": float(t.sgst_rate),
            })
        except GeneratedBarcode.DoesNotExist:
            return Response({"error": "Barcode invalid or sold"}, status=404)



class DashboardViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    def list(self, request):
        try:
            today = timezone.now().date()
            user = request.user
            
            # --- 🛡️ ROLE BASED FILTER LOGIC ---
            is_privileged = user.role in ['superuser', 'admin', 'manager']

            if is_privileged:
                # Admins see global data
                sales_qs = SaleHeader.objects.filter(bill_date__date=today)
                stock_qs = GeneratedBarcode.objects.all()
            else:
                # ✅ Staff see ONLY their sales and their location's stock
                sales_qs = SaleHeader.objects.filter(
                    bill_date__date=today, 
                    sold_by=user
                )
                # Relationship path: Barcode -> Transaction -> Location
                stock_qs = GeneratedBarcode.objects.filter(transaction__location=user.location)

            # --- CALCULATIONS ---
            financials = sales_qs.aggregate(
                rev=Sum('total_amount'),
                disc=Sum('discount')
            )
            
            total_rev = financials['rev'] or 0.0
            total_disc = financials['disc'] or 0.0

            return Response({
                "status": "success",
                "user_role": user.role,
                "summary": {
                    "current_stock": stock_qs.filter(is_active=True).count(),
                    "items_sold": stock_qs.filter(is_active=False).count(),
                    "financials": {
                        "total_revenue": float(total_rev),
                        "total_discount_amt": float(total_disc),
                        "bill_count": sales_qs.count()
                    }
                },
                "recent_sales": list(sales_qs.order_by('-bill_date')[:10].values(
                    'bill_no', 'customer_name', 'total_amount', 'bill_date', 'payment_mode'
                ))
            })
        except Exception as e:
            print(f"Dashboard Summary Error: {traceback.format_exc()}")
            return Response({"error": str(e)}, status=500)

    # ==========================================================================
    # 2. DETAILED REPORTS (Sales & Stock)
    # ==========================================================================
    @action(detail=False, methods=['get'])
    def detailed_report(self, request):
        r_type = request.query_params.get('type')
        start_str = request.query_params.get('start_date')
        end_str = request.query_params.get('end_date')
        loc_id = request.query_params.get('location') # From Flutter Dropdown
        user = request.user

        try:
            # Parse dates
            start_date = timezone.make_aware(datetime.strptime(start_str, '%Y-%m-%d'))
            end_date = timezone.make_aware(datetime.strptime(end_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59))

            if r_type == 'sales':
                # Base Query
                qs = SaleItem.objects.filter(
                    sale__bill_date__range=[start_date, end_date]
                ).select_related('sale', 'sale__location', 'sale__sold_by')

                # ✅ PRIVACY & FILTER LOGIC
                if user.role not in ['superuser', 'admin', 'manager']:
                    # Staff: Strictly limited to their own data
                    qs = qs.filter(sale__sold_by=user)
                elif loc_id and loc_id != 'null':
                    # Admin: Specific location filter from dropdown
                    qs = qs.filter(sale__location_id=loc_id)
                
                data = list(qs.values(
                    'sale__bill_no', 'sale__customer_name', 
                    price=F('rate'), date=F('sale__bill_date'),
                    item_name=F('barcode__transaction__group__name'),
                    location_name=F('sale__location__name'),
                    sold_by=F('sale__sold_by__username'),
                    hsn=F('barcode__transaction__hsn_code')
                ))
            else:
                # --- INVENTORY REPORT ---
                if user.role not in ['superuser', 'admin', 'manager']:
                    return Response({"error": "Unauthorized Access to Inventory Reports"}, status=403)

                # ✅ Path Fixed: transaction__location
                qs = GeneratedBarcode.objects.filter(
                    transaction__created_at__range=[start_date, end_date]
                ).select_related('transaction', 'transaction__location', 'transaction__group')
                
                if loc_id and loc_id != 'null':
                    qs = qs.filter(transaction__location_id=loc_id)

                data = list(qs.annotate(
                    status_text=Case(
                        When(is_active=True, then=Value('IN STOCK')), 
                        default=Value('SOLD'), 
                        output_field=CharField()
                    )
                ).values(
                    'status_text',
                    date=F('transaction__created_at'),
                    item_name=F('transaction__group__name'),
                    location_name=F('transaction__location__name'),
                    price=F('transaction__price_with_gst'),
                    sold_by=Value('System'), 
                    hsn=F('transaction__hsn_code')
                ))
            
            return Response(data)

        except Exception as e:
            print(f"Report Action Error: {traceback.format_exc()}")
            return Response({"error": str(e)}, status=500)