from django.urls import path
from . import views

app_name = 'procurement'

urlpatterns = [
    path('', views.po_list, name='po_list'),
    path('<uuid:pk>/', views.po_detail, name='po_detail'),
    path('create/', views.po_create, name='po_create'),
    
    # Suppliers
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/create/', views.supplier_create, name='supplier_create'),
    path('suppliers/<uuid:pk>/edit/', views.supplier_edit, name='supplier_edit'),

    # PO Builder (HTMX/Dynamic)
    path('<uuid:pk>/add-item/', views.po_add_item, name='po_add_item'),
    path('<uuid:pk>/remove-item/<int:index>/', views.po_remove_item, name='po_remove_item'),
    path('<uuid:pk>/update-qty/<int:index>/', views.po_update_qty, name='po_update_qty'),
    path('product-search/', views.product_search, name='product_search'),

    # PO Workflow
    path('<uuid:pk>/submit/', views.po_submit, name='po_submit'),
    path('<uuid:pk>/approve/', views.po_approve, name='po_approve'),
    path('<uuid:pk>/receive/', views.po_receive, name='po_receive'),
]
