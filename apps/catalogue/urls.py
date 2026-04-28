from django.urls import path
from . import views

app_name = 'catalogue'

urlpatterns = [
    path('', views.inventory_list, name='inventory'),
    path('add/', views.add_product, name='add_product'),
    path('edit/', views.edit_product, name='edit_product'),
    path('<uuid:pk>/edit/form/', views.edit_product_form, name='edit_product_form'),
    path('delete/<uuid:pk>/', views.delete_product, name='delete_product'),
    path('bulk-delete/', views.bulk_delete_products, name='bulk_delete'),

    # Categories
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.add_category, name='add_category'),
    path('categories/<uuid:pk>/edit/', views.edit_category, name='edit_category'),
    path('categories/<uuid:pk>/delete/', views.delete_category, name='delete_category'),

    # Sub-categories
    path('subcategories/add/', views.add_subcategory, name='add_subcategory'),
    path('subcategories/<uuid:pk>/delete/', views.delete_subcategory, name='delete_subcategory'),

    # Batches
    path('batches/<uuid:product_pk>/', views.batch_list, name='batch_list'),
    path('batches/<uuid:pk>/quarantine/', views.quarantine_batch, name='quarantine_batch'),
    path('adjust-stock/', views.manual_stock_adjustment, name='adjust_stock'),
    path('manual-cut/', views.manual_cut, name='manual_cut'),
]
