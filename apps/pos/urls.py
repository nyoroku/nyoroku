from django.urls import path
from . import views

app_name = 'pos'

urlpatterns = [
    path('', views.index, name='index'),
    path('checkout/', views.checkout, name='checkout'),
    path('receipt/<uuid:pk>/', views.receipt_print, name='receipt_print'),
]
