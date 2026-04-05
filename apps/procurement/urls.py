from django.urls import path
from . import views

app_name = 'procurement'

urlpatterns = [
    path('', views.po_list, name='po_list'),
    path('<uuid:pk>/', views.po_detail, name='po_detail'),
    path('create/', views.po_create, name='po_create'),
]
