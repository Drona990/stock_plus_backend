from venv import logger
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from authentication.models import CustomUser
from core.permissions import IsAccountActive, IsAdminOrSuperuser
from .models import GeneratedBarcode, ItemLocation, ProductGroup, SaleHeader, SaleItem, StockTransaction, Location
from .serializers import ItemLocationSerializer, ProductGroupSerializer, SaleHeaderSerializer, StockTransactionSerializer, LocationSerializer
from .models import InventoryCategory,ProductSubGroup
from django.db.models import FloatField, Sum, Count, F, Q, Value, Case, When, CharField
from datetime import datetime
import traceback
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from rest_framework.views import APIView
from .serializers import (
    InventoryCategorySerializer, ProductSubGroupSerializer
    
)
from django.db.models.functions import Concat, Coalesce
import psutil
import shutil
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from django.db import connection

from django.utils import timezone
from datetime import datetime
import logging
logger = logging.getLogger(__name__)



@api_view(['GET'])
@authentication_classes([]) 
@permission_classes([AllowAny]) 
def health_check(request):
    # 1. RAM Usage check
    vm = psutil.virtual_memory()
    ram_usage = vm.percent # Percentage of RAM used

    # 2. Disk Usage check (Root directory '/')
    total, used, free = shutil.disk_usage("/")
    disk_usage = (used / total) * 100

    health_status = {
        "status": "healthy",
        "database": "up",
        "resources": {
            "ram_used_percent": ram_usage,
            "disk_used_percent": round(disk_usage, 2),
        }
    }

    # 3. Database Check
    try:
        connection.ensure_connection()
    except Exception:
        health_status["database"] = "down"
        health_status["status"] = "unhealthy"

    # 4. Critical Threshold check (Alert logic)
    # Agar 90% se zyada RAM ya Disk bhar gayi toh status "warning" kar dein
    if ram_usage > 90 or disk_usage > 90:
        health_status["status"] = "warning"
        health_status["message"] = "System resources are running low!"

    status_code = 200 if health_status["status"] != "unhealthy" else 503
    return Response(health_status, status=status_code)


class InventoryBaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrSuperuser,IsAccountActive]

class LocationViewSet(InventoryBaseViewSet):
    queryset = Location.objects.all().order_by('name')
    serializer_class = LocationSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


class ItemLocationViewSet(InventoryBaseViewSet):
    queryset = ItemLocation.objects.all().order_by('name')
    serializer_class = ItemLocationSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']


class InventoryCategoryViewSet(InventoryBaseViewSet):
    queryset = InventoryCategory.objects.all().order_by('name')
    serializer_class = InventoryCategorySerializer
    search_fields = ['name']


class ProductGroupViewSet(viewsets.ModelViewSet):
    queryset = ProductGroup.objects.all().order_by('name')
    serializer_class = ProductGroupSerializer
    permission_classes = [IsAdminOrSuperuser,IsAccountActive]
    
    # Filtering setup
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'hsn_code'] 


class ProductSubGroupViewSet(viewsets.ModelViewSet):
    queryset = ProductSubGroup.objects.all().order_by('group__name', 'name')
    serializer_class = ProductSubGroupSerializer
    permission_classes = [IsAdminOrSuperuser,IsAccountActive]
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['group'] 
    search_fields = ['name', 'group__name']


class StockTransactionViewSet(viewsets.ModelViewSet):
    queryset = StockTransaction.objects.all().order_by('-created_at')
    serializer_class = StockTransactionSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        active_barcodes = instance.barcodes.filter(is_active=True)
        sold_barcodes = instance.barcodes.filter(is_active=False)

        if sold_barcodes.exists():
            # 💡 SMART DELETE: Jo bik gaye unhe rehne do, baki uda do
            count_removed = active_barcodes.count()
            active_barcodes.delete()
            
            # Record ko update kar do ki ab zero active pieces hain
            instance.no_of_pieces = 0
            instance.save()
            
            return Response({
                "message": f"Partial Delete: {count_removed} unsold items delete ho gaye hain. Sold items ka record bacha liya gaya hai."
            }, status=status.HTTP_200_OK)
        
        # Agar ek bhi nahi bika, toh poora delete kar do
        self.perform_destroy(instance)
        return Response({"message": "Stock fully deleted successfully!"}, status=status.HTTP_200_OK)

class SalesViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated,IsAccountActive]
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


class FetchBillForReturnView(APIView):
    permission_classes = [IsAuthenticated,IsAccountActive]

    def get(self, request, invoice_no):
        try:
            sale = SaleHeader.objects.get(bill_no=invoice_no)
            serializer = SaleHeaderSerializer(sale)
            return Response({"status": "success", "data": serializer.data})
        except SaleHeader.DoesNotExist:
            return Response({"error": "Invoice number nnot found!"}, status=404)



class ProcessReturnExchangeView(APIView):
    permission_classes = [IsAuthenticated,IsAccountActive]
    @transaction.atomic
    def post(self, request):
        data = request.data
        # Hum barcode ID (1, 2, etc.) ko use karke SaleItem dhoondenge
        barcode_id = data.get('sale_item_id') 
        action_type = data.get('action_type')
        new_bc_val = data.get('new_barcode')

        try:
            # Barcode ID se SaleItem dhoondein jo becha gaya hai
            sale_item = SaleItem.objects.select_related('sale', 'barcode').get(barcode__id=barcode_id)
            sale_header = sale_item.sale
            old_barcode = sale_item.barcode

            # --- STEP 1: Reverse Old Item ---
            sale_header.total_amount -= sale_item.rate
            old_barcode.is_active = True
            old_barcode.save()

            if action_type == 'exchange':
                # --- STEP 2: Issue New Item ---
                if not new_bc_val:
                    return Response({"error": "Scan new item barcode!"}, status=400)
                
                new_barcode = GeneratedBarcode.objects.get(barcode_value=new_bc_val, is_active=True)
                new_rate = new_barcode.transaction.price_with_gst
                
                sale_header.total_amount += new_rate
                new_barcode.is_active = False
                new_barcode.save()

                sale_item.barcode = new_barcode
                sale_item.rate = new_rate
                sale_item.save()
            else:
                # --- STEP 3: Pure Return (Delete from Bill) ---
                sale_item.delete()

            sale_header.save()
            sale_header.refresh_from_db()
            
            return Response({
                "status": "success",
                "message": f"Item {action_type}ed successfully",
                "data": SaleHeaderSerializer(sale_header).data
            })

        except GeneratedBarcode.DoesNotExist:
            return Response({"error": "New Barcode not in stock!"}, status=404)
        except SaleItem.DoesNotExist:
            return Response({"error": "Sale records not found!"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)



class DashboardViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    # ==========================================================================
    # 1. SUMMARY DASHBOARD (Daily KPI View)
    # ==========================================================================
    def list(self, request):
        try:
            today = timezone.localtime().date()
            user = request.user
            is_privileged = user.role in ['superuser', 'admin', 'manager']

            if is_privileged:
                sales_qs = SaleHeader.objects.filter(bill_date__date=today)
                stock_qs = GeneratedBarcode.objects.all()
            else:
                sales_qs = SaleHeader.objects.filter(bill_date__date=today, sold_by=user)
                # Filter stock by user's assigned location
                stock_qs = GeneratedBarcode.objects.filter(transaction__location=user.location)

            financials = sales_qs.aggregate(
                rev=Coalesce(Sum('total_amount'), 0.0, output_field=FloatField()),
                disc=Coalesce(Sum('discount'), 0.0, output_field=FloatField())
            )
            
            payment_stats = sales_qs.values('payment_mode').annotate(
                mode_total=Coalesce(Sum('total_amount'), 0.0, output_field=FloatField())
            ).order_by('-mode_total')

            return Response({
                "status": "success",
                "user_role": user.role,
                "summary": {
                    "current_stock": stock_qs.filter(is_active=True).count(),
                    "items_sold": stock_qs.filter(is_active=False).count(),
                    "financials": {
                        "total_revenue": financials['rev'],
                        "total_discount_amt": financials['disc'],
                        "bill_count": sales_qs.count(),
                        "revenue_by_mode": {item['payment_mode']: item['mode_total'] for item in payment_stats}
                    }
                },
                "recent_sales": list(sales_qs.order_by('-bill_date')[:10].values(
                    'bill_no', 'customer_name', 'total_amount', 'bill_date', 'payment_mode'
                ))
            })
        except Exception as e:
            logger.error(f"Error in Dashboard list: {str(e)}")
            return Response({"error": str(e)}, status=500)

    # ==========================================================================
    # 2. STAFF PERFORMANCE REPORT (Leaderboard)
    # ==========================================================================
    @action(detail=False, methods=['get'])
    def staff_performance_report(self, request):
        try:
            period = request.query_params.get('period', 'monthly')
            loc_id = request.query_params.get('location')
            today = timezone.localtime().date()
            
            sales_filter = Q()
            if period == 'daily':
                sales_filter &= Q(sales__bill_date__date=today.date())
            elif period == 'monthly':
                month = int(request.query_params.get('month', today.month))
                year = int(request.query_params.get('year', today.year))
                sales_filter &= Q(sales__bill_date__month=month, sales__bill_date__year=year)

            if loc_id and loc_id != 'null' and loc_id != '':
                sales_filter &= Q(sales__location_id=loc_id)

            # Get User model dynamically
            from django.contrib.auth import get_user_model
            User = get_user_model()
            staff_qs = User.objects.filter(role='staff')

            performance_data = staff_qs.annotate(
                full_name=Concat(Coalesce(F('first_name'), Value('')), Value(' '), Coalesce(F('last_name'), Value('')), output_field=CharField()),
                total_invoices=Count('sales', filter=sales_filter, distinct=True),
                revenue=Coalesce(Sum('sales__total_amount', filter=sales_filter), 0.0, output_field=FloatField()),
            ).values('id', 'username', 'full_name', 'total_invoices', 'revenue').order_by('-revenue')

            report_list = list(performance_data)
            best = report_list[0] if report_list and report_list[0]['revenue'] > 0 else None
            
            return Response({"status": "success", "best_performer": best, "report": report_list})
        except Exception as e:
            return Response({"error": str(e)}, status=500)

    # ==========================================================================
    # 3. MY PERSONAL REPORT (Secure Isolation)
    # ==========================================================================
    @action(detail=False, methods=['get'])
    def my_personal_report(self, request):
        user = request.user
        start_str = request.query_params.get('start_date')
        end_str = request.query_params.get('end_date')

        try:
            start_date = timezone.make_aware(datetime.strptime(start_str, '%Y-%m-%d'))
            end_date = timezone.make_aware(datetime.strptime(end_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59))

            # Query optimized for SaleItem -> SaleHeader mapping
            qs = SaleItem.objects.select_related('sale', 'barcode').filter(
                sale__bill_date__range=[start_date, end_date],
                sale__sold_by=user
            )

            raw_data = qs.values(
                'sale__bill_no', 'sale__customer_name', 'sale__bill_date', 'sale__payment_mode',
                'rate',
                b_val=F('barcode__barcode_value'), # From GeneratedBarcode model
            ).order_by('-sale__bill_date')

            grouped = {}
            for row in raw_data:
                b_no = row['sale__bill_no']
                if b_no not in grouped:
                    grouped[b_no] = {
                        "bill_no": b_no,
                        "barcode_no": row['b_val'] or "N/A",
                        "customer_name": row['sale__customer_name'] or "CASH",
                        "date": row['sale__bill_date'],
                        "payment_mode": row['sale__payment_mode'] or "CASH",
                        "invoice_total": 0.0,
                    }
                grouped[b_no]["invoice_total"] += float(row['rate'] or 0.0)

            return Response(list(grouped.values()))
        except Exception as e:
            logger.error(f"Personal Report Crash: {str(e)}")
            return Response({"error": str(e)}, status=500)

    # ==========================================================================
    # 4. DETAILED AUDIT REPORT (Sales & Stock Global Audit)
    # ==========================================================================
    @action(detail=False, methods=['get'])
    def detailed_report(self, request):
        r_type = request.query_params.get('type')
        start_str = request.query_params.get('start_date')
        end_str = request.query_params.get('end_date')
        loc_id = request.query_params.get('location')
        
        try:
            start_date = timezone.make_aware(datetime.strptime(start_str, '%Y-%m-%d'))
            end_date = timezone.make_aware(datetime.strptime(end_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59))

            if r_type == 'sales':
                qs = SaleItem.objects.select_related('sale', 'barcode').filter(
                    sale__bill_date__range=[start_date, end_date]
                )
                if loc_id and loc_id != 'null' and loc_id != '':
                    qs = qs.filter(sale__location_id=loc_id)

                raw_data = qs.values(
                    'sale__bill_no', 'sale__customer_name', 'sale__bill_date', 'sale__payment_mode',
                    'rate',
                    b_val=F('barcode__barcode_value'),
                    staff_name=Concat(Coalesce(F('sale__sold_by__first_name'), Value('')), Value(' '), Coalesce(F('sale__sold_by__last_name'), Value(''))),
                    item_name=F('barcode__transaction__group__name')
                ).order_by('-sale__bill_date')

                grouped = {}
                for row in raw_data:
                    b_no = row['sale__bill_no']
                    if b_no not in grouped:
                        grouped[b_no] = {
                            "bill_no": b_no, 
                            "barcode_no": row['b_val'] or "N/A",
                            "customer_name": row['sale__customer_name'] or "CASH", 
                            "date": row['sale__bill_date'], 
                            "payment_mode": row['sale__payment_mode'], 
                            "sold_by": row['staff_name'], 
                            "invoice_total": 0.0,
                            "item_name": row['item_name']
                        }
                    grouped[b_no]["invoice_total"] += float(row['rate'] or 0.0)
                return Response(list(grouped.values()))

            elif r_type == 'stock':
                qs = GeneratedBarcode.objects.select_related('transaction__group').filter(
                    transaction__created_at__range=[start_date, end_date]
                )
                if loc_id and loc_id != 'null' and loc_id != '':
                    qs = qs.filter(transaction__location_id=loc_id)

                data = qs.values(
                    date=F('transaction__created_at'),
                    barcode_no=F('barcode_value'),
                    item_name=F('transaction__group__name'),
                    price=F('transaction__price_with_gst'),
                    status_text=Case(
                        When(is_active=True, then=Value('IN STOCK')),
                        default=Value('SOLD'),
                        output_field=CharField()
                    )
                ).order_by('-transaction__created_at')
                return Response(list(data))

            return Response({"error": f"Invalid type '{r_type}'"}, status=400)
            
        except Exception as e:
            logger.error(f"Detailed Audit Crash: {str(e)}")
            return Response({"error": str(e)}, status=500)



class MasterReportViewSet(viewsets.ViewSet):
    def list(self, request):
        try:
            category = request.query_params.get('category', 'SALES')
            r_type = request.query_params.get('type', 'TODAY')
            now_local = timezone.localtime(timezone.now())

            if category == 'STOCK':
                stock_qs = GeneratedBarcode.objects.select_related('transaction__group', 'transaction__sub_group','transaction__item_location').filter(is_active=True)
                raw_data = [{
                    "barcode": b.barcode_value,
                    "group": b.transaction.group.name,
                    "sub_master": b.transaction.sub_group.name,
                    "item_location_name": b.transaction.item_location.name if b.transaction.item_location else "No Rack",
                    "hsn": b.transaction.hsn_code,
                    "cgst": float(b.transaction.cgst_rate),
                    "sgst": float(b.transaction.sgst_rate),
                    "igst": float(b.transaction.igst_rate),
                    "price": float(b.transaction.cost_price),
                    "price_with_gst": float(b.transaction.price_with_gst)

                } for b in stock_qs]
                
                counts = {}
                for item in raw_data:
                    counts[item['sub_master']] = counts.get(item['sub_master'], 0) + 1

                return Response({
                    "status": "success", "data": raw_data, "item_wise_counts": counts,
                    "summary": {"total_val": sum(i['price'] for i in raw_data), "total_count": len(raw_data)}
                })

            else: # --- SALES ---
                sales_qs = SaleHeader.objects.prefetch_related('items__barcode__transaction__group').all()
                if r_type == 'TODAY': sales_qs = sales_qs.filter(bill_date__date=now_local.date())
                elif r_type == 'MONTH': sales_qs = sales_qs.filter(bill_date__month=request.query_params.get('month'))
                elif r_type == 'CUSTOM': sales_qs = sales_qs.filter(bill_date__date__range=[request.query_params.get('start_date'), request.query_params.get('end_date')])

                sales_list = []
                for sale in sales_qs:
                    sales_list.append({
                        "bill_no": sale.bill_no,
                        "customer": sale.customer_name or "CASH",
                        "date": timezone.localtime(sale.bill_date).strftime("%d-%m-%Y"),
                        "mode": sale.payment_mode or "CASH",
                        "total": float(sale.total_amount),
                        "items": [{
                            "name": itm.barcode.transaction.group.name,
                            "barcode": itm.barcode.barcode_value,
                            "hsn": itm.barcode.transaction.group.hsn_code,
                            "cgst_amt": float(itm.cgst_amt),
                            "sgst_amt": float(itm.sgst_amt),
                            "igst_amt": float(itm.igst_amt),
                            "rate": float(itm.rate),

                        } for itm in sale.items.all()]
                    })
                return Response({
                    "status": "success", 
                    "data": sales_list, 
                    "summary": {"rev": sum(s['total'] for s in sales_list)}
                })
        except Exception as e:
            return Response({"error": str(e)}, status=500)