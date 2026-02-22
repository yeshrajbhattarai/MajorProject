from django.shortcuts import render
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import ConsentRequest
from .serializers import ConsentRequestSerializer
from django.db import IntegrityError # this is the error name - if someone accidentally request same patient record to the same hospital multiple times
import logging


# Create your views here.

logger = logging.getLogger(__name__)
@api_view(['POST'])
def create_consent(request):
    serializer = ConsentRequestSerializer(data=request.data)
    if serializer.is_valid():
        try:
            serializer.save()
        except IntegrityError:
            logger.warning(
                f"Duplicate consent request attempted"
            )
            return Response(
                {"error": "Consent request already exists."},
                status=400
            )
        return Response(serializer.data)
    return Response(serializer.errors)