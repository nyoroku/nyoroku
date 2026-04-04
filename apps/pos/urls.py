from django.urls import path
from . import views

app_name = 'pos'

urlpatterns = [
    path('', views.index, name='index'),
    path('checkout/', views.checkout, name='checkout'),
    path('receipt/<uuid:pk>/', views.receipt_print, name='receipt_print'),
    path('coupon/validate/', views.validate_coupon, name='validate_coupon'),
    # Coupon management
    path('coupons/', views.coupon_list, name='coupon_list'),
    path('coupons/add/', views.add_coupon, name='add_coupon'),
    path('coupons/toggle/<uuid:pk>/', views.toggle_coupon, name='toggle_coupon'),
    path('coupons/delete/<uuid:pk>/', views.delete_coupon, name='delete_coupon'),
]
