from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .models import Product, ProductType, PendingAction, ProductVariant

@login_required
def inventory_list(request):
    query = request.GET.get('q', '')
    status = request.GET.get('status', 'all')
    
    products = Product.objects.all().order_by('-created_at')
    
    if query:
        products = products.filter(name__icontains=query)
    
    if status == 'pending' and request.user.role == 'admin':
        products = products.filter(approved=False)
    
    pending_count = Product.objects.filter(approved=False).count()
    product_types = ProductType.objects.all().order_by('name')
    
    context = {
        'products': products,
        'product_types': product_types,
        'pending_count': pending_count,
        'active_status': status,
        'query': query,
    }
    
    if request.headers.get('HX-Request'):
        return render(request, 'catalogue/partials/product_list.html', context)
        
    return render(request, 'catalogue/inventory.html', context)

@login_required
@require_http_methods(["POST"])
def add_product(request):
    name = request.POST.get('name')
    type_name = request.POST.get('type_name', '').strip()
    price = request.POST.get('price')
    cost_price = request.POST.get('cost_price')
    stock_qty = request.POST.get('stock_qty')
    image = request.POST.get('image', '📦')

    # Create-or-get ProductType by name
    if type_name:
        product_type, _ = ProductType.objects.get_or_create(name=type_name)
    else:
        return HttpResponse('Type name is required', status=400)
    
    # Logic: Admin auto-approves, Cashier pending
    is_approved = (request.user.role == 'admin')
    
    product = Product.objects.create(
        name=name,
        product_type=product_type,
        price=price,
        cost_price=cost_price or None,
        stock_qty=stock_qty or 0,
        image=image,
        approved=is_approved,
        pending_by=request.user if not is_approved else None
    )
    
    # Multi-option variants logic
    options_json = request.POST.get('options_json')
    variants_json = request.POST.get('variants_json')

    if options_json:
        import json
        try:
            options_data = json.loads(options_json)
            for opt in options_data:
                from .models import ProductVariantOptionType
                ProductVariantOptionType.objects.create(
                    product=product,
                    name=opt['name'],
                    values=opt['values']
                )
        except (json.JSONDecodeError, KeyError):
            pass

    if variants_json:
        import json
        from decimal import Decimal, InvalidOperation
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            variants = json.loads(variants_json)
            # Remove existing variants if any (to handle re-submissions or bulk updates)
            product.variants.all().delete()
            
            for v in variants:
                try:
                    price_input = v.get('price_override') or v.get('price')
                    price_val = Decimal(str(price_input)) if price_input not in [None, ''] else None
                    
                    variant_cost = v.get('cost_price')
                    variant_cost = Decimal(str(variant_cost)) if variant_cost not in [None, '', 0, '0'] else None
                    
                    ProductVariant.objects.create(
                        product=product,
                        options=v.get('options', {}),
                        price_override=price_val,
                        cost_price=variant_cost,
                        stock_qty=int(v.get('stock_qty', 0)),
                        reorder_level=5
                    )
                except (InvalidOperation, ValueError, TypeError) as e:
                    logger.error(f"Error creating single variant: {str(e)}")
                    continue
            
            if product.variants.exists():
                product.has_variants = True
                product.save()
        except Exception as e:
            logger.error(f"Error parsing variants_json: {str(e)}")
    
    return redirect('catalogue:inventory')

@login_required
@require_http_methods(["POST"])
def edit_product(request):
    product_id = request.POST.get('id')
    product = get_object_or_404(Product, id=product_id)
    
    product.name = request.POST.get('name')
    
    type_name = request.POST.get('type_name', '').strip()
    if type_name:
        product_type, _ = ProductType.objects.get_or_create(name=type_name)
        product.product_type = product_type
    
    product.price = request.POST.get('price')
    cost_price = request.POST.get('cost_price')
    product.cost_price = cost_price if cost_price else None
    product.image = request.POST.get('image', '📦')
    
    # If edited by a non-admin, force it to pending mode again
    if request.user.role != 'admin':
        product.approved = False
        product.pending_by = request.user
        
    product.save()

    # Handle Options and Variants in Edit
    options_json = request.POST.get('options_json')
    variants_json = request.POST.get('variants_json')

    if options_json:
        import json
        try:
            options_data = json.loads(options_json)
            # Replace existing option types
            product.option_types.all().delete()
            for opt in options_data:
                from .models import ProductVariantOptionType
                ProductVariantOptionType.objects.create(
                    product=product,
                    name=opt['name'],
                    values=opt['values']
                )
        except (json.JSONDecodeError, KeyError):
            pass

    if variants_json:
        import json
        from decimal import Decimal, InvalidOperation
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            variants = json.loads(variants_json)
            # Remove existing variants not in the new list (if they have IDs)
            keep_ids = [v.get('id') for v in variants if v.get('id')]
            product.variants.exclude(id__in=keep_ids).delete()
            
            for v in variants:
                try:
                    # Support both 'price_override' and 'price' keys for flexibility
                    price_input = v.get('price_override') or v.get('price')
                    price_val = Decimal(str(price_input)) if price_input not in [None, ''] else None
                    
                    variant_cost = v.get('cost_price')
                    variant_cost = Decimal(str(variant_cost)) if variant_cost not in [None, '', 0, '0'] else None
                    
                    if v.get('id'):
                        variant_obj = ProductVariant.objects.filter(id=v['id'], product=product).first()
                        if variant_obj:
                            variant_obj.options = v.get('options', {})
                            variant_obj.price_override = price_val
                            variant_obj.cost_price = variant_cost
                            variant_obj.stock_qty = int(v.get('stock_qty', 0))
                            variant_obj.save()
                    else:
                        ProductVariant.objects.create(
                            product=product,
                            options=v.get('options', {}),
                            price_override=price_val,
                            cost_price=variant_cost,
                            stock_qty=int(v.get('stock_qty', 0)),
                            reorder_level=5
                        )
                except (InvalidOperation, ValueError, TypeError) as e:
                    logger.error(f"Error updating single variant: {str(e)}")
                    continue
            
            product.has_variants = product.variants.exists()
            product.save()
        except Exception as e:
            logger.error(f"Error parsing variants_json in edit: {str(e)}")
            
    return redirect('catalogue:inventory')

@login_required
@require_http_methods(["POST"]) # HTMX uses POST fallback if PATCH is complex
def approve_product(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    
    product = get_object_or_404(Product, pk=pk)
    product.approved = True
    product.save()
    
    return render(request, 'catalogue/partials/product_row.html', {'product': product})

@login_required
@require_http_methods(["DELETE", "POST"])
def delete_product(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
        
    product = get_object_or_404(Product, pk=pk)
    product.delete()
    
    if request.headers.get('HX-Request'):
        return HttpResponse('') # Remove from DOM
    
    return redirect('catalogue:inventory')

@login_required
def type_list(request):
    if request.user.role != 'admin':
        return redirect('catalogue:inventory')
    
    product_types = ProductType.objects.all().order_by('name').prefetch_related('products')
    return render(request, 'catalogue/type_list.html', {'product_types': product_types})

@login_required
@require_http_methods(["POST"])
def add_type(request):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    
    name = request.POST.get('name', '').strip()
    if name:
        ProductType.objects.get_or_create(name=name)
    return redirect('catalogue:type_list')

@login_required
@require_http_methods(["POST", "DELETE"])
def delete_type(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
        
    product_type = get_object_or_404(ProductType, pk=pk)
    product_type.delete()
    return redirect('catalogue:type_list')

@login_required
@require_http_methods(["POST"])
def edit_type(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    
    product_type = get_object_or_404(ProductType, pk=pk)
    name = request.POST.get('name', '').strip()
    if name:
        product_type.name = name
        product_type.save()
    return redirect('catalogue:type_list')

@login_required
def pending_actions(request):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
        
    actions = PendingAction.objects.filter(status='pending').order_by('-submitted_at')
    return render(request, 'catalogue/pending_actions.html', {'actions': actions})

@login_required
@require_http_methods(["POST"])
def resolve_action(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
        
    action = get_object_or_404(PendingAction, pk=pk)
    resolution = request.POST.get('resolution') # 'approve' or 'reject'
    
    if resolution == 'approve':
        action.status = 'approved'
        # Apply stock changes
        product_id = action.details.get('product_id')
        variant_id = action.details.get('variant_id')
        qty_change = int(action.details.get('qty', 0))
        
        if variant_id:
            try:
                v = ProductVariant.objects.get(id=variant_id)
                v.stock_qty += qty_change
                v.save(update_fields=['stock_qty'])
            except ProductVariant.DoesNotExist:
                pass
        elif product_id:
            try:
                p = Product.objects.get(id=product_id)
                p.stock_qty += qty_change
                p.save(update_fields=['stock_qty'])
            except Product.DoesNotExist:
                pass
    else:
        action.status = 'rejected'
        action.rejection_reason = request.POST.get('reason', '')
        
    action.approved_by = request.user
    action.approved_at = timezone.now()
    action.save()
    
    return redirect('catalogue:pending_actions')
