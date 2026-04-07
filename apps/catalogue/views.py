from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .models import Product, Category, PendingAction, ProductVariant

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
    categories = Category.objects.all()
    
    context = {
        'products': products,
        'categories': categories,
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
    category_id = request.POST.get('category')
    price = request.POST.get('price')
    cost_price = request.POST.get('cost_price')
    stock_qty = request.POST.get('stock_qty')
    barcode = request.POST.get('barcode', '')
    image = request.POST.get('image', '📦')

    category = get_object_or_404(Category, id=category_id)
    
    # Logic: Admin auto-approves, Cashier pending
    is_approved = (request.user.role == 'admin')
    
    product = Product.objects.create(
        name=name,
        category=category,
        price=price,
        cost_price=cost_price or None,
        stock_qty=stock_qty or 0,
        barcode=barcode,
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
        try:
            variants = json.loads(variants_json)
            for v in variants:
                ProductVariant.objects.create(
                    product=product,
                    options=v.get('options', {}),
                    price_override=v.get('price', price),
                    cost_price=v.get('cost_price') or None,
                    barcode=v.get('barcode', ''),
                    stock_qty=v.get('stock_qty', 0),
                    reorder_level=v.get('reorder_level', 5)
                )
            if variants:
                product.has_variants = True
                product.save()
        except json.JSONDecodeError:
            pass
    
    return redirect('catalogue:inventory')

@login_required
@require_http_methods(["POST"])
def edit_product(request):
    product_id = request.POST.get('id')
    product = get_object_or_404(Product, id=product_id)
    
    product.name = request.POST.get('name')
    product.category_id = request.POST.get('category')
    product.price = request.POST.get('price')
    cost_price = request.POST.get('cost_price')
    product.cost_price = cost_price if cost_price else None
    product.barcode = request.POST.get('barcode', '')
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
        try:
            variants = json.loads(variants_json)
            # Remove existing variants not in the new list (if they have IDs)
            keep_ids = [v.get('id') for v in variants if v.get('id')]
            product.variants.exclude(id__in=keep_ids).delete()
            
            for v in variants:
                if v.get('id'):
                    variant_obj = ProductVariant.objects.filter(id=v['id'], product=product).first()
                    if variant_obj:
                        variant_obj.options = v.get('options', {})
                        variant_obj.price_override = v.get('price', product.price)
                        variant_obj.cost_price = v.get('cost_price') or None
                        variant_obj.barcode = v.get('barcode', '')
                        variant_obj.stock_qty = v.get('stock_qty', 0)
                        variant_obj.reorder_level = v.get('reorder_level', 5)
                        variant_obj.save()
                else:
                    ProductVariant.objects.create(
                        product=product,
                        options=v.get('options', {}),
                        price_override=v.get('price', product.price),
                        cost_price=v.get('cost_price') or None,
                        barcode=v.get('barcode', ''),
                        stock_qty=v.get('stock_qty', 0),
                        reorder_level=v.get('reorder_level', 5)
                    )
            product.has_variants = bool(variants)
            product.save()
        except json.JSONDecodeError:
            pass
            
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
def category_list(request):
    if request.user.role != 'admin':
        return redirect('catalogue:inventory')
    
    categories = Category.objects.all().order_by('name')
    return render(request, 'catalogue/category_list.html', {'categories': categories})

@login_required
@require_http_methods(["POST"])
def add_category(request):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
    
    name = request.POST.get('name')
    if name:
        Category.objects.get_or_create(name=name)
    return redirect('catalogue:category_list')

@login_required
@require_http_methods(["POST", "DELETE"])
def delete_category(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
        
    category = get_object_or_404(Category, pk=pk)
    category.delete()
    return redirect('catalogue:category_list')

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
