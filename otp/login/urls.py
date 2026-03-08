from django.urls import path

#now import the views.py file into this code
from . import views
urlpatterns=[
path('',views.index),
path('login/',views.login),
path('regestration/',views.regestration,name="regestration"),
path('receipes/',views.receipes,name="receipes"),
path('successfully/',views.successfully,name="/successfully"),
]

