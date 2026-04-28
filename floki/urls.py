from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('inventory/', include('catalogue.urls')),
    path('pos/', include('pos.urls')),
    path('procurement/', include('procurement.urls')),
    path('promotions/', include('promotions.urls')),
    path('audit/', include('audit_module.urls')),
    path('expenses/', include('expenses.urls')),
    path('reports/', include('reports.urls')),
    path('payroll/', include('payroll.urls')),
    path('trail/', include('core.urls')),
    path('', lambda r: redirect('accounts:login')),
]
