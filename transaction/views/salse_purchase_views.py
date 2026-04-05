from rest_framework import viewsets, status, filters # <--- Added 'status'
from django_filters.rest_framework import DjangoFilterBackend
from core.permissions import IsAccountActive, IsAdminOrSuperuser
from transaction.serializers.salse_purchase_serializer import PurchaseHeaderSerializer, SalesHeaderSerializer
from ..models import PurchaseLedger, SalesHeader, PurchaseHeader, SalesLedger
import logging
from rest_framework.response import Response
logger = logging.getLogger(__name__)
from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from django.forms.models import model_to_dict
import traceback


@api_view(['GET'])
def get_invoice_print_data(request):
    inv_no = request.query_params.get('inv_no')
    
    # LOG 1: Check if API is hit
    print(f"\n--- DEBUG: Invoice Print API Hit for Inv No: {inv_no} ---")

    if not inv_no:
        return Response({"status": "error", "message": "Invoice number is required"}, status=400)

    try:
        # LOG 2: Database Query Start
        print("DEBUG: Fetching SalesHeader from DB...")
        header = SalesHeader.objects.filter(billno=inv_no, delflag=' ').first()
        
        if not header:
            print(f"DEBUG: Invoice {inv_no} not found in SalesHeader table.")
            return Response({"status": "error", "message": "Invoice not found"}, status=404)

        print(f"DEBUG: Found Header ID: {header.id}, Customer: {header.name}")

        # LOG 3: Mapping Data
        try:
            # Check if customer object exists to avoid AttributeError
            customer_mobile = ""
            if hasattr(header, 'customer') and header.customer:
                customer_mobile = getattr(header.customer, 'mobile', "")
            
            print("DEBUG: Mapping basic fields...")
            data = {
                "name": header.name or "",
                "address": header.address or "",
                "gst_number": header.gst_number or "",
                "mobile": customer_mobile,
                "billno": header.billno,
                "billdate": header.billdate.strftime('%Y-%m-%d') if header.billdate else "",
                "purchase_order_no": header.purchase_order_no or "",
                "purchase_order_date": header.purchase_order_date.strftime('%Y-%m-%d') if header.purchase_order_date else "",
                "dc_no": header.dc_no or "",
                "dc_date": header.dc_date.strftime('%Y-%m-%d') if header.dc_date else "",
                "no_of_package": header.no_of_package or "",
                "amtin_words": header.amtin_words or "",
                "totalamount": str(header.totalamount or 0.00),
                "cgst": str(header.cgst or 0.00),
                "sgst": str(header.sgst or 0.00),
                "grand_totamt": str(header.grand_totamt or 0.00),
            }

            # LOG 4: Mapping Details (Items)
            print("DEBUG: Fetching related SalesDetail (items)...")
            # header.details.all() works only if related_name='details' is in ForeignKey
            details_list = []
            for detail in header.details.all():
                details_list.append({
                    "sno": detail.sno,
                    "product_name": detail.product_name,
                    "hsncode": detail.hsncode or "",
                    "qty": str(detail.qty),
                    "rate": str(detail.rate),
                    "total": str(detail.total)
                })
            
            data["details"] = details_list
            print(f"DEBUG: Successfully mapped {len(details_list)} items.")

            return Response({"status": "success", "data": data}, status=status.HTTP_200_OK)

        except Exception as map_err:
            print("DEBUG: Error during data mapping!")
            print(traceback.format_exc()) # Print full error stack
            raise map_err

    except Exception as e:
        # LOG 5: Critical Failure
        print("\n!!! CRITICAL ERROR IN INVOICE PRINT API !!!")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        print(traceback.format_exc()) # Yeh terminal mein batayega kaunsi line pe error hai
        
        return Response({
            "status": "error", 
            "message": "Internal Server Error",
            "debug_info": str(e) # Sirf development ke liye
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminOrSuperuser])
def get_advanced_ledger_report(request):
    try:
        # --- 1. QUERY PARAMETERS ---
        party_name = request.query_params.get('name', None)
        from_date = request.query_params.get('from_date', None)
        to_date = request.query_params.get('to_date', None)
        inv_type = request.query_params.get('type', None) # SALES / PURCHASE
        search_query = request.query_params.get('search', None) # INV NO or NAME search

        # --- 2. BASE FILTERS (Live Records Only) ---
        sales_q = Q(delflag=' ')
        purchase_q = Q(delflag=' ')

        # --- 3. DYNAMIC FILTERING ---
        
        # Date Range Filter
        if from_date and to_date:
            sales_q &= Q(trdate__range=[from_date, to_date])
            purchase_q &= Q(trdate__range=[from_date, to_date])

        # Unified Search (Invoice No OR Party Name OR GST)
        if search_query:
            unified_filter = (
                Q(invno__icontains=search_query) | 
                Q(inname__icontains=search_query) |
                Q(invgst__icontains=search_query)
            )
            sales_q &= unified_filter
            purchase_q &= unified_filter

        # Specific Party Name Filter (if separate from search)
        if party_name:
            sales_q &= Q(inname__icontains=party_name)
            purchase_q &= Q(inname__icontains=party_name)

        # --- 4. DATA FETCHING ---
        final_data = []

        # Fetch Sales if type is 'SALES' or 'ALL'
        if not inv_type or inv_type.upper() == 'SALES' or inv_type.upper() == 'ALL':
            sales_qs = SalesLedger.objects.filter(sales_q)
            for item in sales_qs:
                d = model_to_dict(item)
                d['source'] = 'SALES'
                final_data.append(d)

        # Fetch Purchase if type is 'PURCHASE' or 'ALL'
        if not inv_type or inv_type.upper() == 'PURCHASE' or inv_type.upper() == 'ALL':
            purchase_qs = PurchaseLedger.objects.filter(purchase_q)
            for item in purchase_qs:
                d = model_to_dict(item)
                d['source'] = 'PURCHASE'
                final_data.append(d)

        # --- 5. SORTING & SUMMARY ---
        # Sort by Transaction Date (Latest First)
        final_data.sort(key=lambda x: x['trdate'], reverse=True)

        # Total Calculation for Summary
        total_dr = sum(float(x['trdr']) for x in final_data)
        total_cr = sum(float(x['trcr']) for x in final_data)

        return Response({
            "status": "success",
            "total_records": len(final_data),
            "summary": {
                "total_debit": total_dr,
                "total_credit": total_cr,
                "closing_balance": total_dr - total_cr
            },
            "filters_applied": {
                "date_range": f"{from_date} to {to_date}" if from_date else "All Time",
                "type": inv_type if inv_type else "ALL",
                "search": search_query
            },
            "data": final_data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"💥 LEDGER REPORT FATAL ERROR: {str(e)}", exc_info=True)
        return Response({
            "status": "error",
            "message": "Internal Server Error",
            "details": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SalesViewSet(viewsets.ModelViewSet):
    queryset = SalesHeader.objects.filter(delflag=' ').order_by('-created_at')
    serializer_class = SalesHeaderSerializer
    permission_classes = [IsAdminOrSuperuser, IsAccountActive]

    def create(self, request, *args, **kwargs):
        logger.info(f"🚀 Attempting to create Sales Bill. Data: {request.data}")
        
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            try:
                # Serializer ke create() method mein logic handle hoga
                serializer.save()
                logger.info(f"✅ Sales Bill Created Successfully: {serializer.data.get('billno')}")
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            except Exception as e:
                # Agar DB save ya Ledger entry fail hui toh yahan pakda jayega
                logger.error(f"💥 DATABASE SAVE ERROR (Sales): {str(e)}", exc_info=True)
                return Response(
                    {"error": "Database error occurred while saving sales bill.", "details": str(e)}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            # Agar frontend ne galat data bheja
            logger.warning(f"❌ VALIDATION FAILED (Sales): {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PurchaseViewSet(viewsets.ModelViewSet):
    queryset = PurchaseHeader.objects.filter(delflag=' ').order_by('-created_at')
    serializer_class = PurchaseHeaderSerializer
    permission_classes = [IsAdminOrSuperuser, IsAccountActive]

    def create(self, request, *args, **kwargs):
        logger.info(f"🚀 Attempting to create Purchase Bill. Data: {request.data}")
        
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            try:
                serializer.save()
                logger.info(f"✅ Purchase Bill Created Successfully: {serializer.data.get('billno')}")
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            except Exception as e:
                logger.error(f"💥 DATABASE SAVE ERROR (Purchase): {str(e)}", exc_info=True)
                return Response(
                    {"error": "Database error occurred while saving purchase bill.", "details": str(e)}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            logger.warning(f"❌ VALIDATION FAILED (Purchase): {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)