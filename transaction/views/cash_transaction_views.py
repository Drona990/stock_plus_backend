import logging
from django.db.models import Sum, Q , F  # <--- CRITICAL: 'Q' import fix karega 500 error
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
from ..models import JournalItem 



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
    queryset = Ledger.objects.all()

    @action(detail=True, methods=['get'])
    def detailed_report(self, request, pk=None):
        try:
            ledger = self.get_object()
            
            # 1. Fetch Cash Transactions
            cash_txns = CashTransaction.objects.filter(ledger=ledger).annotate(
                v_type=F('voucher_type'),
                v_no=F('voucher_no')
            ).values('v_no', 'date', 'amount', 'narration', 'v_type')

            # 2. Fetch Journal Transactions (JV)
            journal_txns = JournalItem.objects.filter(ledger=ledger).annotate(
                v_no=F('voucher__voucher_no'),
                date=F('voucher__date'),
                narration=F('voucher__narration'),
                v_type=F('type') # DEBIT or CREDIT
            ).values('v_no', 'date', 'amount', 'narration', 'v_type')

            # 3. Merge and Sort by Date
            all_txns = sorted(list(cash_txns) + list(journal_txns), key=lambda x: x['date'])

            # 4. Calculation
            t_dr = Decimal('0.00')
            t_cr = Decimal('0.00')

            for t in all_txns:
                # Rule: PAYMENT/DEBIT is DR, RECEIPT/CREDIT is CR
                if t['v_type'] in ['PAYMENT', 'DEBIT']:
                    t_dr += Decimal(str(t['amount']))
                else:
                    t_cr += Decimal(str(t['amount']))

            op_dr = ledger.opening_balance_debit or Decimal('0.00')
            op_cr = ledger.opening_balance_credit or Decimal('0.00')
            
            # Closing Balance = (Op DR + Total DR) - (Op CR + Total CR)
            net_bal = (op_dr + t_dr) - (op_cr + t_cr)

            return Response({
                "ledger_info": {"name": ledger.name, "group": ledger.group},
                "transactions": all_txns,
                "summary": {
                    "total_dr": float(t_dr + op_dr),
                    "total_cr": float(t_cr + op_cr),
                    "closing_balance": float(abs(net_bal)),
                    "type": "DR (Receivable)" if net_bal >= 0 else "CR (Payable)"
                }
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)