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
    # Types (replaces Categories)
    path('types/', views.type_list, name='type_list'),
    path('types/add/', views.add_type, name='add_type'),
    path('types/delete/<int:pk>/', views.delete_type, name='delete_type'),
    path('types/edit/<int:pk>/', views.edit_type, name='edit_type'),
]
