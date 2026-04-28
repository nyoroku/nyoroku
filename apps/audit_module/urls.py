from django.urls import path
from . import views

app_name = 'audit_module'

urlpatterns = [
    path('', views.audit_list, name='list'),
    path('initiate/', views.audit_initiate, name='initiate'),
    path('<uuid:pk>/', views.audit_detail, name='detail'),
    path('<uuid:pk>/submit/', views.audit_submit, name='submit'),
    path('<uuid:pk>/print/', views.audit_print, name='print'),
]
