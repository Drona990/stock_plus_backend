from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DashboardViewSet, InventoryCategoryViewSet, ProductGroupViewSet, ProductSubGroupViewSet, SalesViewSet, StockTransactionViewSet, LocationViewSet

)

router = DefaultRouter()
router.register(r'locations', LocationViewSet)
router.register(r'categories', InventoryCategoryViewSet)
router.register(r'product-groups', ProductGroupViewSet)
router.register(r'product-subgroups', ProductSubGroupViewSet, basename='productsubgroup')
router.register(r'stock-transactions', StockTransactionViewSet)
router.register(r'sales', SalesViewSet, basename='sales')
router.register(r'dashboard', DashboardViewSet, basename='dashboard')

urlpatterns = [
    path('', include(router.urls)),
]