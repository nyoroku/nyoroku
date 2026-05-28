import random
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction
from .models import AuditSession, AuditItem
from catalogue.models import Product, Category, SubCategory, StockLedger
from core.models import log_audit


@login_required
def audit_list(request):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    sessions = AuditSession.objects.all()
    return render(request, 'audit_module/list.html', {'sessions': sessions})


@login_required
@require_http_methods(["GET", "POST"])
def audit_initiate(request):
    """Admin initiates a stock audit."""
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)

    form_errors = None
    if request.method == 'POST':
        from .forms import AuditInitiateForm
        form = AuditInitiateForm(request.POST)
        if form.is_valid():
            scope = form.cleaned_data['scope']
            sample_size = form.cleaned_data.get('sample_size')
            category_id = form.cleaned_data.get('category_id')
            subcategory_id = form.cleaned_data.get('subcategory_id')

            # Build product queryset
            qs = Product.objects.filter(is_active=True)
            if scope == 'category' and category_id:
                qs = qs.filter(subcategory__category_id=category_id)
            elif scope == 'subcategory' and subcategory_id:
                qs = qs.filter(subcategory_id=subcategory_id)

            all_products = list(qs)
            
            if scope == 'all':
                selected = all_products
                sample_size = len(selected)
            else:
                if len(all_products) <= sample_size:
                    selected = all_products
                else:
                    # Weighted random: recently updated products get higher weight
                    weights = []
                    for p in all_products:
                        days_since = (timezone.now() - p.updated_at).days
                        weight = max(1, 30 - days_since)
                        weights.append(weight)
                    selected = random.choices(all_products, weights=weights, k=min(sample_size, len(all_products)))
                    # Deduplicate
                    seen = set()
                    unique = []
                    for p in selected:
                        if p.pk not in seen:
                            seen.add(p.pk)
                            unique.append(p)
                    selected = unique

            session = AuditSession.objects.create(
                initiated_by=request.user,
                scope=scope,
                scope_category_id=category_id,
                scope_subcategory_id=subcategory_id,
                sample_size=len(selected),
            )

            for product in selected:
                system_qty = product.stock_in_weight_unit if product.weight_sell_enabled else product.stock_qty
                AuditItem.objects.create(
                    session=session,
                    product=product,
                    system_qty=system_qty,
                )

            return redirect('audit_module:detail', pk=session.pk)
        else:
            form_errors = form.errors

    categories = Category.objects.all().order_by('name')
    subcategories = SubCategory.objects.all().order_by('name')
    return render(request, 'audit_module/initiate.html', {
        'categories': categories,
        'subcategories': subcategories,
        'form_errors': form_errors,
    })


@login_required
def audit_detail(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    session = get_object_or_404(AuditSession, pk=pk)
    items = session.items.select_related('product', 'product__subcategory', 'product__subcategory__category').all()
    
    from accounts.models import User
    staff_users = User.objects.filter(is_active=True).order_by('name')
    
    return render(request, 'audit_module/detail.html', {
        'session': session,
        'items': items,
        'staff_users': staff_users,
    })


@login_required
@require_http_methods(["POST"])
def audit_submit(request, pk):
    """Submit physical counts and compute variances."""
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)

    session = get_object_or_404(AuditSession, pk=pk)

    for item in session.items.all():
        physical_str = request.POST.get(f'physical_{item.pk}', '')
        note = request.POST.get(f'note_{item.pk}', '')

        if physical_str:
            physical_qty = Decimal(physical_str)
            item.physical_qty = physical_qty
            item.variance = physical_qty - item.system_qty
            item.note = note
            item.save()

    session.status = 'completed'
    session.completed_at = timezone.now()
    session.notes = request.POST.get('session_notes', '')
    session.save()

    log_audit(
        action='audit_completed',
        user=request.user,
        entity_type='AuditSession',
        entity_id=str(session.pk),
        description=f'Audit completed: {session.total_items} items, {session.variance_count} variances',
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return redirect('audit_module:detail', pk=session.pk)


@login_required
@require_http_methods(["POST"])
def audit_item_apply(request, item_id):
    """Apply a single item's physical count to the database stock.
    
    Updates product stock and creates a StockLedger ADJUSTMENT entry.
    Sets AuditItem.action_status to 'applied'.
    """
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)

    item = get_object_or_404(AuditItem, pk=item_id)
    if item.session.status != 'completed':
        return HttpResponse('Audit session is not completed', status=400)
    if item.variance is None or item.variance == 0:
        return HttpResponse('No variance to apply', status=400)
    if item.action_status == 'applied':
        return HttpResponse('Already applied', status=400)

    product = item.product

    with transaction.atomic():
        # Update product stock
        if product.weight_sell_enabled:
            product.stock_in_weight_unit = item.physical_qty
            product.save(update_fields=['stock_in_weight_unit'])
        else:
            product.stock_qty = item.physical_qty
            product.save(update_fields=['stock_qty'])

        # Create StockLedger entry
        StockLedger.objects.create(
            product=product,
            entry_type='ADJUSTMENT',
            qty_delta=int(item.variance),
            reference_id=str(item.session.pk),
            created_by=request.user,
        )

        # Mark as applied
        item.action_status = 'applied'
        item.save(update_fields=['action_status'])

    log_audit(
        action='audit_stock_applied',
        user=request.user,
        entity_type='AuditItem',
        entity_id=str(item.pk),
        description=f"Applied stock adjustment for {product.name}: {item.system_qty} → {item.physical_qty} (variance: {item.variance})",
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    messages.success(request, f"Stock adjusted successfully for {product.name}.")
    return redirect('audit_module:detail', pk=item.session.pk)


@login_required
@require_http_methods(["POST"])
def audit_apply_all(request, pk):
    """Bulk apply selected or all unposted variance items in one atomic transaction."""
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)

    session = get_object_or_404(AuditSession, pk=pk)
    if session.status != 'completed':
        return HttpResponse('Audit session is not completed', status=400)

    # Support selection
    selected_ids = request.POST.getlist('selected_items')
    
    items = session.items.exclude(variance=Decimal('0')).exclude(variance__isnull=True).exclude(action_status='applied')
    if selected_ids:
        items = items.filter(pk__in=selected_ids)
        
    applied_count = 0

    with transaction.atomic():
        for item in items:
            product = item.product

            # Update product stock
            if product.weight_sell_enabled:
                product.stock_in_weight_unit = item.physical_qty
                product.save(update_fields=['stock_in_weight_unit'])
            else:
                product.stock_qty = item.physical_qty
                product.save(update_fields=['stock_qty'])

            # Create StockLedger entry
            StockLedger.objects.create(
                product=product,
                entry_type='ADJUSTMENT',
                qty_delta=int(item.variance),
                reference_id=str(session.pk),
                created_by=request.user,
            )

            # Mark as applied
            item.action_status = 'applied'
            item.save(update_fields=['action_status'])
            applied_count += 1

    log_audit(
        action='audit_stock_applied_bulk',
        user=request.user,
        entity_type='AuditSession',
        entity_id=str(session.pk),
        description=f"Bulk applied stock adjustments for {applied_count} items.",
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    if applied_count > 0:
        messages.success(request, f"Successfully adjusted stock for {applied_count} products.")
    else:
        messages.warning(request, "No stock adjustments were made.")

    return redirect('audit_module:detail', pk=session.pk)


@login_required
def audit_print(request, pk):
    """Printable audit sheet."""
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    session = get_object_or_404(AuditSession, pk=pk)
    items = session.items.select_related('product', 'product__subcategory', 'product__subcategory__category').all()
    return render(request, 'audit_module/print_sheet.html', {
        'session': session,
        'items': items,
        'store_name': getattr(settings, 'STORE_NAME', "Jimmy's Mini Mart"),
    })


@login_required
@require_http_methods(["POST"])
def audit_item_validate(request, item_id):
    """Admin validates a completed stock audit item variance and posts to payroll."""
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)

    item = get_object_or_404(AuditItem, pk=item_id)
    if item.session.status != 'completed':
        return HttpResponse('Audit session is not completed', status=400)

    staff_id = request.POST.get('staff_id')
    if not staff_id:
        return HttpResponse('Staff member is required', status=400)

    from accounts.models import User
    staff = get_object_or_404(User, pk=staff_id)

    # Find active draft payroll period
    from payroll.models import PayrollPeriod, PayrollEntry, PayrollAdjustment
    period = PayrollPeriod.objects.filter(status='Draft').first()
    if not period:
        return HttpResponse('Error: No active draft payroll period found. Please create a draft payroll period first.', status=400)

    # Get or create payroll entry
    entry, created = PayrollEntry.objects.get_or_create(
        period=period,
        user=staff,
        defaults={'base_pay': staff.basic_salary}
    )

    # Calculate cash surplus from cashier's last confirmed handover
    from pos.models import CashHandover
    last_handover = CashHandover.objects.filter(staff=staff, status='confirmed').order_by('-confirmed_at').first()
    cash_surplus = Decimal('0.00')
    if last_handover and last_handover.variance > 0:
        cash_surplus = last_handover.variance

    variance_val = item.variance_value
    adjustment = None

    if variance_val < 0:
        # Shortage
        shortage = -variance_val
        net_deduction = max(Decimal('0.00'), shortage - cash_surplus)
        
        if net_deduction > 0:
            adjustment = PayrollAdjustment.objects.create(
                type='DEDUCTION',
                name=f"Stock Audit Shortage - {item.product.name}",
                amount=net_deduction,
                created_by=request.user,
                payroll_entry=entry,
            )
            entry.calculate_financials()
    elif variance_val > 0:
        # Surplus / Allowance
        net_allowance = variance_val
        adjustment = PayrollAdjustment.objects.create(
            type='ALLOWANCE',
            name=f"Stock Audit Surplus - {item.product.name}",
            amount=net_allowance,
            created_by=request.user,
            payroll_entry=entry,
        )
        entry.calculate_financials()

    # Update AuditItem status
    item.action_status = 'posted'
    item.payroll_adjustment = adjustment
    item.validated_by = request.user
    item.validated_at = timezone.now()
    item.save()

    log_audit(
        action='audit_item_validated',
        user=request.user,
        entity_type='AuditItem',
        entity_id=str(item.pk),
        description=f"Validated variance for {item.product.name}: posted to payroll for {staff.name}.",
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return redirect('audit_module:detail', pk=item.session.pk)


@login_required
@require_http_methods(["POST"])
def audit_item_dispute(request, item_id):
    """Admin marks a completed stock audit item variance as disputed."""
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)

    item = get_object_or_404(AuditItem, pk=item_id)
    if item.session.status != 'completed':
        return HttpResponse('Audit session is not completed', status=400)

    item.action_status = 'disputed'
    item.save()

    log_audit(
        action='audit_item_disputed',
        user=request.user,
        entity_type='AuditItem',
        entity_id=str(item.pk),
        description=f"Disputed variance for {item.product.name}.",
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return redirect('audit_module:detail', pk=item.session.pk)


@login_required
def staff_surplus(request):
    """HTMX endpoint to calculate cash surplus offset for a selected staff member."""
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)

    staff_id = request.GET.get('staff_id')
    item_id = request.GET.get('item_id')

    if not staff_id or not item_id:
        return HttpResponse('<p class="text-xs text-red-600">Select a staff member</p>')

    from accounts.models import User
    staff = get_object_or_404(User, pk=staff_id)
    item = get_object_or_404(AuditItem, pk=item_id)

    # Cash Surplus calculation
    from pos.models import CashHandover
    last_handover = CashHandover.objects.filter(staff=staff, status='confirmed').order_by('-confirmed_at').first()
    cash_surplus = Decimal('0.00')
    if last_handover and last_handover.variance > 0:
        cash_surplus = last_handover.variance

    variance_val = item.variance_value
    is_shortage = variance_val < 0
    shortage = -variance_val if is_shortage else Decimal('0.00')
    net_amount = Decimal('0.00')

    if is_shortage:
        net_amount = max(Decimal('0.00'), shortage - cash_surplus)
    else:
        net_amount = variance_val

    html = f"""
    <div class="p-4 rounded-xl space-y-2 text-xs border" style="background: var(--bg-main); border-color: var(--border);">
        <div class="flex justify-between items-center">
            <span class="text-text-secondary font-medium">Original Variance:</span>
            <span class="font-mono font-bold text-red-600 if is_shortage else text-emerald-600">
                KES {abs(variance_val):.2f} ({'Shortage' if is_shortage else 'Surplus'})
            </span>
        </div>
        
        <div class="flex justify-between items-center border-t border-dashed pt-2 mt-1">
            <span class="text-text-secondary font-medium">Staff Cash Surplus Offset:</span>
            <span class="font-mono font-bold text-emerald-600">
                KES {cash_surplus:.2f}
            </span>
        </div>
        
        <div class="flex justify-between items-center border-t pt-2 mt-2 border-slate-200">
            <span class="font-bold text-sm" style="color: var(--primary-dark)">Net Posting Amount:</span>
            <span class="font-mono font-extrabold text-sm text-red-600 if is_shortage else text-emerald-600">
                KES {net_amount:.2f}
            </span>
        </div>
        
        <div class="text-[10px] text-text-secondary italic mt-1">
            {"* Cash surplus offsets applied successfully." if is_shortage and cash_surplus > 0 else ""}
            {"* No surplus offset available for this cashier." if is_shortage and cash_surplus == 0 else ""}
        </div>
    </div>
    """
    # Fix the class formatting with dynamic classes in python string formatting:
    text_color_class = 'text-red-600' if is_shortage else 'text-emerald-600'
    html = f"""
    <div class="p-4 rounded-xl space-y-2 text-xs border" style="background: var(--bg-main); border-color: var(--border);">
        <div class="flex justify-between items-center">
            <span class="text-text-secondary font-medium">Original Variance:</span>
            <span class="font-mono font-bold {text_color_class}">
                KES {abs(variance_val):.2f} ({'Shortage' if is_shortage else 'Surplus'})
            </span>
        </div>
        
        <div class="flex justify-between items-center border-t border-dashed pt-2 mt-1" style="border-color: var(--border)">
            <span class="text-text-secondary font-medium">Staff Cash Surplus Offset:</span>
            <span class="font-mono font-bold text-emerald-600">
                KES {cash_surplus:.2f}
            </span>
        </div>
        
        <div class="flex justify-between items-center border-t pt-2 mt-2" style="border-color: var(--border)">
            <span class="font-bold text-sm" style="color: var(--primary-dark)">Net Posting Amount:</span>
            <span class="font-mono font-extrabold text-sm {text_color_class}">
                KES {net_amount:.2f}
            </span>
        </div>
        
        <div class="text-[10px] text-text-secondary italic mt-1">
            {"* Cash surplus offsets applied successfully." if is_shortage and cash_surplus > 0 else ""}
            {"* No surplus offset available for this cashier." if is_shortage and cash_surplus == 0 else ""}
        </div>
    </div>
    """
    return HttpResponse(html)
