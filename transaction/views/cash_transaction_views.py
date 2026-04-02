import logging
from django.db.models import Sum, Q  # <--- CRITICAL: 'Q' import fix karega 500 error
from rest_framework.response import Response 
from rest_framework import viewsets, filters, status
from django_filters.rest_framework import DjangoFilterBackend
from decimal import Decimal
from rest_framework.decorators import action

# Apne models aur serializers ke sahi path check karein
from master.models import Ledger
from core.permissions import IsAdminOrSuperuser
from transaction.models import CashTransaction
from transaction.serializers.cash_transaction_serializer import CashTransactionSerializer

# Logger setup taaki terminal mein error dikhe
logger = logging.getLogger(__name__)

class CashTransactionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminOrSuperuser]
    queryset = CashTransaction.objects.all().order_by('-created_at')
    serializer_class = CashTransactionSerializer
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['voucher_type', 'ledger']
    search_fields = ['ledger__name', 'narration', 'voucher_no']

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user.username if self.request.user.is_authenticated else 'ADMIN'
        )


class LedgerReportViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminOrSuperuser]
    queryset = Ledger.objects.all()

    @action(detail=True, methods=['get'])
    def detailed_report(self, request, pk=None):
        try:
            # 1. Fetch Ledger Object
            ledger = self.get_object()
            logger.info(f"Generating report for Ledger ID: {pk} - {ledger.name}")
            
            # 2. Filter Transactions
            transactions = CashTransaction.objects.filter(ledger=ledger).order_by('date', 'created_at')
            serializer = CashTransactionSerializer(transactions, many=True)

            # 3. Aggregation with Q Filters (Strictly for RECEIPT/PAYMENT)
            res = transactions.aggregate(
                total_receipts=Sum('amount', filter=Q(voucher_type='RECEIPT')),
                total_payments=Sum('amount', filter=Q(voucher_type='PAYMENT'))
            )
            
            # Decimal conversion to avoid float errors
            t_receipts = res['total_receipts'] or Decimal('0.00')
            t_payments = res['total_payments'] or Decimal('0.00')

            # Opening Balance from Master Table
            op_debit = ledger.opening_balance_debit or Decimal('0.00')
            op_credit = ledger.opening_balance_credit or Decimal('0.00')
            
            # Formula: (Op DR - Op CR) + Total Payments - Total Receipts
            net_balance = (op_debit - op_credit) + t_payments - t_receipts

            logger.info(f"Calculation Success: Net Balance = {net_balance}")

            return Response({
                "ledger_info": {
                    "id": ledger.id,
                    "name": ledger.name,
                    "group": ledger.group,
                    "opening_debit": float(op_debit),
                    "opening_credit": float(op_credit),
                },
                "transactions": serializer.data,
                "summary": {
                    "total_receipts": float(t_receipts),
                    "total_payments": float(t_payments),
                    "closing_balance": float(abs(net_balance)),
                    "type": "DR (Receivable)" if net_balance >= 0 else "CR (Payable)"
                }
            })

        except Exception as e:
            # Ye terminal mein print hoga agar code crash hua
            logger.error(f"CRITICAL ERROR in Detailed Report: {str(e)}")
            return Response({
                "error": "Server Calculation Error",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)