from django import forms
from .models import CashHandover


class CashHandoverForm(forms.ModelForm):
    class Meta:
        model = CashHandover
        fields = ['cash_amount', 'mpesa_amount']
        widgets = {
            'cash_amount': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 rounded-lg border border-gray-300 text-sm font-mono '
                         'focus:ring-2 focus:ring-amber-400 focus:border-amber-400 outline-none',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00',
            }),
            'mpesa_amount': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 rounded-lg border border-gray-300 text-sm font-mono '
                         'focus:ring-2 focus:ring-amber-400 focus:border-amber-400 outline-none',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00',
            }),
        }
