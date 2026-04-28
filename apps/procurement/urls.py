from django.urls import path
from . import views

app_name = 'procurement'

urlpatterns = [
    path('', views.po_list, name='po_list'),
    path('create/', views.po_create, name='po_create'),
    path('<uuid:pk>/', views.po_detail, name='po_detail'),
    path('<uuid:pk>/add-item/', views.po_add_item, name='po_add_item'),
    path('<uuid:pk>/remove-item/<uuid:item_pk>/', views.po_remove_item, name='po_remove_item'),
    path('<uuid:pk>/update-item/<uuid:item_pk>/', views.po_update_item, name='po_update_item'),
    path('<uuid:pk>/submit/', views.po_submit, name='po_submit'),
    path('<uuid:pk>/approve/', views.po_approve, name='po_approve'),
    path('<uuid:pk>/receive/', views.po_receive_goods, name='po_receive'),
    path('<uuid:pk>/cancel/', views.po_cancel, name='po_cancel'),
    path('product-search/', views.product_search, name='product_search'),
    path('api/product-search/', views.product_search_json, name='product_search_json'),

    # Suppliers
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/create/', views.supplier_create, name='supplier_create'),
    path('suppliers/<uuid:pk>/edit/', views.supplier_edit, name='supplier_edit'),
    path('suppliers/<uuid:pk>/delete/', views.supplier_delete, name='supplier_delete'),
]
