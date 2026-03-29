from django.urls import path, include
from rest_framework.routers import DefaultRouter
from master.views.uom_views import UOMViewSet
from .views.customer_supplier_views import CustomerMasterViewSet, SupplierMasterViewSet

router = DefaultRouter()
router.register(r'customers', CustomerMasterViewSet)
router.register(r'suppliers', SupplierMasterViewSet)
router.register(r'uom', UOMViewSet)




urlpatterns = [
    path('', include(router.urls)),
]