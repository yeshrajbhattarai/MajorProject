from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
def consent_request(req):
    return HttpResponse("Hello")