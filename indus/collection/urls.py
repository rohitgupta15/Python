from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('reception/', views.reception, name='reception'),
    path('receipting/', views.receipting, name='receipting'),
    path('receipting/<int:payment_id>/edit/', views.receipting_edit, name='receipting_edit'),
    path('acm/', views.acm, name='acm'),
    path('agency/', views.agency, name='agency'),
]
