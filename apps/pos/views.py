import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from catalogue.models import Product, Category
from .models import Transaction

@login_required
def index(request):
    # Only approved products
    products = Product.objects.filter(approved=True).order_by('name')
    categories = Category.objects.all()
    
    context = {
        'products': products,
        'categories': categories,
    }
    
    if request.headers.get('HX-Request'):
        return render(request, 'pos/partials/product_grid.html', context)
        
    return render(request, 'pos/index.html', context)

@login_required
@require_http_methods(["POST"])
def checkout(request):
    try:
        data = json.loads(request.body)
        items = data.get('items', [])
        payment_method = data.get('payment_method', 'cash')
        
        if not items:
            return HttpResponse('Empty cart', status=400)
            
        subtotal = sum(Decimal(str(item['price'])) * int(item['qty']) for item in items)
        total = subtotal # Handle discounts/tips here if needed
        
        # Create Transaction
        transaction = Transaction.objects.create(
            cashier=request.user,
            items=items,
            subtotal=subtotal,
            total=total,
            payment_method=payment_method,
            status='complete'
        )
        
        # Deduct stock
        for item in items:
            try:
                product = Product.objects.get(id=item['id'])
                product.stock_qty = max(0, product.stock_qty - int(item['qty']))
                product.save()
            except Product.DoesNotExist:
                pass
                
        return render(request, 'pos/partials/receipt_modal.html', {'transaction': transaction})
        
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        return HttpResponse(f'Error processing checkout: {str(e)}', status=400)

@login_required
def receipt_print(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk)
    return render(request, 'pos/receipt_print.html', {'transaction': transaction})
