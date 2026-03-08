from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_protect
from .models import *
# Create your views here.
def index(request):
    return HttpResponse('Hello to login app')

def login(request):
    return render(request,"login.html")

@csrf_protect
def regestration(request):
    if request.method=="POST":
        data = request.POST
        first = data.get('first')
        last = data.get('last')
        email = data.get('email')
        password = data.get('password')
        contact = data.get('contact')
        gender = data.get('gender')
        print (first," ",last," ",email," ",contact," ",gender)

        Reg.objects.create(
             first=first,
             last=last,
             email=email,
             password=password,
             contact=contact,
             gender=gender,
        )

        return redirect('/regestration/')
    return render(request,"reg.html")


@csrf_protect
def receipes(request):
    if request.method=="POST":
        data = request.POST
        receipe_name=data.get('receipe_name')
        receipe_desc=data.get('receipe_desc')
        receipe_img=request.FILES.get('receipe_img')
        print(receipe_desc," ",receipe_name,"" ,receipe_img)

        Receipe.objects.create(
            receipe_name=receipe_name,
            receipe_desc=receipe_desc,
            receipe_img=receipe_img,

        )
        return redirect('/receipes/')
    
    queryset = Receipe.objects.all()
    context= {'receipe':queryset}

    return render(request,"receipes.html",context)

def successfully(request):
    return render(request,"successfully.html")