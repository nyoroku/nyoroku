from django.urls import path
from . import views

app_name = 'catalogue'

urlpatterns = [
    path('', views.inventory_list, name='inventory'),
    path('add/', views.add_product, name='add_product'),
    path('edit/', views.edit_product, name='edit_product'),
    path('approve/<uuid:pk>/', views.approve_product, name='approve_product'),
    path('delete/<uuid:pk>/', views.delete_product, name='delete_product'),
    
    path('pending-actions/', views.pending_actions, name='pending_actions'),
    path('pending-actions/<uuid:pk>/resolve/', views.resolve_action, name='resolve_action'),
    # Categories
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.add_category, name='add_category'),
    path('categories/delete/<int:pk>/', views.delete_category, name='delete_category'),
]
