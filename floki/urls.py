from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

from django.views.generic import TemplateView

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
    path('manifest.json', TemplateView.as_view(template_name='manifest.json', content_type='application/json'), name='manifest_json'),
    path('sw.js', TemplateView.as_view(template_name='sw.js', content_type='application/javascript'), name='sw_js'),
    path('offline.html', TemplateView.as_view(template_name='offline.html'), name='offline_html'),
    path('', lambda r: redirect('accounts:login')),
]
