from django.urls import path, include
from rest_framework.routers import DefaultRouter
from transaction.views.cash_transaction_views import CashTransactionViewSet, LedgerReportViewSet
from transaction.views.salse_purchase_views import PurchaseViewSet, SalesViewSet, get_advanced_ledger_report


router = DefaultRouter()
router.register(r'salse_transaction', SalesViewSet)
router.register(r'purchase_transaction', PurchaseViewSet)
router.register(r'cash-transactions', CashTransactionViewSet)
router.register(r'cash-ledger-report', LedgerReportViewSet, basename='cash-ledger-report')



urlpatterns = [
    path('', include(router.urls)),
    path('ledger-report/', get_advanced_ledger_report, name='ledger-report'),
]