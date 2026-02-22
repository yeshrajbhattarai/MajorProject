from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import ConsentRequest
from .serializers import ConsentRequestSerializer


@api_view(['POST'])
def create_consent(request):
    serializer = ConsentRequestSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors)