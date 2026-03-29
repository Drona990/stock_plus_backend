from django.urls import path, include
from rest_framework.routers import DefaultRouter
from transaction.views.salse_purchase_views import PurchaseViewSet, SalesViewSet


router = DefaultRouter()
router.register(r'salse_transaction', SalesViewSet)
router.register(r'purchase_transaction', PurchaseViewSet)



urlpatterns = [
    path('', include(router.urls)),
]