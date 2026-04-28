import random
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .models import AuditSession, AuditItem
from catalogue.models import Product, Category, SubCategory
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
    """Admin initiates a random stock audit."""
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)

    if request.method == 'POST':
        scope = request.POST.get('scope', 'all')
        sample_size = int(request.POST.get('sample_size', 10))
        category_id = request.POST.get('category_id') or None
        subcategory_id = request.POST.get('subcategory_id') or None

        # Build product queryset
        qs = Product.objects.filter(is_active=True)
        if scope == 'category' and category_id:
            qs = qs.filter(subcategory__category_id=category_id)
        elif scope == 'subcategory' and subcategory_id:
            qs = qs.filter(subcategory_id=subcategory_id)

        # Weight selection towards recently moved stock
        all_products = list(qs)
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

    categories = Category.objects.all().order_by('name')
    subcategories = SubCategory.objects.all().order_by('name')
    return render(request, 'audit_module/initiate.html', {
        'categories': categories,
        'subcategories': subcategories,
    })


@login_required
def audit_detail(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    session = get_object_or_404(AuditSession, pk=pk)
    items = session.items.select_related('product').all()
    return render(request, 'audit_module/detail.html', {
        'session': session,
        'items': items,
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

            # Apply stock adjustment if variance exists
            if item.variance != 0:
                product = item.product
                if product.weight_sell_enabled:
                    product.stock_in_weight_unit = physical_qty
                    product.save(update_fields=['stock_in_weight_unit'])
                else:
                    product.stock_qty = physical_qty
                    product.save(update_fields=['stock_qty'])

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
def audit_print(request, pk):
    """Printable audit sheet."""
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    session = get_object_or_404(AuditSession, pk=pk)
    items = session.items.select_related('product', 'product__subcategory', 'product__subcategory__category').all()
    return render(request, 'audit_module/print_sheet.html', {
        'session': session,
        'items': items,
        'store_name': 'Floki Minimart',
    })
