import json
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction as db_transaction
from django.utils import timezone
from .models import Supplier, PurchaseOrder, POLineItem, GoodsReceipt, GoodsReceiptItem, PurchaseOrderTrail
from catalogue.models import Product, Batch
from core.models import log_audit
from django.db.models import Q, Count, Sum


@login_required
def po_list(request):
    pos = PurchaseOrder.objects.all().select_related('supplier', 'created_by')
    status = request.GET.get('status', '')
    if status:
        pos = pos.filter(status=status)

    # Summary stats for dashboard cards
    all_pos = PurchaseOrder.objects.all()
    stats = {
        'total': all_pos.count(),
        'draft': all_pos.filter(status='draft').count(),
        'pending': all_pos.filter(status='pending_approval').count(),
        'approved': all_pos.filter(status='approved').count(),
        'partial': all_pos.filter(status='partially_received').count(),
        'received': all_pos.filter(status='fully_received').count(),
    }

    return render(request, 'procurement/po_list.html', {
        'pos': pos,
        'active_status': status,
        'stats': stats,
    })


@login_required
def po_detail(request, pk):
    po = get_object_or_404(
        PurchaseOrder.objects.select_related('supplier', 'created_by', 'approved_by'),
        pk=pk,
    )
    line_items = po.line_items.select_related('product').all()
    trail = po.trail.all()

    # Calculate totals
    total_items = line_items.count()
    total_qty = sum(li.ordered_qty for li in line_items)
    received_count = sum(1 for li in line_items if li.line_status == 'received')

    return render(request, 'procurement/po_detail.html', {
        'po': po,
        'line_items': line_items,
        'trail': trail,
        'total_items': total_items,
        'total_qty': total_qty,
        'received_count': received_count,
    })


@login_required
@require_http_methods(["GET", "POST"])
def po_create(request):
    if request.method == 'POST':
        supplier_id = request.POST.get('supplier_id')
        supplier = get_object_or_404(Supplier, id=supplier_id)
        notes = request.POST.get('notes', '')

        po = PurchaseOrder(
            supplier=supplier,
            created_by=request.user,
            status='draft',
            notes=notes,
        )
        po.save()

        PurchaseOrderTrail.objects.create(
            po=po, user=request.user, action='PO Created',
        )

        log_audit(
            action='po_created',
            user=request.user,
            entity_type='PurchaseOrder',
            entity_id=str(po.pk),
            description=f'{po.po_number} created for {supplier.name}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )

        return redirect('procurement:po_detail', pk=po.pk)

    suppliers = Supplier.objects.all().order_by('name')
    return render(request, 'procurement/po_create.html', {'suppliers': suppliers})


@login_required
@require_http_methods(["POST"])
def po_add_item(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status not in ('draft', 'pending_approval'):
        return HttpResponse('Cannot modify this PO', status=400)

    product_id = request.POST.get('product_id')
    product = get_object_or_404(Product, pk=product_id)
    qty = Decimal(request.POST.get('qty', '1'))
    unit_cost = request.POST.get('unit_cost', '')
    if unit_cost:
        unit_cost = Decimal(unit_cost)
    else:
        unit_cost = product.cost_price or Decimal('0')

    # Check for duplicate
    existing = po.line_items.filter(product=product).first()
    if existing:
        existing.ordered_qty += qty
        existing.unit_cost = unit_cost
        existing.save()
    else:
        POLineItem.objects.create(
            po=po,
            product=product,
            ordered_qty=qty,
            unit_cost=unit_cost,
        )

    if request.headers.get('HX-Request'):
        # Return the updated line items table
        line_items = po.line_items.select_related('product').all()
        return render(request, 'procurement/partials/po_line_items.html', {
            'po': po,
            'line_items': line_items,
        })

    return redirect('procurement:po_detail', pk=po.pk)


@login_required
@require_http_methods(["POST"])
def po_remove_item(request, pk, item_pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status not in ('draft', 'pending_approval'):
        return HttpResponse('Cannot modify this PO', status=400)
    line = get_object_or_404(POLineItem, pk=item_pk, po=po)
    line.delete()

    if request.headers.get('HX-Request'):
        line_items = po.line_items.select_related('product').all()
        return render(request, 'procurement/partials/po_line_items.html', {
            'po': po,
            'line_items': line_items,
        })

    return redirect('procurement:po_detail', pk=po.pk)


@login_required
@require_http_methods(["POST"])
def po_update_item(request, pk, item_pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status not in ('draft', 'pending_approval'):
        return HttpResponse('Cannot modify this PO', status=400)
    line = get_object_or_404(POLineItem, pk=item_pk, po=po)
    qty = request.POST.get('qty')
    unit_cost = request.POST.get('unit_cost')
    if qty:
        line.ordered_qty = Decimal(qty)
    if unit_cost:
        line.unit_cost = Decimal(unit_cost)
    line.save()

    if request.headers.get('HX-Request'):
        line_items = po.line_items.select_related('product').all()
        return render(request, 'procurement/partials/po_line_items.html', {
            'po': po,
            'line_items': line_items,
        })
    return redirect('procurement:po_detail', pk=po.pk)


from django.contrib import messages

@login_required
@require_http_methods(["POST"])
def po_submit(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status == 'draft':
        if po.line_items.exists():
            po.status = 'pending_approval'
            po.save()
            PurchaseOrderTrail.objects.create(
                po=po, user=request.user, action='Submitted for Approval',
            )
            messages.success(request, f"PO {po.po_number} submitted for approval.")
        else:
            messages.error(request, "Cannot submit an empty Purchase Order. Please add items first.")
    return redirect('procurement:po_detail', pk=po.pk)


@login_required
@require_http_methods(["POST"])
def po_approve(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Only Admin can approve POs', status=403)
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status == 'pending_approval':
        # Check for below-margin warning acknowledgement
        reason = request.POST.get('margin_override_reason', '')

        po.status = 'approved'
        po.approved_by = request.user
        po.approved_at = timezone.now()
        po.save()

        notes = 'Order Approved'
        if reason:
            notes += f' — Margin override: {reason}'

        PurchaseOrderTrail.objects.create(
            po=po, user=request.user, action=notes,
        )
        messages.success(request, f"PO {po.po_number} has been approved.")
        log_audit(
            action='po_approved',
            user=request.user,
            entity_type='PurchaseOrder',
            entity_id=str(po.pk),
            description=f'{po.po_number} approved',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
    return redirect('procurement:po_detail', pk=po.pk)


@login_required
@db_transaction.atomic
@require_http_methods(["POST"])
def po_receive_goods(request, pk):
    """Receive goods against a PO — supports partial receipt."""
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)

    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status not in ('approved', 'sent', 'partially_received'):
        return HttpResponse('PO must be approved before receiving', status=400)

    data = json.loads(request.body) if request.content_type == 'application/json' else None

    if data:
        received_lines = data.get('lines', [])
    else:
        received_lines = []
        for key, val in request.POST.items():
            if key.startswith('received_qty_'):
                line_id = key.replace('received_qty_', '')
                received_lines.append({
                    'line_id': line_id,
                    'received_qty': val,
                    'batch_number': request.POST.get(f'batch_number_{line_id}', ''),
                    'expiry_date': request.POST.get(f'expiry_date_{line_id}', ''),
                })

    receipt = GoodsReceipt.objects.create(
        po=po,
        received_by=request.user,
        notes=request.POST.get('notes', ''),
    )

    any_received = False
    for line_data in received_lines:
        line_id = line_data.get('line_id')
        rcvd_qty = Decimal(str(line_data.get('received_qty', 0)))
        batch_num = line_data.get('batch_number', '')
        exp_date = line_data.get('expiry_date') or None

        if rcvd_qty <= 0:
            continue

        po_line = get_object_or_404(POLineItem, pk=line_id, po=po)

        # Create receipt item
        GoodsReceiptItem.objects.create(
            receipt=receipt,
            po_line=po_line,
            received_qty=rcvd_qty,
            batch_number=batch_num,
            expiry_date=exp_date,
        )

        # Update PO line received qty
        po_line.received_qty += rcvd_qty
        if po_line.received_qty >= po_line.ordered_qty:
            po_line.line_status = 'received'
        else:
            po_line.line_status = 'partial'
        po_line.save()

        # Update product stock
        product = po_line.product
        base_qty_added = int(rcvd_qty * Decimal(product.units_per_purchase))

        if product.weight_sell_enabled:
            product.stock_in_weight_unit += rcvd_qty * Decimal(product.units_per_purchase)
            product.save(update_fields=['stock_in_weight_unit'])
        elif product.is_kadogo:
            product.whole_unit_stock += int(base_qty_added)
            product.save(update_fields=['whole_unit_stock'])
        else:
            product.stock_qty += Decimal(str(base_qty_added))
            product.save(update_fields=['stock_qty'])

        # Write to StockLedger
        from catalogue.models import StockLedger
        StockLedger.objects.create(
            product=product,
            entry_type='GRN',
            pool='WHOLE' if product.is_kadogo else 'WHOLE', # Both map to whole conceptually
            qty_delta=base_qty_added,
            purchase_unit_qty=int(rcvd_qty),
            purchase_unit_label_snapshot=product.purchase_unit_label,
            reference_id=f"GRN-{receipt.id}",
            created_by=request.user
        )

        # Update cost price (derive base unit cost from purchase unit cost)
        if product.units_per_purchase > 0:
            product.cost_price = po_line.unit_cost / Decimal(str(product.units_per_purchase))
        else:
            product.cost_price = po_line.unit_cost
        product.save(update_fields=['cost_price'])

        # Create batch record
        if batch_num:
            Batch.objects.create(
                product=product,
                batch_number=batch_num,
                expiry_date=exp_date,
                quantity=rcvd_qty,
            )

        any_received = True

    if any_received:
        if po.is_fully_received:
            po.status = 'fully_received'
        else:
            po.status = 'partially_received'
        po.save()

        PurchaseOrderTrail.objects.create(
            po=po, user=request.user,
            action=f'Goods Received ({po.get_status_display()})',
        )
        log_audit(
            action='goods_received',
            user=request.user,
            entity_type='PurchaseOrder',
            entity_id=str(po.pk),
            description=f'Goods received for {po.po_number}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )

    return redirect('procurement:po_detail', pk=po.pk)


@login_required
def po_cancel(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status in ('draft', 'pending_approval', 'approved'):
        po.status = 'cancelled'
        po.save()
        PurchaseOrderTrail.objects.create(
            po=po, user=request.user, action='PO Cancelled',
        )
    return redirect('procurement:po_detail', pk=po.pk)


# ── Product search for PO builder ──

@login_required
def product_search(request):
    """HTMX search — returns HTML partial."""
    query = request.GET.get('q', '').strip()
    if len(query) < 1:
        return HttpResponse('')

    qs = Product.objects.filter(is_active=True)
    terms = query.split()
    for term in terms:
        qs = qs.filter(
            Q(name__icontains=term) | Q(sku__icontains=term) | Q(barcode__icontains=term)
        )

    products = qs.select_related('subcategory', 'subcategory__category')[:10]

    return render(request, 'procurement/partials/product_search_results.html', {
        'products': products,
    })


@login_required
def product_search_json(request):
    """JSON search endpoint for Alpine.js PO builder."""
    query = request.GET.get('q', '').strip()
    if len(query) < 1:
        return JsonResponse([], safe=False)

    qs = Product.objects.filter(is_active=True)
    terms = query.split()
    for term in terms:
        qs = qs.filter(
            Q(name__icontains=term) | Q(sku__icontains=term) | Q(barcode__icontains=term)
        )

    products = qs.select_related('subcategory', 'subcategory__category')[:10]

    results = []
    for p in products:
        cat_name = ''
        subcat_name = ''
        try:
            if p.subcategory:
                subcat_name = p.subcategory.name
                if p.subcategory.category:
                    cat_name = p.subcategory.category.name
        except Exception:
            pass

        results.append({
            'id': str(p.pk),
            'name': p.name,
            'sku': p.sku or '',
            'cost_price': str(p.cost_price or 0),
            'sell_price': str(p.base_unit_price or 0),
            'stock_qty': str(p.effective_stock),
            'category': cat_name,
            'subcategory': subcat_name,
            'image': p.image or '📦',
            'purchase_unit_label': p.purchase_unit_label,
            'base_unit_label': p.base_unit_label,
            'units_per_purchase': p.units_per_purchase,
            'bundle_pricing_enabled': p.bundle_pricing_enabled,
        })

    return JsonResponse(results, safe=False)


# ── Suppliers ──

@login_required
def supplier_list(request):
    suppliers = Supplier.objects.all().order_by('name')
    # Count POs per supplier
    supplier_data = []
    for s in suppliers:
        po_count = s.purchase_orders.count()
        active_pos = s.purchase_orders.filter(
            status__in=['draft', 'pending_approval', 'approved', 'partially_received']
        ).count()
        supplier_data.append({
            'supplier': s,
            'po_count': po_count,
            'active_pos': active_pos,
        })
    return render(request, 'procurement/supplier_list.html', {
        'suppliers': suppliers,
        'supplier_data': supplier_data,
    })


@login_required
@require_http_methods(["POST"])
def supplier_create(request):
    name = request.POST.get('name', '').strip()
    if not name:
        return HttpResponse('Name required', status=400)

    Supplier.objects.create(
        name=name,
        contact_person=request.POST.get('contact_person', ''),
        phone=request.POST.get('phone', ''),
        email=request.POST.get('email', ''),
        address=request.POST.get('address', ''),
        payment_terms=request.POST.get('payment_terms', ''),
        kra_pin=request.POST.get('kra_pin', ''),
        notes=request.POST.get('notes', ''),
    )
    return redirect('procurement:supplier_list')


@login_required
@require_http_methods(["POST"])
def supplier_edit(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    supplier.name = request.POST.get('name', supplier.name)
    supplier.contact_person = request.POST.get('contact_person', supplier.contact_person)
    supplier.phone = request.POST.get('phone', supplier.phone)
    supplier.email = request.POST.get('email', supplier.email)
    supplier.address = request.POST.get('address', supplier.address)
    supplier.payment_terms = request.POST.get('payment_terms', supplier.payment_terms)
    supplier.kra_pin = request.POST.get('kra_pin', supplier.kra_pin)
    supplier.notes = request.POST.get('notes', supplier.notes)
    supplier.save()
    return redirect('procurement:supplier_list')


@login_required
@require_http_methods(["POST", "DELETE"])
def supplier_delete(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    supplier = get_object_or_404(Supplier, pk=pk)
    supplier.delete()
    return redirect('procurement:supplier_list')
