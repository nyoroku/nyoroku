from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('sales-by-category/', views.sales_by_category, name='sales_by_category'),
    path('product-performance/', views.product_performance, name='product_performance'),
    path('margin/', views.margin_report, name='margin_report'),
    path('supplier-spend/', views.supplier_spend, name='supplier_spend'),
    path('stock-valuation/', views.stock_valuation, name='stock_valuation'),
    path('batch-expiry/', views.batch_expiry, name='batch_expiry'),
    path('po-history/', views.po_history, name='po_history'),
    path('promotion-effectiveness/', views.promotion_effectiveness, name='promotion_effectiveness'),
    path('export/<str:report_type>/', views.export_csv, name='export_csv'),
]
