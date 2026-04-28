# payroll/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.core.exceptions import ValidationError
from django.utils import timezone
# from pos.models import WaiterRewardSettings  # Removed - not supported in Floki
from decimal import Decimal
from .models import (PayrollPeriod, PayrollEntry, PayrollAdjustment, User,
                     TaxDeductionRule, UserTaxProfile, Payslip)
from .forms import PayrollPeriodForm, PayrollAdjustmentForm, UserTaxProfileForm


# @admin_manager_required
@login_required
def payroll_period_list_view(request):
    """Displays a list of all payroll runs."""
    periods = PayrollPeriod.objects.all()
    return render(request, 'payroll/period_list.html', {'periods': periods})


# @admin_manager_required
@login_required
def run_new_payroll_view(request):
    """Handles the creation of a new payroll period and its initial entries."""
    if request.method == 'POST':
        form = PayrollPeriodForm(request.POST)
        if form.is_valid():
            active_users = User.objects.filter(is_active=True)
            if not active_users.exists():
                messages.warning(request, "No active employees were found.")
                return render(request, 'payroll/run_new_payroll.html', {'form': form})

            with transaction.atomic():
                period = form.save()
                entries_created = 0
                for user in active_users:
                    entry = PayrollEntry.objects.create(period=period, user=user)
                    entry.calculate_financials()
                    entries_created += 1

                messages.success(request,
                                 f"Payroll '{period.name}' created with {entries_created} entries. "
                                 f"Status: {period.get_status_display()}")
                return redirect('payroll:period_detail', period_id=period.id)
    else:
        form = PayrollPeriodForm()
    return render(request, 'payroll/run_new_payroll.html', {'form': form})


# @admin_manager_required
@login_required
def payroll_period_detail_view(request, period_id):
    """The main workbench for managing a specific payroll run."""
    period = get_object_or_404(PayrollPeriod, id=period_id)
    entries = period.entries.select_related('user').prefetch_related(
        'adjustments',
        'user__recurring_adjustments',
        'statutory_deductions__rule'
    )
    adjustment_form = PayrollAdjustmentForm()

    # Calculate totals for the period
    total_gross = sum(entry.gross_pay for entry in entries)
    total_deductions = sum(entry.total_deductions for entry in entries)
    total_net = sum(entry.net_pay for entry in entries)

    return render(request, 'payroll/period_detail.html', {
        'period': period,
        'entries': entries,
        'adjustment_form': adjustment_form,
        'total_gross': total_gross,
        'total_deductions': total_deductions,
        'total_net': total_net,
    })


@login_required
def approve_payroll(request, period_id):
    """Approve a payroll period and generate payslips"""
    period = get_object_or_404(PayrollPeriod, id=period_id)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                period.approve(request.user)
                messages.success(request,
                                 f"Payroll '{period.name}' has been approved and payslips generated. "
                                 f"Status: {period.get_status_display()}")
        except ValidationError as e:
            messages.error(request, f"Cannot approve payroll: {e}")
        except Exception as e:
            messages.error(request, f"Error approving payroll: {str(e)}")

    return redirect('payroll:period_detail', period_id=period.id)


@login_required
def mark_payroll_as_paid(request, period_id):
    """Mark a payroll period as paid"""
    period = get_object_or_404(PayrollPeriod, id=period_id)

    if request.method == 'POST':
        try:
            period.mark_as_paid(request.user)
            messages.success(request,
                             f"Payroll '{period.name}' has been marked as paid. "
                             f"Status: {period.get_status_display()}")
        except ValidationError as e:
            messages.error(request, f"Cannot mark as paid: {e}")
        except Exception as e:
            messages.error(request, f"Error marking as paid: {str(e)}")

    return redirect('payroll:period_detail', period_id=period.id)


@login_required
def recalculate_payroll(request, period_id):
    """Recalculate all entries in a payroll period (only for draft status)"""
    period = get_object_or_404(PayrollPeriod, id=period_id)

    if period.status != PayrollPeriod.Status.DRAFT:
        messages.error(request, "Can only recalculate payroll in Draft status")
        return redirect('payroll:period_detail', period_id=period.id)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                for entry in period.entries.all():
                    entry.calculate_financials()
                messages.success(request, "All payroll entries recalculated successfully")
        except Exception as e:
            messages.error(request, f"Error recalculating payroll: {str(e)}")

    return redirect('payroll:period_detail', period_id=period.id)


# @admin_manager_required
@login_required
def user_payroll_profile_view(request, user_id):
    """A page to manage a single user's recurring allowances, deductions, and tax profile."""
    user = get_object_or_404(User, id=user_id)

    # Get or create tax profile
    tax_profile, created = UserTaxProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        action = request.POST.get('action', 'add_adjustment')  # Default action

        if action == 'add_adjustment':
            # Create form with POST data
            form = PayrollAdjustmentForm(request.POST)
            if form.is_valid():
                try:
                    # Create recurring adjustment (payroll_entry should be None for recurring)
                    adjustment = PayrollAdjustment.objects.create(
                        type=form.cleaned_data['type'],
                        name=form.cleaned_data['name'],
                        amount=form.cleaned_data['amount'],
                        user=user,  # This makes it recurring
                        payroll_entry=None,  # This is key - no specific entry means recurring
                        created_by=request.user
                    )

                    # Recalculate any open payroll entries for this user
                    open_entries = PayrollEntry.objects.filter(
                        user=user,
                        period__status=PayrollPeriod.Status.DRAFT
                    )

                    recalculated_count = 0
                    for open_entry in open_entries:
                        open_entry.calculate_financials()
                        recalculated_count += 1

                    success_msg = f"Recurring adjustment '{adjustment.name}' added successfully."
                    if recalculated_count > 0:
                        success_msg += f" {recalculated_count} open payroll entries recalculated."

                    messages.success(request, success_msg)
                    return redirect('payroll:user_profile', user_id=user.id)

                except ValidationError as e:
                    messages.error(request, f"Validation Error: {e}")
                except Exception as e:
                    messages.error(request, f"An error occurred: {str(e)}")
            else:
                # Handle form errors
                error_messages = []
                for field, errors in form.errors.items():
                    for error in errors:
                        error_messages.append(f"{field.title()}: {error}")

                messages.error(request, "Please correct the following errors: " + "; ".join(error_messages))

        elif action == 'update_tax_profile':
            # Handle tax profile updates
            selected_deductions = request.POST.getlist('applicable_deductions')
            personal_relief = request.POST.get('personal_relief', 0)

            try:
                tax_profile.applicable_deductions.set(selected_deductions)
                tax_profile.personal_relief = personal_relief
                tax_profile.save()

                # Recalculate any open payroll entries
                open_entries = PayrollEntry.objects.filter(
                    user=user,
                    period__status=PayrollPeriod.Status.DRAFT
                )
                for open_entry in open_entries:
                    open_entry.calculate_financials()

                messages.success(request, "Tax profile updated successfully.")
                return redirect('payroll:user_profile', user_id=user.id)
            except Exception as e:
                messages.error(request, f"Error updating tax profile: {str(e)}")

    # Create fresh form for GET requests or after successful POST
    form = PayrollAdjustmentForm()

    # Get recurring adjustments (where payroll_entry is None)
    recurring_adjustments = user.recurring_adjustments.filter(payroll_entry__isnull=True)
    tax_rules = TaxDeductionRule.objects.filter(is_active=True)

    return render(request, 'payroll/user_profile.html', {
        'profile_user': user,
        'tax_profile': tax_profile,
        'adjustments': recurring_adjustments,
        'form': form,
        'tax_rules': tax_rules,
    })


# @admin_manager_required
@login_required
def add_one_time_adjustment(request, entry_id):
    """Adds a one-time allowance/deduction to a specific payslip."""
    entry = get_object_or_404(PayrollEntry, id=entry_id)

    # Check if payroll is still in draft
    if entry.period.status != PayrollPeriod.Status.DRAFT:
        messages.error(request, "Cannot modify payroll entries after approval.")
        return redirect('payroll:period_detail', period_id=entry.period.id)

    if request.method == 'POST':
        form = PayrollAdjustmentForm(request.POST)
        if form.is_valid():
            try:
                adjustment = PayrollAdjustment.objects.create(
                    type=form.cleaned_data['type'],
                    name=form.cleaned_data['name'],
                    amount=form.cleaned_data['amount'],
                    payroll_entry=entry,  # This makes it one-time
                    user=None,  # No user for one-time adjustments
                    created_by=request.user
                )
                entry.calculate_financials()  # Recalculate totals
                messages.success(request, f"One-time adjustment '{adjustment.name}' added successfully.")
            except ValidationError as e:
                messages.error(request, f"Error: {e}")
            except Exception as e:
                messages.error(request, f"An error occurred: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

    return redirect('payroll:period_detail', period_id=entry.period.id)


# @admin_manager_required
@login_required
def remove_adjustment(request, adj_id):
    """Removes any adjustment (one-time or recurring)."""
    adjustment = get_object_or_404(PayrollAdjustment, id=adj_id)

    # Check if it's a one-time adjustment (has payroll_entry)
    if entry := adjustment.payroll_entry:
        # Check if payroll is still in draft
        if entry.period.status != PayrollPeriod.Status.DRAFT:
            messages.error(request, "Cannot modify payroll entries after approval.")
            return redirect('payroll:period_detail', period_id=entry.period.id)

        period_id = entry.period.id
        adjustment_name = adjustment.name
        adjustment.delete()
        entry.calculate_financials()  # Recalculate
        messages.success(request, f"One-time adjustment '{adjustment_name}' removed.")
        return redirect('payroll:period_detail', period_id=period_id)

    # Check if it's a recurring adjustment (has user but no payroll_entry)
    elif user := adjustment.user:
        user_id = user.id
        adjustment_name = adjustment.name
        adjustment.delete()

        # Recalculate any open payroll entries for this user
        open_entries = PayrollEntry.objects.filter(
            user=user,
            period__status=PayrollPeriod.Status.DRAFT
        )
        recalculated_count = 0
        for open_entry in open_entries:
            open_entry.calculate_financials()
            recalculated_count += 1

        success_msg = f"Recurring adjustment '{adjustment_name}' removed."
        if recalculated_count > 0:
            success_msg += f" {recalculated_count} open payroll entries recalculated."

        messages.success(request, success_msg)
        return redirect('payroll:user_profile', user_id=user_id)

    messages.error(request, "Could not determine adjustment type.")
    return redirect('payroll:period_list')


@login_required
def payslip_detail_view(request, payslip_id):
    """View individual payslip"""
    payslip = get_object_or_404(Payslip, id=payslip_id)
    entry = payslip.payroll_entry

    # Get breakdown of deductions
    statutory_deductions = entry.statutory_deductions.select_related('rule')
    one_time_adjustments = entry.adjustments.all()
    # Get recurring adjustments that were applied to this user
    recurring_adjustments = entry.user.recurring_adjustments.filter(payroll_entry__isnull=True)

    return render(request, 'payroll/payslip_detail.html', {
        'payslip': payslip,
        'entry': entry,
        'statutory_deductions': statutory_deductions,
        'one_time_adjustments': one_time_adjustments,
        'recurring_adjustments': recurring_adjustments,
    })


@login_required
def generate_payslip_pdf(request, payslip_id):
    """Generate PDF version of payslip"""
    payslip = get_object_or_404(Payslip, id=payslip_id)

    # You can implement PDF generation here using libraries like:
    # - reportlab
    # - weasyprint
    # - wkhtmltopdf

    # For now, return a simple response
    messages.info(request, "PDF generation feature coming soon!")
    return redirect('payroll:payslip_detail', payslip_id=payslip.id)


@login_required
def tax_rules_management(request):
    """Manage tax deduction rules (PAYE, NHIF, etc.)"""
    rules = TaxDeductionRule.objects.all()

    if request.method == 'POST':
        # Handle adding/updating tax rules
        # This would typically be done through Django admin or a dedicated form
        pass

    return render(request, 'payroll/tax_rules.html', {'rules': rules})


@login_required
def print_payroll_summary(request, period_id):
    """Generate a print-friendly payroll summary page"""
    period = get_object_or_404(PayrollPeriod, id=period_id)
    entries = period.entries.select_related('user').prefetch_related(
        'adjustments',
        'statutory_deductions__rule'
    ).order_by('user__last_name', 'user__first_name')

    # Calculate totals
    total_gross = sum(entry.gross_pay for entry in entries)
    total_deductions = sum(entry.total_deductions for entry in entries)
    total_net = sum(entry.net_pay for entry in entries)

    context = {
        'period': period,
        'entries': entries,
        'total_gross': total_gross,
        'total_deductions': total_deductions,
        'total_net': total_net,
        'print_date': timezone.now(),
        'printed_by': request.user,
    }

    return render(request, 'payroll/print_summary.html', context)


@login_required
def print_payroll_register(request, period_id):
    """Generate a detailed payroll register for printing"""
    period = get_object_or_404(PayrollPeriod, id=period_id)
    entries = period.entries.select_related('user').prefetch_related(
        'adjustments',
        'statutory_deductions__rule'
    ).order_by('user__last_name', 'user__first_name')

    context = {
        'period': period,
        'entries': entries,
        'print_date': timezone.now(),
        'printed_by': request.user,
    }

    return render(request, 'payroll/print_register.html', context)


@login_required
def print_payslips(request, period_id):
    """Print all payslips for the period"""
    period = get_object_or_404(PayrollPeriod, id=period_id)

    if period.status not in ['Approved', 'Paid']:
        messages.error(request, "Payslips can only be printed for approved or paid payrolls.")
        return redirect('payroll:period_detail', period_id=period.id)

    entries = period.entries.select_related('user', 'payslip').prefetch_related(
        'adjustments',
        'statutory_deductions__rule'
    ).order_by('user__last_name', 'user__first_name')

    context = {
        'period': period,
        'entries': entries,
        'print_date': timezone.now(),
    }

    return render(request, 'payroll/print_payslips.html', context)


@login_required
def export_payroll_csv(request, period_id):
    """Export payroll data to CSV for Windows Excel"""
    import csv

    period = get_object_or_404(PayrollPeriod, id=period_id)
    entries = period.entries.select_related('user').prefetch_related(
        'adjustments',
        'statutory_deductions__rule'
    ).order_by('user__last_name', 'user__first_name')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="payroll_{period.name.replace(" ", "_")}.csv"'

    writer = csv.writer(response)

    # Header row
    writer.writerow([
        'Employee ID', 'Employee Name', 'Basic Pay', 'Total Allowances',
        'Gross Pay', 'PAYE', 'NSSF', 'NHIF', 'Other Deductions',
        'Total Deductions', 'Net Pay'
    ])

    # Data rows
    for entry in entries:
        paye = entry.statutory_deductions.filter(rule__name='PAYE').first()
        nssf = entry.statutory_deductions.filter(rule__name='NSSF').first()
        nhif = entry.statutory_deductions.filter(rule__name='NHIF').first()

        writer.writerow([
            entry.user.employee_id or '',
            entry.user.get_full_name(),
            entry.base_pay,
            entry.total_allowances,
            entry.gross_pay,
            paye.amount if paye else 0,
            nssf.amount if nssf else 0,
            nhif.amount if nhif else 0,
            entry.total_deductions - entry.total_statutory_deductions,
            entry.total_deductions,
            entry.net_pay,
        ])

    return response


@login_required
def redeem_waiter_points(request, entry_id):
    """Redeem waiter reward points as a cash allowance for a specific payroll entry."""
    entry = get_object_or_404(PayrollEntry, id=entry_id)

    # Check if payroll is still in draft
    if entry.period.status != PayrollPeriod.Status.DRAFT:
        messages.error(request, "Cannot redeem points for a payroll that is not in Draft status.")
        return redirect('payroll:period_detail', period_id=entry.period.id)

    messages.error(request, "Waiter reward system is not supported in this version of Floki POS.")
    return redirect('payroll:period_detail', period_id=entry.period.id)

    if request.method == 'POST':
        try:
            points_to_redeem = int(request.POST.get('points_to_redeem', 0))
            if points_to_redeem <= 0:
                messages.error(request, "Please enter a valid number of points to redeem.")
                return redirect('payroll:period_detail', period_id=entry.period.id)

            # Check if user has enough points
            if points_to_redeem > entry.user.waiter_reward_points:
                messages.error(request, f"User only has {entry.user.waiter_reward_points} points available.")
                return redirect('payroll:period_detail', period_id=entry.period.id)

            # Get the reward settings
            reward_settings = WaiterRewardSettings.objects.first()
            if not reward_settings or not reward_settings.is_active:
                messages.error(request, "Waiter reward system is not active.")
                return redirect('payroll:period_detail', period_id=entry.period.id)

            # Calculate cash value
            cash_value = Decimal(points_to_redeem) * reward_settings.kes_per_point

            # Update the payroll entry
            entry.reward_points_redeemed = points_to_redeem
            entry.reward_points_value = cash_value
            entry.save()

            # Deduct points from user's balance
            entry.user.waiter_reward_points -= points_to_redeem
            entry.user.save(update_fields=['waiter_reward_points'])

            # Recalculate the entire entry
            entry.calculate_financials()

            messages.success(request, f"Successfully redeemed {points_to_redeem} points ({cash_value} KES) for {entry.user.get_full_name()}.")
            return redirect('payroll:period_detail', period_id=entry.period.id)

        except (ValueError, TypeError):
            messages.error(request, "Invalid number of points entered.")
        except Exception as e:
            messages.error(request, f"Error redeeming points: {str(e)}")

    return redirect('payroll:period_detail', period_id=entry.period.id)