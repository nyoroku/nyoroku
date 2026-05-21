from django.urls import path
from . import views

app_name = 'audit_module'

urlpatterns = [
    path('', views.audit_list, name='list'),
    path('initiate/', views.audit_initiate, name='initiate'),
    path('<uuid:pk>/', views.audit_detail, name='detail'),
    path('<uuid:pk>/submit/', views.audit_submit, name='submit'),
    path('<uuid:pk>/print/', views.audit_print, name='print'),
    path('items/<uuid:item_id>/validate/', views.audit_item_validate, name='item_validate'),
    path('items/<uuid:item_id>/dispute/', views.audit_item_dispute, name='item_dispute'),
    path('staff-surplus/', views.staff_surplus, name='staff_surplus'),
]
