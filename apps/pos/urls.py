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
    # Cancellation workflow
    path('cancel/request/<uuid:pk>/', views.request_cancellation, name='cancel_request'),
    path('cancel/approve/<uuid:pk>/', views.approve_cancellation, name='cancel_approve'),
    path('cancel/reject/<uuid:pk>/', views.reject_cancellation, name='cancel_reject'),
    path('cancel/pending/', views.pending_cancellations, name='cancel_pending'),
    # Offline API
    path('api/products/', views.api_products, name='api_products'),
    path('api/sync/', views.api_sync, name='api_sync'),
]
