from django.urls import path
from . import views

app_name = 'promotions'

urlpatterns = [
    path('', views.promotion_list, name='list'),
    path('create/', views.promotion_create, name='create'),
    path('<uuid:pk>/edit/', views.promotion_edit, name='edit'),
    path('<uuid:pk>/toggle/', views.promotion_toggle, name='toggle'),
    path('<uuid:pk>/delete/', views.promotion_delete, name='delete'),
    path('hampers/', views.hamper_list, name='hamper_list'),
    path('hampers/create/', views.hamper_create, name='hamper_create'),
    path('hampers/<uuid:pk>/edit/', views.hamper_edit, name='hamper_edit'),
    path('hampers/<uuid:pk>/delete/', views.hamper_delete, name='hamper_delete'),
]
