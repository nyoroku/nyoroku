import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from catalogue.models import Product, Category, ProductVariant
from .models import Transaction, Coupon, ParkedSale

@login_required
def index(request):
    query = request.GET.get('q', '')
    cat_id = request.GET.get('category', '')
    
    products = Product.objects.filter(approved=True).order_by('name')
    
    if query:
        products = products.filter(name__icontains=query)
    
    if cat_id and cat_id != 'all':
        products = products.filter(category_id=cat_id)
        
    categories = Category.objects.all().order_by('name')
    
    context = {
        'products': products,
        'categories': categories,
        'active_category': cat_id or 'all',
        'query': query,
    }
    
    if request.headers.get('HX-Request'):
        return render(request, 'pos/partials/product_grid.html', context)
        
    return render(request, 'pos/index.html', context)

@login_required
@require_http_methods(["POST"])
def validate_coupon(request):
    """HTMX endpoint to validate a coupon code and return discount preview."""
    code = request.POST.get('code', '').strip().upper()
    subtotal = Decimal(request.POST.get('subtotal', '0'))
    
    if not code:
        return HttpResponse(
            '<div id="coupon-feedback" class="text-text-muted text-xs">Enter a coupon code</div>'
        )
    
    try:
        coupon = Coupon.objects.get(code=code)
    except Coupon.DoesNotExist:
        return HttpResponse(
            '<div id="coupon-feedback" class="text-brand-red text-xs font-bold animate-shake">'
            '❌ Invalid coupon code</div>'
        )
    
    if not coupon.is_valid:
        reason = 'Coupon has expired'
        if coupon.max_uses and coupon.used_count >= coupon.max_uses:
            reason = 'Coupon usage limit reached'
        elif not coupon.is_active:
            reason = 'Coupon is inactive'
        return HttpResponse(
            f'<div id="coupon-feedback" class="text-brand-red text-xs font-bold animate-shake">'
            f'❌ {reason}</div>'
        )
    
    if coupon.min_order and subtotal < coupon.min_order:
        return HttpResponse(
            f'<div id="coupon-feedback" class="text-brand-amber text-xs font-bold">'
            f'⚠️ Minimum order KES {coupon.min_order} required</div>'
        )
    
    # Calculate discount preview
    if coupon.discount_type == 'percent':
        discount = round(subtotal * coupon.discount_value / 100, 2)
        label = f"{coupon.discount_value}% off"
    else:
        discount = min(coupon.discount_value, subtotal)
        label = f"KES {coupon.discount_value} off"
    
    return HttpResponse(
        f'<div id="coupon-feedback" class="space-y-1">'
        f'<div class="text-brand-green text-xs font-bold flex items-center gap-1">'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>'
        f'{label} — Save KES {discount}</div>'
        f'<input type="hidden" id="coupon-discount-value" value="{coupon.discount_value}" />'
        f'<input type="hidden" id="coupon-discount-type" value="{coupon.discount_type}" />'
        f'</div>'
    )

@login_required
@require_http_methods(["POST"])
def checkout(request):
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        payment_method = data.get('payment_method', 'cash')
        coupon_code = data.get('coupon_code', '').strip().upper()
        
        if not items:
            return HttpResponse('Empty cart', status=400)
            
        subtotal = Decimal('0')
        line_discounts_total = Decimal('0')
        for item in items:
            # Inject current cost price for profit reporting
            try:
                product = Product.objects.get(id=item.get('id'))
                item['cost_price'] = float(product.cost_price or 0)
            except Product.DoesNotExist:
                item['cost_price'] = 0.0
                
            qty = int(item.get('qty', 1))
            line_price = Decimal(str(item['price']))
            line_discount = Decimal(str(item.get('discount', 0)))
            
            line_discounts_total += line_discount * qty
            subtotal += (line_price - line_discount) * qty
            
        # Process coupon
        coupon_obj = None
        coupon_discount = Decimal('0')
        
        if coupon_code:
            try:
                coupon_obj = Coupon.objects.get(code=coupon_code)
                if coupon_obj.is_valid:
                    if coupon_obj.discount_type == 'percent':
                        coupon_discount = round(subtotal * coupon_obj.discount_value / 100, 2)
                    else:
                        coupon_discount = min(coupon_obj.discount_value, subtotal)
                    
                    # Check minimum order
                    if coupon_obj.min_order and subtotal < coupon_obj.min_order:
                        coupon_discount = Decimal('0')
                        coupon_obj = None
                    else:
                        # Increment usage
                        coupon_obj.used_count += 1
                        coupon_obj.save()
                else:
                    coupon_obj = None
            except Coupon.DoesNotExist:
                coupon_obj = None
        
        total = max(Decimal('0'), subtotal - coupon_discount)
        
        # Create Transaction
        transaction = Transaction.objects.create(
            cashier=request.user,
            items=items,
            subtotal=subtotal + line_discounts_total,
            discount=line_discounts_total,
            coupon=coupon_obj,
            coupon_discount=coupon_discount,
            total=total,
            payment_method=payment_method,
            status='complete'
        )
        
        # Deduct stock
        for item in items:
            item_id = item.get('id')
            qty = int(item.get('qty', 0))
            if not item_id or qty <= 0:
                continue
                
            try:
                # First check if it's a Variant
                variant = ProductVariant.objects.get(id=item_id)
                variant.stock_qty = max(0, variant.stock_qty - qty)
                variant.save(update_fields=['stock_qty'])
            except ProductVariant.DoesNotExist:
                # Fallback to Product
                try:
                    product = Product.objects.get(id=item_id)
                    product.stock_qty = max(0, product.stock_qty - qty)
                    product.save(update_fields=['stock_qty'])
                except Product.DoesNotExist:
                    pass
                
        return render(request, 'pos/partials/receipt_modal.html', {'transaction': transaction})
        
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        return HttpResponse(f'Error processing checkout: {str(e)}', status=400)

@login_required
def receipt_print(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk)
    return render(request, 'pos/receipt_print.html', {'transaction': transaction})

# ─── Coupon Management ──────────────────────────────────────────────

@login_required
def coupon_list(request):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    
    coupons = Coupon.objects.all().order_by('-created_at')
    active_count = coupons.filter(is_active=True).count()
    
    context = {
        'coupons': coupons,
        'active_count': active_count,
    }
    return render(request, 'pos/coupon_list.html', context)

@login_required
@require_http_methods(["POST"])
def add_coupon(request):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    
    code = request.POST.get('code', '').strip().upper()
    description = request.POST.get('description', '')
    discount_type = request.POST.get('discount_type', 'fixed')
    discount_value = request.POST.get('discount_value', '0')
    min_order = request.POST.get('min_order') or None
    max_uses = request.POST.get('max_uses') or None
    valid_until = request.POST.get('valid_until') or None
    
    if not code or not discount_value:
        return HttpResponse('Code and discount value are required', status=400)
    
    if Coupon.objects.filter(code=code).exists():
        return HttpResponse('A coupon with this code already exists', status=400)
    
    Coupon.objects.create(
        code=code,
        description=description,
        discount_type=discount_type,
        discount_value=discount_value,
        min_order=min_order,
        max_uses=int(max_uses) if max_uses else None,
        valid_until=valid_until,
        created_by=request.user,
    )
    return redirect('pos:coupon_list')

@login_required
@require_http_methods(["POST"])
def toggle_coupon(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    
    coupon = get_object_or_404(Coupon, pk=pk)
    coupon.is_active = not coupon.is_active
    coupon.save()
    
    if request.headers.get('HX-Request'):
        return render(request, 'pos/partials/coupon_row.html', {'coupon': coupon})
    return redirect('pos:coupon_list')

@login_required
@require_http_methods(["DELETE", "POST"])
def delete_coupon(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    
    coupon = get_object_or_404(Coupon, pk=pk)
    coupon.delete()
    
    if request.headers.get('HX-Request'):
        return HttpResponse('')
    return redirect('pos:coupon_list')

@login_required
@require_http_methods(["POST"])
def park_sale(request):
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        customer = data.get('customer_identifier', '')
        
        if not items:
            return HttpResponse('Cart is empty', status=400)
            
        # Max limit check
        if ParkedSale.objects.filter(cashier=request.user).count() >= 5:
            return HttpResponse('Maximum 5 parked sales per cashier allowed.', status=400)
            
        sale = ParkedSale.objects.create(
            cashier=request.user,
            customer_identifier=customer,
            items=items
        )
        return JsonResponse({'status': 'success', 'parked_id': sale.id})
    except Exception as e:
        return HttpResponse(str(e), status=400)

@login_required
def parked_sales_list(request):
    sales = ParkedSale.objects.filter(cashier=request.user)
    return render(request, 'pos/partials/parked_sales_list.html', {'sales': sales})

@login_required
def resume_sale(request, pk):
    sale = get_object_or_404(ParkedSale, pk=pk, cashier=request.user)
    items_json = json.dumps(sale.items)
    sale.delete()  # Remove from parked once resumed
    return HttpResponse(items_json, content_type="application/json")

@login_required
def delete_parked_sale(request, pk):
    sale = get_object_or_404(ParkedSale, pk=pk, cashier=request.user)
    sale.delete()
    return parked_sales_list(request)

@login_required
@require_http_methods(["POST"])
def void_transaction(request, pk):
    if request.user.role not in ['admin', 'manager']:
        return HttpResponse('Unauthorized. Admin or Manager required to void.', status=403)
        
    transaction = get_object_or_404(Transaction, pk=pk)
    
    if transaction.status == 'voided':
        return HttpResponse('Transaction already voided.', status=400)
        
    data = json.loads(request.body)
    reason = data.get('reason', '')
    if not reason:
        return HttpResponse('Void requires a reason.', status=400)
        
    from datetime import timedelta
    from catalogue.models import PendingAction
    
    time_since = timezone.now() - transaction.created_at
    if time_since > timedelta(hours=24) and request.user.role != 'admin':
        # Route to admin via pending action if it's over 24h and user is a manager
        PendingAction.objects.create(
            action_type='void_transaction',
            submitted_by=request.user,
            details={'transaction_id': str(transaction.id), 'reason': reason}
        )
        return JsonResponse({'status': 'pending_approval', 'message': 'Void requested successfully. Requires Admin approval.'})

    # Direct Void
    transaction.status = 'voided'
    transaction.void_reason = reason
    transaction.voided_at = timezone.now()
    transaction.voided_by = request.user
    transaction.save()
    
    # Reverse stock
    for item in transaction.items:
        qty = int(item.get('qty', 0))
        if qty:
            if item.get('is_variant'):
                try:
                    pv = ProductVariant.objects.get(id=item.get('id'))
                    pv.stock_qty += qty
                    pv.save()
                except ProductVariant.DoesNotExist:
                    pass
            else:
                try:
                    p = Product.objects.get(id=item.get('id'))
                    p.stock_qty += qty
                    p.save()
                except Product.DoesNotExist:
                    pass
                    
    return JsonResponse({'status': 'success', 'message': 'Transaction voided.'})
