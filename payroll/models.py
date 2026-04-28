# payroll/models.py

from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.core.exceptions import ValidationError
from accounts.models import User  # Import your POS User model
from decimal import Decimal
import uuid


class TaxDeductionRule(models.Model):
    """Predefined tax and statutory deductions with percentage rates"""

    class CalculationBase(models.TextChoices):
        BASIC_SALARY = 'BASIC', 'Basic Salary'
        GROSS_PAY = 'GROSS', 'Gross Pay'
        FIXED_AMOUNT = 'FIXED', 'Fixed Amount'

    name = models.CharField(max_length=100, help_text="e.g., 'PAYE', 'NHIF', 'NSSF'")
    percentage_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                          help_text="Percentage rate (e.g., 30.00 for 30%)")
    fixed_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                       help_text="Fixed amount if not percentage-based")
    calculation_base = models.CharField(max_length=10, choices=CalculationBase.choices,
                                        default=CalculationBase.BASIC_SALARY)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    def __str__(self):
        if self.percentage_rate:
            return f"{self.name} ({self.percentage_rate}% of {self.get_calculation_base_display()})"
        return f"{self.name} (Fixed: {self.fixed_amount})"


class UserTaxProfile(models.Model):
    """User's tax profile - which deductions apply to them"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tax_profile')

    # Which statutory deductions apply to this user
    applicable_deductions = models.ManyToManyField(TaxDeductionRule, blank=True,
                                                   help_text="Select which deductions apply to this user")

    # Tax brackets or special rates
    personal_relief = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,
                                          help_text="Monthly personal relief amount")

    def __str__(self):
        return f"Tax Profile - {self.user.get_full_name()}"


class PayrollPeriod(models.Model):
    """ Represents a single payroll run, e.g., "July 2025 Payroll". """

    class Status(models.TextChoices):
        DRAFT = 'Draft', 'Draft'
        PENDING_APPROVAL = 'Pending Approval', 'Pending Approval'
        APPROVED = 'Approved', 'Approved'
        PAID = 'Paid', 'Paid'

    name = models.CharField(max_length=255, help_text="e.g., 'July 2025 Payroll'")
    start_date = models.DateField()
    end_date = models.DateField()
    pay_date = models.DateField()
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='approved_payrolls')
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='processed_payrolls')
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    def can_be_approved(self):
        """Check if payroll can be approved"""
        return self.status == self.Status.DRAFT and self.entries.exists()

    def can_be_paid(self):
        """Check if payroll can be marked as paid"""
        return self.status == self.Status.APPROVED

    def approve(self, approved_by_user):
        """Approve the payroll and generate payslips"""
        if not self.can_be_approved():
            raise ValidationError("Payroll cannot be approved in its current state")

        self.status = self.Status.APPROVED
        self.approved_by = approved_by_user
        self.approved_at = timezone.now()
        self.save()

        # Generate payslips for all entries
        for entry in self.entries.all():
            entry.generate_payslip()

    def mark_as_paid(self, paid_by_user):
        """Mark payroll as paid"""
        if not self.can_be_paid():
            raise ValidationError("Payroll cannot be marked as paid in its current state")

        self.status = self.Status.PAID
        self.paid_by = paid_by_user
        self.paid_at = timezone.now()
        self.save()

    class Meta:
        ordering = ['-start_date']


class PayrollEntry(models.Model):
    """ Represents the payslip for a single User within a PayrollPeriod. """
    period = models.ForeignKey(PayrollPeriod, related_name='entries', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='payroll_entries', on_delete=models.PROTECT)

    # Financial fields are calculated and stored for historical accuracy
    base_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_allowances = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_statutory_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    gross_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def calculate_statutory_deductions(self):
        """Calculate PAYE, NHIF, NSSF etc based on user's tax profile"""
        if not hasattr(self.user, 'tax_profile'):
            return Decimal('0.00')

        total_statutory = Decimal('0.00')

        for rule in self.user.tax_profile.applicable_deductions.filter(is_active=True):
            if rule.percentage_rate:
                if rule.calculation_base == TaxDeductionRule.CalculationBase.BASIC_SALARY:
                    base_amount = self.base_pay
                elif rule.calculation_base == TaxDeductionRule.CalculationBase.GROSS_PAY:
                    base_amount = self.gross_pay
                else:
                    base_amount = Decimal('0.00')

                deduction_amount = (base_amount * rule.percentage_rate) / 100
            else:
                deduction_amount = rule.fixed_amount or Decimal('0.00')

            total_statutory += deduction_amount

            # Store individual statutory deduction for transparency
            StatutoryDeduction.objects.update_or_create(
                payroll_entry=self,
                rule=rule,
                defaults={'calculated_amount': deduction_amount}
            )

        return total_statutory

    def calculate_financials(self, commit=True):
        """Orchestrates all calculations for this payslip."""
        # 1. Get all one-time allowances/deductions for this specific payslip
        one_time_allowances = Decimal(str(self.adjustments.filter(type='ALLOWANCE').aggregate(total=Sum('amount'))['total'] or '0.00'))
        one_time_deductions = Decimal(str(self.adjustments.filter(type='DEDUCTION').aggregate(total=Sum('amount'))['total'] or '0.00'))

        # 2. Get all recurring allowances/deductions for the user
        recurring_allowances = Decimal(str(self.user.recurring_adjustments.filter(type='ALLOWANCE').aggregate(total=Sum('amount'))['total'] or '0.00'))
        recurring_deductions = Decimal(str(self.user.recurring_adjustments.filter(type='DEDUCTION').aggregate(total=Sum('amount'))['total'] or '0.00'))

        self.base_pay = Decimal(str(self.user.basic_salary or '0.00'))
        self.total_allowances = one_time_allowances + recurring_allowances
        self.gross_pay = self.base_pay + self.total_allowances

        # Calculate statutory deductions (PAYE, NHIF, etc.)
        self.total_statutory_deductions = self.calculate_statutory_deductions()

        self.total_deductions = one_time_deductions + recurring_deductions + self.total_statutory_deductions
        self.net_pay = self.gross_pay - self.total_deductions

        if commit:
            self.save()

    def generate_payslip(self):
        """Generate a payslip document when payroll is approved"""
        payslip, created = Payslip.objects.get_or_create(
            payroll_entry=self,
            defaults={
                'payslip_number': self.generate_payslip_number(),
                'generated_at': timezone.now()
            }
        )
        return payslip

    def generate_payslip_number(self):
        """
        Generate a guaranteed-unique payslip number.
        Format: PS-YYYYMM-XXXXXX
        """
        base = f"PS-{self.period.start_date.strftime('%Y%m')}"
        unique_suffix = str(uuid.uuid4()).upper()[:6]  # 6-char uppercase UUID
        return f"{base}-{unique_suffix}"

    def __str__(self):
        return f"Payslip for {self.user.get_full_name()} - {self.period.name}"


class StatutoryDeduction(models.Model):
    """Track individual statutory deductions for transparency"""
    payroll_entry = models.ForeignKey(PayrollEntry, on_delete=models.CASCADE,
                                      related_name='statutory_deductions')
    rule = models.ForeignKey(TaxDeductionRule, on_delete=models.CASCADE)
    calculated_amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ['payroll_entry', 'rule']

    def __str__(self):
        return f"{self.rule.name}: {self.calculated_amount} for {self.payroll_entry}"


class PayrollAdjustment(models.Model):
    """
    A flexible model for any financial adjustment. Can be a one-time bonus
    for a specific payslip, or a recurring loan payment for a user.
    """

    class AdjustmentType(models.TextChoices):
        ALLOWANCE = 'ALLOWANCE', 'Allowance'
        DEDUCTION = 'DEDUCTION', 'Deduction'

    type = models.CharField(max_length=10, choices=AdjustmentType.choices)
    name = models.CharField(max_length=100, help_text="e.g., 'SHA Contribution', 'Loan Repayment', 'Travel Bonus'")
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Track when adjustment was made (useful for mid-month adjustments)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='created_adjustments')

    # For one-time adjustments linked to a specific payslip
    payroll_entry = models.ForeignKey(PayrollEntry, on_delete=models.CASCADE, related_name='adjustments', null=True,
                                      blank=True)

    # For recurring adjustments linked to a user profile
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_adjustments', null=True,
                             blank=True)

    def __str__(self):
        target = self.payroll_entry or self.user
        return f"{self.get_type_display()}: {self.name} for {target}"

    def clean(self):
        if hasattr(self, '_state') and self._state.adding:
            return

        if self.payroll_entry and self.user:
            raise ValidationError("An adjustment cannot be linked to both a specific payslip and a user profile.")
        if not self.payroll_entry and not self.user:
            raise ValidationError("An adjustment must be linked to either a payslip or a user.")

    def save(self, *args, **kwargs):
        if self.payroll_entry and self.user:
            raise ValidationError("An adjustment cannot be linked to both a specific payslip and a user profile.")
        if not self.payroll_entry and not self.user:
            raise ValidationError("An adjustment must be linked to either a payslip or a user.")
        super().save(*args, **kwargs)


class Payslip(models.Model):
    """Generated payslip document"""
    payroll_entry = models.OneToOneField(PayrollEntry, on_delete=models.CASCADE, related_name='payslip')
    payslip_number = models.CharField(max_length=50, unique=True)
    generated_at = models.DateTimeField()

    # Optional: Store PDF file path if you generate PDF payslips
    pdf_file = models.FileField(upload_to='payslips/', null=True, blank=True)

    def __str__(self):
        return f"Payslip {self.payslip_number} - {self.payroll_entry.user.get_full_name()}"

    class Meta:
        ordering = ['-generated_at']