from django.urls import path
from . import views

app_name = 'catalogue'

urlpatterns = [
    path('', views.inventory_list, name='inventory'),
    path('add/', views.add_product, name='add_product'),
    path('approve/<uuid:pk>/', views.approve_product, name='approve_product'),
    path('delete/<uuid:pk>/', views.delete_product, name='delete_product'),
]
