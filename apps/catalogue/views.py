from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from .models import Product, Category

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
