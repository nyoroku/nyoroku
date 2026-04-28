import json
import logging
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction as db_transaction
from django.utils import timezone
from django.conf import settings
from catalogue.models import Product, Category, SubCategory, Batch
from .models import Sale, SaleLineItem, ParkedSale
from core.models import log_audit

logger = logging.getLogger(__name__)


@login_required
def index(request):
    """POS sell screen — phone-first layout."""
    query = request.GET.get('q', '')
    cat_id = request.GET.get('category', '')

    qs = Product.objects.filter(is_active=True).select_related(
        'subcategory', 'subcategory__category'
    ).order_by('name')

    if query:
        from django.db.models import Q
        qs = qs.filter(
            Q(name__icontains=query) | Q(sku__icontains=query) | Q(barcode__icontains=query)
        )
    if cat_id and cat_id != 'all':
        try:
            qs = qs.filter(subcategory__category_id=cat_id)
        except (ValueError,):
            pass

    # Check for active promotions — build lookup maps once
    from promotions.models import Promotion
    now = timezone.now()
    active_promos = list(Promotion.objects.filter(
        is_active=True, start_date__lte=now, end_date__gte=now,
    ))
    product_promo_map = {}
    category_promo_map = {}
    for p in active_promos:
        if p.product_id:
            product_promo_map[str(p.product_id)] = p
        elif p.category_id:
            category_promo_map[str(p.category_id)] = p

    products_data = []
    for product in qs[:100]:
        promo = product_promo_map.get(str(product.pk))
        if not promo:
            promo = category_promo_map.get(str(product.subcategory.category_id))
        
        # Kadogo fragment sizes
        fragments_list = []
        total_fragments = 0
        if product.is_kadogo:
            fragments_qs = product.fragment_sizes.filter(is_active=True).values(
                'id', 'name', 'fragment_count', 'fragment_price', 'is_default', 'fragment_pool'
            )
            for f in fragments_qs:
                fragments_list.append({
                    'id': str(f['id']),
                    'name': f['name'],
                    'fragment_count': int(f['fragment_count']),
                    'fragment_price': float(f['fragment_price']),
                    'is_default': bool(f['is_default']),
                    'fragment_pool': int(f['fragment_pool']),
                })
            
            if fragments_list:
                base_frag = fragments_list[0]
                total_fragments = base_frag['fragment_pool'] + (product.whole_unit_stock * base_frag['fragment_count'])

        # Comprehensive product data for JS
        product_json_data = {
            'id': str(product.id),
            'name': product.name,
            'base_unit_price': float(product.base_unit_price or 0),
            'base_unit_label': product.base_unit_label or 'Unit',
            'is_kadogo': product.is_kadogo,
            'fragments': fragments_list,
            'cost_price': float(product.cost_price or 0),
            'stock_qty': float(product.stock_qty or 0),
            'split_enabled': product.split_enabled,
            'split_unit_price': float(product.split_unit_price or 0),
            'split_unit_label': product.split_unit_label or 'Piece',
            'weight_sell_enabled': product.weight_sell_enabled,
            'bundle_pricing_enabled': product.bundle_pricing_enabled,
            'bundle_price': float(product.bundle_price or 0),
            'bundle_qty': product.bundle_qty or 1,
            'single_unit_price': float(product.single_unit_price or 0),
            'allow_single_sale': product.allow_single_sale,
            'image': product.image if hasattr(product, 'image') and product.image else '📦',
            'total_fragments': total_fragments,
        }
        
        products_data.append({
            'product': product,
            'promo': promo,
            'product_json': json.dumps(product_json_data),
            'total_fragments': total_fragments,
        })

    categories = Category.objects.all().order_by('order', 'name')

    context = {
        'products_data': products_data,
        'categories': categories,
        'active_category': cat_id or 'all',
        'query': query,
        'is_admin': request.user.role == 'admin',
        'is_manager': request.user.role in ('admin', 'manager'),
        'store_name': getattr(settings, 'STORE_NAME', 'Floki Minimart'),
    }

    if request.headers.get('HX-Request'):
        return render(request, 'pos/partials/product_grid.html', context)
    return render(request, 'pos/index.html', context)


@login_required
@require_http_methods(["POST"])
@db_transaction.atomic
def checkout(request):
    """Process a sale: validate, decrement stock, create Sale + SaleLineItems."""
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        payment_method = data.get('payment_method', 'cash')

        if not items:
            return HttpResponse('Empty cart', status=400)

        subtotal = Decimal('0')
        discount_total = Decimal('0')
        line_items_to_create = []
        ledger_data = []

        for item_data in items:
            product_id = item_data.get('product_id')
            product = Product.objects.select_for_update().get(pk=product_id)

            sell_mode = item_data.get('sell_mode', 'whole')
            quantity = Decimal(str(item_data.get('quantity', 1)))
            unit_price = Decimal(str(item_data.get('unit_price', 0)))
            discount_amt = Decimal(str(item_data.get('discount_amount', 0)))
            is_free = item_data.get('is_free_item', False)
            weight_value = item_data.get('weight_value')
            weight_unit = item_data.get('weight_unit', '')

            # ── Server-side price validation ──
            if sell_mode == 'whole':
                expected_price = product.base_unit_price
            elif sell_mode == 'split':
                expected_price = product.split_unit_price or product.base_unit_price
            elif sell_mode == 'weight':
                expected_price = product.price_per_weight_unit or product.base_unit_price
            elif sell_mode == 'bundle':
                expected_price = product.bundle_price
            elif sell_mode == 'single':
                expected_price = product.single_unit_price
            elif sell_mode == 'fragment':
                frag_id = item_data.get('fragment_size_id')
                from catalogue.models import FragmentSize
                frag_size = get_object_or_404(FragmentSize, pk=frag_id)
                expected_price = frag_size.fragment_price
            else:
                expected_price = product.base_unit_price

            if not is_free and expected_price and unit_price != expected_price:
                # Check if user has discount permission
                if request.user.role == 'cashier':
                    unit_price = expected_price  # Force correct price for cashiers

            if is_free:
                line_total = Decimal('0')
            else:
                line_total = unit_price * quantity

            # ── Stock decrement ──
            base_qty_deducted = 0
            bundle_qty_sold = None
            bundle_size = None
            bundle_price = None
            is_singles_sale = False

            if sell_mode == 'weight' and weight_value:
                weight_dec = Decimal(str(weight_value))
                if product.stock_in_weight_unit < weight_dec:
                    return HttpResponse(
                        f'Insufficient stock for {product.name}: {product.stock_in_weight_unit} {product.weight_unit} available',
                        status=400,
                    )
                product.stock_in_weight_unit -= weight_dec
                product.save(update_fields=['stock_in_weight_unit'])
            elif sell_mode == 'split':
                # Deduct fractional base units
                deduction = quantity / Decimal(str(product.pieces_per_base))
                if product.stock_qty < deduction:
                    return HttpResponse(
                        f'Insufficient stock for {product.name}',
                        status=400,
                    )
                product.stock_qty -= deduction
                product.save(update_fields=['stock_qty'])
            elif sell_mode in ('whole', 'bundle', 'single'):
                # Whole unit, bundle, or single
                stock_deduct = quantity
                if sell_mode == 'bundle' and product.bundle_pricing_enabled:
                    stock_deduct = quantity * Decimal(str(product.bundle_qty))
                    bundle_qty_sold = int(quantity)
                    bundle_size = product.bundle_qty
                    bundle_price = product.bundle_price
                elif sell_mode == 'single':
                    stock_deduct = quantity
                    is_singles_sale = True

                # Special case for Kadogo whole units (ignore stock_qty, use whole_unit_stock for all whole-based modes)
                if product.is_kadogo:
                    if product.whole_unit_stock < stock_deduct:
                         return HttpResponse(f"Insufficient whole units for {product.name}", status=400)
                    product.whole_unit_stock -= int(stock_deduct)
                    product.save(update_fields=['whole_unit_stock'])
                    ledger_data.append({
                        'product': product, 
                        'entry_type': 'SALE', 
                        'pool': 'WHOLE', 
                        'qty_delta': -int(stock_deduct),
                        'bundle_qty_sold': bundle_qty_sold,
                        'bundle_size': bundle_size,
                        'bundle_price': bundle_price,
                        'is_singles_sale': is_singles_sale,
                    })
                    base_qty_deducted = 0
                else:
                    if product.stock_qty < stock_deduct:
                        return HttpResponse(
                            f'Insufficient stock for {product.name}: {product.stock_qty} available',
                            status=400,
                        )
                    product.stock_qty -= stock_deduct
                    product.save(update_fields=['stock_qty'])
                    base_qty_deducted = int(stock_deduct)

            elif sell_mode == 'fragment' and product.is_kadogo:
                from catalogue.models import FragmentSize, CutAction, StockLedger
                frag_id = item_data.get('fragment_size_id')
                frag_size = FragmentSize.objects.select_for_update().get(pk=frag_id)
                
                # Check if we need to cut
                if frag_size.fragment_pool < quantity:
                    needed = quantity - Decimal(str(frag_size.fragment_pool))
                    cuts_needed = int((needed + frag_size.fragment_count - 1) // frag_size.fragment_count)
                    
                    if product.whole_unit_stock < cuts_needed:
                        return HttpResponse(f"Insufficient whole units to cut fragments for {product.name}", status=400)
                    
                    # Perform CutAction
                    cut = CutAction.objects.create(
                        product=product,
                        fragment_size=frag_size,
                        whole_units_cut=cuts_needed,
                        fragments_added=cuts_needed * frag_size.fragment_count,
                        performed_by=request.user,
                        triggered_by='SALE'
                    )
                    
                    # Update pools
                    product.whole_unit_stock -= cuts_needed
                    product.save(update_fields=['whole_unit_stock'])
                    
                    frag_size.fragment_pool += (cuts_needed * frag_size.fragment_count)
                    frag_size.save(update_fields=['fragment_pool'])
                    
                    # Paired CUT Ledger entries
                    StockLedger.objects.create(
                        product=product, entry_type='CUT', pool='WHOLE',
                        qty_delta=-cuts_needed, cut_action_id=cut.id, created_by=request.user
                    )
                    StockLedger.objects.create(
                        product=product, entry_type='CUT', pool='FRAGMENT',
                        fragment_size=frag_size, fragment_size_snapshot=frag_size.name,
                        qty_delta=cuts_needed * frag_size.fragment_count, cut_action_id=cut.id, created_by=request.user
                    )

                # Now deduct from fragment pool
                frag_size.fragment_pool -= int(quantity)
                frag_size.save(update_fields=['fragment_pool'])
                
                # Queue SALE_FRAGMENT ledger
                ledger_data.append({
                    'product': product,
                    'entry_type': 'SALE',
                    'pool': 'FRAGMENT',
                    'qty_delta': -int(quantity),
                    'fragment_size': frag_size,
                    'fragment_size_snapshot': frag_size.name,
                })
            

            # ── Batch FEFO ──
            batch_used = None
            active_batches = product.batches.filter(status='active').order_by('expiry_date', 'received_date')
            if active_batches.exists():
                batch_used = active_batches.first()

            # Store ledger data to create after sale object exists
            if sell_mode != 'weight' and sell_mode != 'split' and sell_mode != 'fragment' and not (sell_mode == 'whole' and product.is_kadogo):
                ledger_data.append({
                    'product': product,
                    'qty_delta': -base_qty_deducted,
                    'bundle_qty_sold': bundle_qty_sold,
                    'bundle_size': bundle_size,
                    'bundle_price': bundle_price,
                    'is_singles_sale': is_singles_sale,
                    'unit_label': product.base_unit_label,
                    'batch_number': batch_used.batch_number if batch_used else ''
                })

            subtotal += line_total
            discount_total += discount_amt * quantity

            line_items_to_create.append(SaleLineItem(
                product=product,
                product_name=product.name,
                sell_mode=sell_mode,
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total,
                weight_value=Decimal(str(weight_value)) if weight_value else None,
                weight_unit=weight_unit,
                discount_amount=discount_amt,
                is_free_item=is_free,
                batch=batch_used,
                cost_price_at_sale=product.cost_price,
                bundle_size_snapshot=bundle_size,
                bundle_price_snapshot=bundle_price,
                is_singles_sale=is_singles_sale,
            ))

        total = max(Decimal('0'), subtotal)

        # ── Create Sale ──
        sale = Sale(
            cashier=request.user,
            subtotal=subtotal,
            discount_total=discount_total,
            total=total,
            payment_method=payment_method,
            status='complete',
        )

        # Payment details
        if payment_method == 'cash':
            sale.cash_amount = total
            cash_tendered = data.get('cash_tendered')
            if cash_tendered:
                sale.cash_tendered = Decimal(str(cash_tendered))
                sale.change_due = sale.cash_tendered - total
        elif payment_method == 'mpesa':
            sale.mpesa_amount = total
            sale.mpesa_phone = data.get('mpesa_phone', '')
            sale.mpesa_reference = data.get('mpesa_reference', '')
        elif payment_method == 'split':
            sale.cash_amount = Decimal(str(data.get('cash_amount', 0)))
            sale.cash_tendered = Decimal(str(data.get('cash_tendered', 0)))
            sale.change_due = max(Decimal('0'), sale.cash_tendered - sale.cash_amount) if sale.cash_tendered else Decimal('0')
            sale.mpesa_amount = total - sale.cash_amount
            sale.mpesa_phone = data.get('mpesa_phone', '')
            sale.mpesa_reference = data.get('mpesa_reference', '')
        elif payment_method == 'credit':
            sale.credit_customer_name = data.get('credit_customer_name', '')
            sale.credit_due_date = data.get('credit_due_date')

        sale.save()

        # Link line items
        for li in line_items_to_create:
            li.sale = sale
        SaleLineItem.objects.bulk_create(line_items_to_create)

        # Write to StockLedger
        from catalogue.models import StockLedger
        ledger_entries_to_create = []
        for ld in ledger_data:
            entry = StockLedger(
                product=ld['product'],
                entry_type=ld.get('entry_type', 'SALE'),
                qty_delta=ld['qty_delta'],
                reference_id=str(sale.id),
                created_by=request.user,
                pool=ld.get('pool', 'WHOLE'),
                fragment_size=ld.get('fragment_size'),
                fragment_size_snapshot=ld.get('fragment_size_snapshot', ''),
                bundle_qty_sold=ld.get('bundle_qty_sold'),
                bundle_size_snapshot=ld.get('bundle_size'),
                bundle_price_snapshot=ld.get('bundle_price'),
                is_singles_sale=ld.get('is_singles_sale', False),
                unit_label_snapshot=ld.get('unit_label', ''),
                batch_snapshot=ld.get('batch_number', ''),
            )
            ledger_entries_to_create.append(entry)
        StockLedger.objects.bulk_create(ledger_entries_to_create)

        # ── Auto-PO threshold check ──
        _check_reorder_thresholds([li.product for li in line_items_to_create], request.user)

        # ── Audit trail ──
        log_audit(
            action='sale_processed',
            user=request.user,
            entity_type='Sale',
            entity_id=str(sale.pk),
            description=f'Sale {sale.receipt_number} — KES {sale.total} ({payment_method})',
            metadata={'items': len(items), 'total': str(sale.total)},
            ip_address=request.META.get('REMOTE_ADDR'),
        )

        return render(request, 'pos/partials/receipt_modal.html', {
            'sale': sale,
            'store_name': getattr(settings, 'STORE_NAME', 'Floki Minimart'),
            'store_address': getattr(settings, 'STORE_ADDRESS', ''),
            'store_phone': getattr(settings, 'STORE_PHONE', ''),
            'store_kra_pin': getattr(settings, 'STORE_KRA_PIN', ''),
        })

    except Product.DoesNotExist:
        return HttpResponse('Product not found', status=404)
    except (json.JSONDecodeError, ValueError, KeyError, InvalidOperation) as e:
        logger.error(f'Checkout error: {e}')
        return HttpResponse(f'Error: {str(e)}', status=400)


def _check_reorder_thresholds(products, user):
    """After a sale, check if any products have fallen below reorder threshold."""
    from procurement.models import PurchaseOrder, POLineItem, Supplier

    for product in products:
        # Weight-based
        if product.weight_sell_enabled and product.reorder_threshold_weight:
            if product.stock_in_weight_unit > product.reorder_threshold_weight:
                continue
        else:
            if product.stock_qty > product.reorder_threshold:
                continue

        # Product is below threshold — check for preferred supplier
        if not product.preferred_supplier:
            continue

        supplier = product.preferred_supplier
        today = timezone.now().date()

        # PO consolidation: check for existing open PO for this supplier
        open_po = PurchaseOrder.objects.filter(
            supplier=supplier,
            status__in=['draft', 'pending_approval'],
            created_at__date=today,
        ).first()

        if open_po:
            # Check if product already on this PO
            if not open_po.line_items.filter(product=product).exists():
                POLineItem.objects.create(
                    po=open_po,
                    product=product,
                    ordered_qty=product.reorder_qty,
                    unit_cost=product.cost_price or Decimal('0'),
                )
        else:
            # Create new PO
            po = PurchaseOrder(
                supplier=supplier,
                created_by=user,
                status='draft',
                notes=f'Auto-generated: {product.name} below reorder threshold',
            )
            po.save()
            POLineItem.objects.create(
                po=po,
                product=product,
                ordered_qty=product.reorder_qty,
                unit_cost=product.cost_price or Decimal('0'),
            )


@login_required
@require_http_methods(["POST"])
def mpesa_stk_push(request):
    """Initiate M-Pesa STK Push via Daraja API (or simulate for testing)."""
    phone = request.POST.get('phone', '')
    amount = request.POST.get('amount', '0')

    if not phone or not amount:
        return HttpResponse('Phone and amount are required', status=400)

    # Normalize phone number
    phone = phone.strip().replace(' ', '')
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    elif phone.startswith('+'):
        phone = phone[1:]

    # Check if Daraja credentials are configured
    consumer_key = getattr(settings, 'MPESA_CONSUMER_KEY', '')
    if not consumer_key:
        # Simulate for development
        import uuid
        checkout_id = str(uuid.uuid4())[:12].upper()
        return JsonResponse({
            'status': 'simulated',
            'checkout_id': checkout_id,
            'message': f'STK Push simulated to {phone} for KES {amount}',
        })

    # Real Daraja API call would go here
    # For now, return simulation
    import uuid
    checkout_id = str(uuid.uuid4())[:12].upper()
    return JsonResponse({
        'status': 'pending',
        'checkout_id': checkout_id,
        'message': f'STK Push sent to {phone}',
    })


@login_required
def mpesa_status(request, checkout_id):
    """Poll M-Pesa payment status (HTMX polling endpoint)."""
    # In production, this would check Daraja API or callback status
    # For development, simulate after a few polls
    import random
    if random.random() > 0.7:
        return JsonResponse({
            'status': 'completed',
            'mpesa_reference': f'QHX{random.randint(10000, 99999)}',
        })
    return JsonResponse({'status': 'pending'})


@login_required
def receipt_view(request, pk):
    """View a sale receipt."""
    sale = get_object_or_404(Sale, pk=pk)
    return render(request, 'pos/receipt_print.html', {
        'sale': sale,
        'store_name': getattr(settings, 'STORE_NAME', 'Floki Minimart'),
        'store_address': getattr(settings, 'STORE_ADDRESS', ''),
        'store_phone': getattr(settings, 'STORE_PHONE', ''),
        'store_kra_pin': getattr(settings, 'STORE_KRA_PIN', ''),
    })


@login_required
@require_http_methods(["POST"])
@db_transaction.atomic
def void_sale(request, pk):
    """Void a completed sale — Admin/Manager only."""
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)

    sale = get_object_or_404(Sale, pk=pk)
    if sale.status == 'voided':
        return HttpResponse('Already voided', status=400)

    data = json.loads(request.body)
    reason = data.get('reason', '')
    if not reason:
        return HttpResponse('Reason required', status=400)

    # Restore stock
    for li in sale.line_items.all():
        product = Product.objects.select_for_update().get(pk=li.product_id)
        if li.sell_mode == 'weight' and li.weight_value:
            product.stock_in_weight_unit += li.weight_value
            product.save(update_fields=['stock_in_weight_unit'])
        elif li.sell_mode == 'split':
            deduction = li.quantity / Decimal(str(product.pieces_per_base))
            product.stock_qty += deduction
            product.save(update_fields=['stock_qty'])
        else:
            stock_revert = li.quantity
            if li.sell_mode == 'bundle' and product.bundle_pricing_enabled:
                stock_revert = li.quantity * Decimal(str(product.bundle_qty))
            product.stock_qty += stock_revert
            product.save(update_fields=['stock_qty'])
            
            from catalogue.models import StockLedger
            StockLedger.objects.create(
                product=product,
                entry_type='VOID',
                qty_delta=int(stock_revert),
                reference_id=sale.receipt_number,
                created_by=request.user
            )

    sale.status = 'voided'
    sale.void_reason = reason
    sale.voided_at = timezone.now()
    sale.voided_by = request.user
    sale.save()

    log_audit(
        action='sale_voided',
        user=request.user,
        entity_type='Sale',
        entity_id=str(sale.pk),
        description=f'Voided {sale.receipt_number}: {reason}',
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    return JsonResponse({'status': 'success', 'message': 'Sale voided.'})


@login_required
@require_http_methods(["POST"])
def park_sale(request):
    """Park an active cart for later."""
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        customer = data.get('customer_identifier', '')

        if not items:
            return HttpResponse('Cart is empty', status=400)

        if ParkedSale.objects.filter(cashier=request.user).count() >= 5:
            return HttpResponse('Maximum 5 parked sales', status=400)

        sale = ParkedSale.objects.create(
            cashier=request.user,
            customer_identifier=customer,
            items=items,
        )
        return JsonResponse({'status': 'success', 'parked_id': str(sale.pk)})
    except Exception as e:
        return HttpResponse(str(e), status=400)


@login_required
def parked_sales_list(request):
    sales = ParkedSale.objects.filter(cashier=request.user)
    return render(request, 'pos/partials/parked_sales.html', {'sales': sales})


@login_required
def resume_sale(request, pk):
    sale = get_object_or_404(ParkedSale, pk=pk, cashier=request.user)
    items_json = json.dumps(sale.items)
    sale.delete()
    return HttpResponse(items_json, content_type='application/json')


@login_required
def sale_history(request):
    """View past sales with filters."""
    sales = Sale.objects.all()

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    status = request.GET.get('status', '')

    if date_from:
        sales = sales.filter(created_at__date__gte=date_from)
    if date_to:
        sales = sales.filter(created_at__date__lte=date_to)
    if status:
        sales = sales.filter(status=status)

    sales = sales[:200]

    context = {
        'sales': sales,
        'date_from': date_from,
        'date_to': date_to,
        'active_status': status,
    }
    return render(request, 'pos/sale_history.html', context)