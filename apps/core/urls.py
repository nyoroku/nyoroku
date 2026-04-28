from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.audit_trail_list, name='audit_trail'),
    path('export/', views.audit_trail_export, name='audit_trail_export'),
]
