from django.urls import path
from . import views

app_name = 'expenses'

urlpatterns = [
    path('', views.expense_list, name='list'),
    path('add/', views.add_expense, name='add_expense'),
    path('delete/<uuid:pk>/', views.delete_expense, name='delete_expense'),
]
