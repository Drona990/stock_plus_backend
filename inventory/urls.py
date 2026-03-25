from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DashboardViewSet, FetchBillForReturnView, InventoryCategoryViewSet, MasterReportViewSet, ProcessReturnExchangeView, ProductGroupViewSet, ProductSubGroupViewSet, SalesViewSet, StockTransactionViewSet, LocationViewSet, health_check

)

router = DefaultRouter()
router.register(r'locations', LocationViewSet)
router.register(r'categories', InventoryCategoryViewSet)
router.register(r'product-groups', ProductGroupViewSet)
router.register(r'product-subgroups', ProductSubGroupViewSet, basename='productsubgroup')
router.register(r'stock-transactions', StockTransactionViewSet)
router.register(r'sales', SalesViewSet, basename='sales')
router.register(r'dashboard', DashboardViewSet, basename='dashboard')
router.register(r'reports', MasterReportViewSet, basename='reports')


urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('returns/fetch/<path:invoice_no>/', FetchBillForReturnView.as_view(), name='fetch-bill'),
    path('returns/process/', ProcessReturnExchangeView.as_view(), name='process-return-exchange'),
    path('', include(router.urls)),
]