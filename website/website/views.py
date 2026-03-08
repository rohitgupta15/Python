from django.http import HttpResponse
from django.shortcuts import render

def about(request):
    return HttpResponse("hello world")
    
def index(request):
    return render(request,"index.html")

def aboutus(request):
    return render(request,"about.html")

def contact(request):
    return render(request,"contact.html")

def register(request):
    return render(request,"register.html")

def login(request):
    return render(request,"login.html")

def data(request):
    dataDic={
        'title':'title data',
        'bdata':'welcome to bdata page',
        'clist':['java','oracle','python','django'],'student': [{'name':'rohit','phone':'8990'},
                                                              {'name':'Ashu','phone':'8990'}]}
    return render(request,"data.html",dataDic)