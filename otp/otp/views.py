from django.http import HttpResponse

from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from login.views import *

def home(request):
    return HttpResponse('Welcome to home page')

def index(request):
  return HttpResponse("Hello Geeks")
