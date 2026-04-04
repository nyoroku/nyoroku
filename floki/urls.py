from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('inventory/', include('catalogue.urls')),
    path('pos/', include('pos.urls')),
    path('expenses/', include('expenses.urls')),
    path('reports/', include('reports.urls')),
    path('', lambda r: redirect('accounts:login')), # Default entry point
]
