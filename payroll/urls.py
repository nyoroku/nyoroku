# payroll/urls.py

from django.urls import path
from . import views

app_name = 'payroll'

urlpatterns = [
    # Main payroll management
    path('payroll/', views.payroll_period_list_view, name='period_list'),
    path('new/', views.run_new_payroll_view, name='run_new'),
    path('period/<int:period_id>/', views.payroll_period_detail_view, name='period_detail'),

    # Payroll status management
    path('period/<int:period_id>/approve/', views.approve_payroll, name='approve_payroll'),
    path('period/<int:period_id>/mark-paid/', views.mark_payroll_as_paid, name='mark_paid'),
    path('period/<int:period_id>/recalculate/', views.recalculate_payroll, name='recalculate_payroll'),
    path('period/<int:period_id>/print-summary/',
         views.print_payroll_summary,
         name='print_payroll_summary'),
    path('entry/<int:entry_id>/redeem-points/', views.redeem_waiter_points, name='redeem_waiter_points'),
    path('period/<int:period_id>/print-register/',
         views.print_payroll_register,
         name='print_payroll_register'),



    path('period/<int:period_id>/export-csv/',
         views.export_payroll_csv,
         name='export_payroll_csv'),
    # User profile management
    path('user/<uuid:user_id>/profile/', views.user_payroll_profile_view, name='user_profile'),

    # Adjustments
    path('entry/<int:entry_id>/add-adjustment/', views.add_one_time_adjustment, name='add_one_time_adjustment'),
    path('adjustment/<int:adj_id>/remove/', views.remove_adjustment, name='remove_adjustment'),

    # Payslips
    path('payslip/<int:payslip_id>/', views.payslip_detail_view, name='payslip_detail'),
    path('payslip/<int:payslip_id>/pdf/', views.generate_payslip_pdf, name='payslip_pdf'),

    # Tax rules management
    path('tax-rules/', views.tax_rules_management, name='tax_rules'),
]