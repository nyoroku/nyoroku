# payroll/admin.py

from django.contrib import admin
from .models import (PayrollPeriod, PayrollEntry, PayrollAdjustment,
                    TaxDeductionRule, UserTaxProfile, Payslip, StatutoryDeduction)


@admin.register(TaxDeductionRule)
class TaxDeductionRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'percentage_rate', 'fixed_amount', 'calculation_base', 'is_active']
    list_filter = ['calculation_base', 'is_active']
    search_fields = ['name', 'description']


@admin.register(UserTaxProfile)
class UserTaxProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'personal_relief']
    search_fields = ['user__first_name', 'user__last_name']
    filter_horizontal = ['applicable_deductions']


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'pay_date', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name']
    readonly_fields = ['approved_by', 'approved_at', 'paid_by', 'paid_at']


class PayrollAdjustmentInline(admin.TabularInline):
    model = PayrollAdjustment
    extra = 0
    fields = ['type', 'name', 'amount']


class StatutoryDeductionInline(admin.TabularInline):
    model = StatutoryDeduction
    extra = 0
    readonly_fields = ['rule', 'calculated_amount']


@admin.register(PayrollEntry)
class PayrollEntryAdmin(admin.ModelAdmin):
    list_display = ['user', 'period', 'gross_pay', 'total_deductions', 'net_pay']
    list_filter = ['period__status', 'period']
    search_fields = ['user__first_name', 'user__last_name', 'period__name']
    readonly_fields = ['base_pay', 'total_allowances', 'total_deductions',
                      'total_statutory_deductions', 'gross_pay', 'net_pay']
    inlines = [PayrollAdjustmentInline, StatutoryDeductionInline]


@admin.register(PayrollAdjustment)
class PayrollAdjustmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'amount', 'payroll_entry', 'user', 'created_at']
    list_filter = ['type', 'created_at']
    search_fields = ['name']


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ['payslip_number', 'payroll_entry', 'generated_at']
    search_fields = ['payslip_number', 'payroll_entry__user__first_name',
                    'payroll_entry__user__last_name']
    readonly_fields = ['payslip_number', 'generated_at']