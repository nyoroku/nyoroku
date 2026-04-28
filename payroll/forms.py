# payroll/forms.py

from django import forms
from .models import PayrollPeriod, PayrollAdjustment, TaxDeductionRule, UserTaxProfile


class PayrollPeriodForm(forms.ModelForm):
    class Meta:
        model = PayrollPeriod
        fields = ['name', 'start_date', 'end_date', 'pay_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'pay_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., August 2025 Payroll'}),
        }


class PayrollAdjustmentForm(forms.ModelForm):
    class Meta:
        model = PayrollAdjustment
        fields = ['type', 'name', 'amount']
        widgets = {
            'type': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Travel Allowance'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }


class UserTaxProfileForm(forms.ModelForm):
    class Meta:
        model = UserTaxProfile
        fields = ['applicable_deductions', 'personal_relief']
        widgets = {
            'applicable_deductions': forms.CheckboxSelectMultiple(),
            'personal_relief': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }


class TaxDeductionRuleForm(forms.ModelForm):
    class Meta:
        model = TaxDeductionRule
        fields = ['name', 'percentage_rate', 'fixed_amount', 'calculation_base', 'is_active', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'percentage_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'fixed_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'calculation_base': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        percentage_rate = cleaned_data.get('percentage_rate')
        fixed_amount = cleaned_data.get('fixed_amount')

        if not percentage_rate and not fixed_amount:
            raise forms.ValidationError("Either percentage rate or fixed amount must be specified.")

        if percentage_rate and fixed_amount:
            raise forms.ValidationError("Cannot specify both percentage rate and fixed amount.")

        return cleaned_data