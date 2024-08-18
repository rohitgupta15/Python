from django.http import HttpResponse
from django.shortcuts import render

def homePage(request):
    data={
        'title':'Home Page1',
        'bdata':'Welcome to Home page',
        'clist':['java','python','django'],
         'number':[10,20,30,40,50],
         'studentdetails':[
             {'name':'Rohit Gupta','phone':98646464},
             {'name':'Rajesh Kumar','phone':989889889}
         ]
    }
    
    return render(request,"index.html",data)


def aboutus(reuqest):
    return HttpResponse("Welcome to aboutus screen")

def cources(reuqest):
    return HttpResponse("<b> Welcome to cources screen </b>")

def contactus(reuqest):
    return HttpResponse("Welcome to contactus screen")

def courceDetails(reuqest,courseid):
    return HttpResponse(courseid)