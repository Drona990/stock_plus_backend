from rest_framework import viewsets, filters
from transaction.serializers.journal_entry_serializers import JournalVoucherSerializer
from ..models import JournalVoucher

class JournalVoucherViewSet(viewsets.ModelViewSet):
    queryset = JournalVoucher.objects.all().order_by('-id')
    serializer_class = JournalVoucherSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['voucher_no', 'narration', 'items__ledger__name']