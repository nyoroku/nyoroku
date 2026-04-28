from django.urls import path
from . import views

app_name = 'pos'

urlpatterns = [
    path('', views.index, name='index'),
    path('checkout/', views.checkout, name='checkout'),
    path('mpesa/stk-push/', views.mpesa_stk_push, name='mpesa_stk_push'),
    path('mpesa/status/<str:checkout_id>/', views.mpesa_status, name='mpesa_status'),
    path('receipt/<uuid:pk>/', views.receipt_view, name='receipt'),
    path('void/<uuid:pk>/', views.void_sale, name='void'),
    path('park/', views.park_sale, name='park'),
    path('parked/', views.parked_sales_list, name='parked_list'),
    path('resume/<uuid:pk>/', views.resume_sale, name='resume'),
    path('history/', views.sale_history, name='history'),
]
