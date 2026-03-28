from django.urls import path, include
from rest_framework.routers import DefaultRouter

from master.views.supplier_views import SupplierMasterViewSet
from .views.customer_views import CustomerMasterViewSet

router = DefaultRouter()
router.register(r'customers', CustomerMasterViewSet)
router.register(r'suppliers', SupplierMasterViewSet)


urlpatterns = [
    path('', include(router.urls)),
]