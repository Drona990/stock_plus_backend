from rest_framework import viewsets, status
from rest_framework.response import Response
import logging

from master.serializers.ledger_serializes import LedgerSerializer
from ..models import Ledger

# Logging setup
logger = logging.getLogger(__name__)

class LedgerViewSet(viewsets.ModelViewSet):
    queryset = Ledger.objects.all().order_by('-updated_at')
    serializer_class = LedgerSerializer

    def create(self, request, *args, **kwargs):
        logger.info(f"Incoming POST request data: {request.data}")
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            self.perform_create(serializer)
            logger.info(f"Ledger '{request.data.get('name')}' created successfully.")
            return Response({
                "message": "Ledger Created Successfully",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)
        
        # AGAR VALIDATION FAIL HUA:
        logger.error(f"POST 400 Bad Request - Errors: {serializer.errors}")
        return Response({
            "error": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        logger.info(f"Incoming PUT request for ID {kwargs.get('pk')}: {request.data}")
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        
        if serializer.is_valid():
            self.perform_update(serializer)
            logger.info(f"Ledger ID {instance.id} updated successfully (Flag: M).")
            return Response({
                "message": "Ledger Updated Successfully (Flag set to 'M')",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        # AGAR VALIDATION FAIL HUA:
        logger.error(f"PUT 400 Bad Request - Errors: {serializer.errors}")
        return Response({
            "error": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)