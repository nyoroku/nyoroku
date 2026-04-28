import json
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, get_object_or_404, redirect
from django.db import transaction as db_transaction
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from .models import Product, Category, SubCategory, Batch, FragmentSize
from core.models import log_audit


def _dec_or_none(val):
    if val is None or str(val).strip() == '':
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError):
        return None


def _int_or_default(val, default=0):
    if val is None or str(val).strip() == '':
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


@login_required
def inventory_list(request):
    """Inventory management — product list with filters."""
    query = request.GET.get('q', '')
    cat_id = request.GET.get('category', '')
    subcat_id = request.GET.get('subcategory', '')
    stock_filter = request.GET.get('stock', '')

    products = Product.objects.filter(is_active=True).select_related(
        'subcategory', 'subcategory__category', 'preferred_supplier'
    ).order_by('name')

    if query:
        from django.db.models import Q
        products = products.filter(
            Q(name__icontains=query) | Q(sku__icontains=query) | Q(barcode__icontains=query)
        )
    if cat_id:
        products = products.filter(subcategory__category_id=cat_id)
    if subcat_id:
        products = products.filter(subcategory_id=subcat_id)
    if stock_filter == 'low':
        products = [p for p in products if p.is_low_stock]
    elif stock_filter == 'out':
        products = products.filter(stock_qty__lte=0, weight_sell_enabled=False) | \
                   products.filter(stock_in_weight_unit__lte=0, weight_sell_enabled=True)

    categories = Category.objects.all().order_by('order', 'name')
    subcategories = SubCategory.objects.all().order_by('order', 'name')

    # Prepare rich data for modals
    products_data = []
    for product in products:
        fragments = []
        if product.is_kadogo:
            fragments = list(product.fragment_sizes.filter(is_active=True).values(
                'id', 'name', 'fragment_count', 'fragment_price'
            ))
            # Rename fragment_count to count for JS compatibility
            for f in fragments:
                f['count'] = f.pop('fragment_count')
        
        products_data.append({
            'product': product,
            'fragments': fragments,
        })

    context = {
        'products_data': products_data,
        'categories': categories,
        'subcategories': subcategories,
        'query': query,
        'active_category': cat_id,
        'active_subcategory': subcat_id,
        'stock_filter': stock_filter,
        'product_count': len(products),
    }

    if request.headers.get('HX-Request'):
        return render(request, 'catalogue/partials/product_list.html', context)
    return render(request, 'catalogue/inventory.html', context)


@login_required
@require_http_methods(["POST"])
def add_product(request):
    """Create a new product with all sell-mode configurations."""
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)

    name = request.POST.get('name', '').strip()
    if not name:
        return HttpResponse('Product name is required', status=400)

    if Product.objects.filter(name__iexact=name).exists():
        return HttpResponse(f'A product with name "{name}" already exists', status=400)

    subcat_id = request.POST.get('subcategory_id')
    subcategory = get_object_or_404(SubCategory, id=subcat_id)

    product = Product(
        name=name,
        subcategory=subcategory,
        image=request.POST.get('image', '📦'),
        base_unit_label=request.POST.get('base_unit_label', 'Unit'),
        base_unit_price=Decimal(request.POST.get('base_unit_price', '0')),
        cost_price=_dec_or_none(request.POST.get('cost_price')),
        is_active=True,
        created_by=request.user,
    )

    # Kadogo / Fractional sell
    product.is_kadogo = request.POST.get('is_kadogo') == 'on'
    if product.is_kadogo:
        product.whole_unit_label = request.POST.get('whole_unit_label', 'Bar')
        # We don't set whole_unit_stock here, it starts at 0 or via adjustment

    # Split sell (Legacy support)
    product.split_enabled = request.POST.get('split_enabled') == 'on'
    if product.split_enabled:
        product.split_unit_label = request.POST.get('split_unit_label', 'Piece')
        product.split_unit_price = _dec_or_none(request.POST.get('split_unit_price'))
        product.pieces_per_base = _int_or_default(request.POST.get('pieces_per_base'), 1)
        product.split_min_qty = _int_or_default(request.POST.get('split_min_qty'), 1)
        product.split_inventory_mode = request.POST.get('split_inventory_mode', 'FIXED_CUT')

    # Weight sell
    product.weight_sell_enabled = request.POST.get('weight_sell_enabled') == 'on'
    if product.weight_sell_enabled:
        product.weight_unit = request.POST.get('weight_unit', 'kg')
        product.price_per_weight_unit = _dec_or_none(request.POST.get('price_per_weight_unit'))
        product.stock_in_weight_unit = _dec_or_none(request.POST.get('stock_in_weight_unit')) or Decimal('0')
        product.weight_sell_mode = request.POST.get('weight_sell_mode', 'BY_WEIGHT')
        product.min_weight_increment = _dec_or_none(request.POST.get('min_weight_increment')) or Decimal('0.050')
        product.reorder_threshold_weight = _dec_or_none(request.POST.get('reorder_threshold_weight'))

    # UoM & Bundle Pricing
    product.purchase_unit_label = request.POST.get('purchase_unit_label', 'unit')
    product.units_per_purchase = int(request.POST.get('units_per_purchase', 1))
    product.bundle_pricing_enabled = request.POST.get('bundle_pricing_enabled') == 'on'
    if product.bundle_pricing_enabled:
        product.bundle_qty = int(request.POST.get('bundle_qty', 1))
        product.bundle_price = _dec_or_none(request.POST.get('bundle_price'))
        product.allow_single_sale = request.POST.get('allow_single_sale') == 'on'
        product.single_unit_price = _dec_or_none(request.POST.get('single_unit_price'))

    # Stock
    product.stock_qty = _dec_or_none(request.POST.get('stock_qty')) or Decimal('0')
    product.reorder_threshold = int(request.POST.get('reorder_threshold', 5))
    product.reorder_qty = int(request.POST.get('reorder_qty', 10))

    # Supplier & Margin
    supplier_id = request.POST.get('preferred_supplier')
    if supplier_id:
        from procurement.models import Supplier
        try:
            product.preferred_supplier = Supplier.objects.get(pk=supplier_id)
        except Supplier.DoesNotExist:
            pass

    product.desired_margin_pct = _dec_or_none(request.POST.get('desired_margin_pct'))
    product.desired_margin_kes = _dec_or_none(request.POST.get('desired_margin_kes'))

    product.save()

    # Create default fragment size if kadogo enabled
    if product.is_kadogo:
        kadogo_name = request.POST.get('kadogo_name', 'Piece')
        kadogo_count = int(request.POST.get('kadogo_count', 7))
        kadogo_price = Decimal(request.POST.get('kadogo_price', '0'))
        
        FragmentSize.objects.create(
            product=product,
            name=kadogo_name,
            fragment_count=kadogo_count,
            fragment_price=kadogo_price,
            is_default=True
        )

    log_audit(
        action='stock_adjusted',
        user=request.user,
        entity_type='Product',
        entity_id=str(product.pk),
        description=f'Product created: {product.name}',
        ip_address=request.META.get('REMOTE_ADDR'),
    )

    if request.headers.get('HX-Request'):
        response = HttpResponse('')
        response['HX-Refresh'] = 'true'
        return response
    return redirect('catalogue:inventory')


@login_required
@require_http_methods(["POST"])
def edit_product(request):
    """Edit an existing product."""
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)

    product_id = request.POST.get('id')
    product = get_object_or_404(Product, id=product_id)

    name = request.POST.get('name', '').strip()
    if Product.objects.filter(name__iexact=name).exclude(id=product.id).exists():
        return HttpResponse(f'A product with name "{name}" already exists', status=400)

    old_price = product.base_unit_price
    old_bundle_price = product.bundle_price
    old_bundle_qty = product.bundle_qty
    old_purchase_label = product.purchase_unit_label
    old_purchase_multiplier = product.units_per_purchase

    product.name = name
    subcat_id = request.POST.get('subcategory_id')
    if subcat_id:
        product.subcategory = get_object_or_404(SubCategory, id=subcat_id)

    product.image = request.POST.get('image', product.image)
    product.base_unit_label = request.POST.get('base_unit_label', product.base_unit_label)
    product.base_unit_price = Decimal(request.POST.get('base_unit_price', str(product.base_unit_price)))
    product.cost_price = _dec_or_none(request.POST.get('cost_price'))

    # Kadogo sell
    product.is_kadogo = request.POST.get('is_kadogo') == 'on'
    if product.is_kadogo:
        product.whole_unit_label = request.POST.get('whole_unit_label', 'Bar')

    # Split sell
    product.split_enabled = request.POST.get('split_enabled') == 'on'
    if product.split_enabled:
        product.split_unit_label = request.POST.get('split_unit_label', 'Piece')
        product.split_unit_price = _dec_or_none(request.POST.get('split_unit_price'))
        product.pieces_per_base = _int_or_default(request.POST.get('pieces_per_base'), 1)
        product.split_min_qty = _int_or_default(request.POST.get('split_min_qty'), 1)
        product.split_inventory_mode = request.POST.get('split_inventory_mode', 'FIXED_CUT')

    # Weight sell
    product.weight_sell_enabled = request.POST.get('weight_sell_enabled') == 'on'
    if product.weight_sell_enabled:
        product.weight_unit = request.POST.get('weight_unit', 'kg')
        product.price_per_weight_unit = _dec_or_none(request.POST.get('price_per_weight_unit'))
        product.weight_sell_mode = request.POST.get('weight_sell_mode', 'BY_WEIGHT')
        product.min_weight_increment = _dec_or_none(request.POST.get('min_weight_increment')) or Decimal('0.050')
        product.reorder_threshold_weight = _dec_or_none(request.POST.get('reorder_threshold_weight'))

    # UoM & Bundle Pricing
    product.purchase_unit_label = request.POST.get('purchase_unit_label', product.purchase_unit_label)
    product.units_per_purchase = _int_or_default(request.POST.get('units_per_purchase'), product.units_per_purchase)
    product.bundle_pricing_enabled = request.POST.get('bundle_pricing_enabled') == 'on'
    if product.bundle_pricing_enabled:
        product.bundle_qty = _int_or_default(request.POST.get('bundle_qty'), product.bundle_qty)
        product.bundle_price = _dec_or_none(request.POST.get('bundle_price'))
        product.allow_single_sale = request.POST.get('allow_single_sale') == 'on'
        product.single_unit_price = _dec_or_none(request.POST.get('single_unit_price'))

    # Stock
    product.reorder_threshold = _int_or_default(request.POST.get('reorder_threshold'), product.reorder_threshold)
    product.reorder_qty = _int_or_default(request.POST.get('reorder_qty'), product.reorder_qty)

    # Supplier & Margin
    supplier_id = request.POST.get('preferred_supplier')
    if supplier_id:
        from procurement.models import Supplier
        try:
            product.preferred_supplier = Supplier.objects.get(pk=supplier_id)
        except Supplier.DoesNotExist:
            pass
    elif supplier_id == '':
        product.preferred_supplier = None

    product.desired_margin_pct = _dec_or_none(request.POST.get('desired_margin_pct'))
    product.desired_margin_kes = _dec_or_none(request.POST.get('desired_margin_kes'))

    product.save()

    # Price change audit
    if old_price != product.base_unit_price:
        log_audit(
            action='price_changed',
            user=request.user,
            entity_type='Product',
            entity_id=str(product.pk),
            description=f'{product.name}: KES {old_price} → KES {product.base_unit_price}',
            metadata={'old_price': str(old_price), 'new_price': str(product.base_unit_price)},
            ip_address=request.META.get('REMOTE_ADDR'),
        )

    if old_bundle_price != product.bundle_price or old_bundle_qty != product.bundle_qty:
        log_audit(
            action='bundle_config_changed',
            user=request.user,
            entity_type='Product',
            entity_id=str(product.pk),
            description=f'{product.name} Bundle: {old_bundle_qty} @ {old_bundle_price} → {product.bundle_qty} @ {product.bundle_price}',
            metadata={'old_qty': old_bundle_qty, 'new_qty': product.bundle_qty, 'old_price': str(old_bundle_price), 'new_price': str(product.bundle_price)},
            ip_address=request.META.get('REMOTE_ADDR'),
        )

    if old_purchase_label != product.purchase_unit_label or old_purchase_multiplier != product.units_per_purchase:
        log_audit(
            action='uom_config_changed',
            user=request.user,
            entity_type='Product',
            entity_id=str(product.pk),
            description=f'{product.name} UoM: {old_purchase_label} (x{old_purchase_multiplier}) → {product.purchase_unit_label} (x{product.units_per_purchase})',
            ip_address=request.META.get('REMOTE_ADDR'),
        )

    # Manage Fragment Sizes
    if product.is_kadogo:
        # Update existing fragments
        for frag in product.fragment_sizes.all():
            name = request.POST.get(f'frag_name_{frag.id}')
            count = request.POST.get(f'frag_count_{frag.id}')
            price = request.POST.get(f'frag_price_{frag.id}')
            active = request.POST.get(f'frag_active_{frag.id}') == 'on'
            
            if name:
                frag.name = name
                frag.fragment_count = _int_or_default(count, frag.fragment_count)
                frag.fragment_price = _dec_or_none(price) or frag.fragment_price
                frag.is_active = active
                frag.save()
        
        # Add new fragment
        new_name = request.POST.get('new_frag_name')
        if new_name:
            new_count = _int_or_default(request.POST.get('new_frag_count'), 2)
            new_price = _dec_or_none(request.POST.get('new_frag_price')) or Decimal('0')
            FragmentSize.objects.create(
                product=product,
                name=new_name,
                fragment_count=new_count,
                fragment_price=new_price
            )

    try:
        product.save()
    except Exception as e:
        return HttpResponse(f'Error saving product: {str(e)}', status=400)

    if request.headers.get('HX-Request'):
        response = HttpResponse('')
        response['HX-Refresh'] = 'true'
        return response
    return redirect('catalogue:inventory')


@login_required
@require_http_methods(["POST", "DELETE"])
def delete_product(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    product = get_object_or_404(Product, pk=pk)
    product.is_active = False
    product.save()

    if request.headers.get('HX-Request'):
        return HttpResponse('')
    return redirect('catalogue:inventory')


@login_required
@require_http_methods(["POST"])
def bulk_delete_products(request):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    try:
        data = json.loads(request.body)
        product_ids = data.get('product_ids', [])
        if product_ids:
            Product.objects.filter(id__in=product_ids).update(is_active=False)
        return HttpResponse('OK', status=200)
    except Exception as e:
        return HttpResponse(str(e), status=400)


@login_required
def edit_product_form(request, pk):
    """Render the edit form modal for a specific product."""
    user_role = str(request.user.role).lower()
    if user_role not in ('admin', 'manager'):
        return HttpResponse(f'Unauthorized: {user_role} role not allowed', status=403)
    
    product = get_object_or_404(Product, pk=pk)
    categories = Category.objects.all().order_by('order', 'name')
    return render(request, 'catalogue/partials/edit_product_modal.html', {
        'product': product,
        'categories': categories,
    })


# ── Category / SubCategory Management ──

@login_required
def category_list(request):
    if request.user.role != 'admin':
        return redirect('catalogue:inventory')
    categories = Category.objects.all().prefetch_related('subcategories')
    return render(request, 'catalogue/category_list.html', {'categories': categories})


@login_required
@require_http_methods(["POST"])
def add_category(request):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    name = request.POST.get('name', '').strip()
    icon = request.POST.get('icon', '📦')
    if name:
        Category.objects.get_or_create(name=name, defaults={'icon': icon})
    return redirect('catalogue:category_list')


@login_required
@require_http_methods(["POST"])
def edit_category(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    cat = get_object_or_404(Category, pk=pk)
    name = request.POST.get('name', '').strip()
    if name:
        cat.name = name
        cat.icon = request.POST.get('icon', cat.icon)
        cat.save()
    return redirect('catalogue:category_list')


@login_required
@require_http_methods(["POST", "DELETE"])
def delete_category(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    cat = get_object_or_404(Category, pk=pk)
    cat.delete()
    return redirect('catalogue:category_list')


@login_required
@require_http_methods(["POST"])
def add_subcategory(request):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    cat_id = request.POST.get('category_id')
    name = request.POST.get('name', '').strip()
    if cat_id and name:
        category = get_object_or_404(Category, pk=cat_id)
        SubCategory.objects.get_or_create(category=category, name=name)
    return redirect('catalogue:category_list')


@login_required
@require_http_methods(["POST", "DELETE"])
def delete_subcategory(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    subcat = get_object_or_404(SubCategory, pk=pk)
    subcat.delete()
    return redirect('catalogue:category_list')


# ── Batch Management ──

@login_required
def batch_list(request, product_pk):
    product = get_object_or_404(Product, pk=product_pk)
    batches = product.batches.all().order_by('expiry_date')
    return render(request, 'catalogue/partials/batch_list.html', {
        'product': product,
        'batches': batches,
    })


@login_required
@require_http_methods(["POST"])
def quarantine_batch(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    batch = get_object_or_404(Batch, pk=pk)
    batch.status = 'quarantined'
    batch.save()
    log_audit(
        action='stock_adjusted',
        user=request.user,
        entity_type='Batch',
        entity_id=str(batch.pk),
        description=f'Quarantined batch {batch.batch_number} of {batch.product.name}',
        ip_address=request.META.get('REMOTE_ADDR'),
    )
    return redirect('catalogue:inventory')


def _dec_or_none(val):
    """Convert string to Decimal or return None for empty/invalid values."""
    if val is None or val == '' or val == 'None':
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError):
        return None
@login_required
@require_http_methods(["POST"])
def manual_stock_adjustment(request):
    product_id = request.POST.get('product_id')
    product = get_object_or_404(Product, pk=product_id)
    
    adj_type = request.POST.get('adjustment_type', 'add') # 'add' or 'subtract'
    mode = request.POST.get('mode', 'units') # 'units' or 'packets'
    qty = Decimal(request.POST.get('qty', '0'))
    reason = request.POST.get('reason', 'Manual Adjustment')
    
    if qty <= 0:
        return HttpResponse('Invalid quantity', status=400)
        
    base_qty_delta = qty
    if mode == 'packets':
        base_qty_delta = qty * Decimal(str(product.units_per_purchase))
        
    if adj_type == 'subtract':
        base_qty_delta = -base_qty_delta
        
    # Update product stock
    if product.is_kadogo:
        product.whole_unit_stock += int(base_qty_delta)
    else:
        product.stock_qty += base_qty_delta
    product.save()
    
    # Write to ledger
    from .models import StockLedger
    StockLedger.objects.create(
        product=product,
        entry_type='ADJUSTMENT',
        qty_delta=int(base_qty_delta),
        reference_id=f"MANUAL-{request.user.username}",
        created_by=request.user
    )
    
    log_audit(
        action='stock_adjusted',
        user=request.user,
        entity_type='Product',
        entity_id=str(product.pk),
        description=f'Manual stock {adj_type}: {base_qty_delta} {product.whole_unit_label if product.is_kadogo else product.base_unit_label}s ({reason})',
        ip_address=request.META.get('REMOTE_ADDR'),
    )
    
    return redirect('catalogue:inventory')


@login_required
@require_http_methods(["POST"])
def manual_cut(request):
    """Admin manually cuts whole units into fragments outside of a sale."""
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)
        
    product_id = request.POST.get('product_id')
    frag_id = request.POST.get('fragment_size_id')
    whole_qty = int(request.POST.get('whole_qty', 1))
    
    from .models import Product, FragmentSize, CutAction, StockLedger
    product = get_object_or_404(Product, pk=product_id)
    frag_size = get_object_or_404(FragmentSize, pk=frag_id, product=product)
    
    if product.whole_unit_stock < whole_qty:
        return HttpResponse('Insufficient whole unit stock to perform cut', status=400)
        
    with db_transaction.atomic():
        # Create CutAction
        cut = CutAction.objects.create(
            product=product,
            fragment_size=frag_size,
            whole_units_cut=whole_qty,
            fragments_added=whole_qty * frag_size.fragment_count,
            performed_by=request.user,
            triggered_by='MANUAL'
        )
        
        # Update pools
        product.whole_unit_stock -= whole_qty
        product.save(update_fields=['whole_unit_stock'])
        
        frag_size.fragment_pool += (whole_qty * frag_size.fragment_count)
        frag_size.save(update_fields=['fragment_pool'])
        
        # Paired CUT Ledger entries
        StockLedger.objects.create(
            product=product, entry_type='CUT', pool='WHOLE',
            qty_delta=-whole_qty, cut_action_id=cut.id, created_by=request.user
        )
        StockLedger.objects.create(
            product=product, entry_type='CUT', pool='FRAGMENT',
            fragment_size=frag_size, fragment_size_snapshot=frag_size.name,
            qty_delta=whole_qty * frag_size.fragment_count, cut_action_id=cut.id, created_by=request.user
        )
        
    log_audit(
        action='stock_cut',
        user=request.user,
        entity_type='Product',
        entity_id=str(product.pk),
        description=f'Manual cut: {whole_qty} {product.whole_unit_label}s into {whole_qty * frag_size.fragment_count} {frag_size.name}s',
        ip_address=request.META.get('REMOTE_ADDR'),
    )
    
    return redirect('catalogue:inventory')
