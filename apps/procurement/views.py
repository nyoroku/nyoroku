from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
import json
from .models import PurchaseOrder, Supplier

@login_required
def po_list(request):
    pos = PurchaseOrder.objects.all().order_by('-created_at')
    return render(request, 'procurement/po_list.html', {'pos': pos})

@login_required
def po_detail(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    return render(request, 'procurement/po_detail.html', {'po': po})

@login_required
def po_create(request):
    if request.method == 'POST':
        # Simple draft creation for MVP
        supplier_id = request.POST.get('supplier_id')
        supplier = get_object_or_404(Supplier, id=supplier_id)
        
        po = PurchaseOrder.objects.create(
            supplier=supplier,
            submitted_by=request.user,
            status='draft'
        )
        return redirect('procurement:po_detail', pk=po.id)
        
    suppliers = Supplier.objects.all()
    return render(request, 'procurement/po_create.html', {'suppliers': suppliers})

# --- SUPPLIERS ---

@login_required
def supplier_list(request):
    suppliers = Supplier.objects.all().order_by('name')
    return render(request, 'procurement/supplier_list.html', {'suppliers': suppliers})

@login_required
def supplier_create(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        phone = request.POST.get('phone', '')
        email = request.POST.get('email', '')
        address = request.POST.get('address', '')
        
        Supplier.objects.create(
            name=name,
            phone=phone,
            email=email,
            address=address
        )
    return redirect('procurement:supplier_list')

@login_required
def supplier_edit(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        supplier.name = request.POST.get('name')
        supplier.phone = request.POST.get('phone', '')
        supplier.email = request.POST.get('email', '')
        supplier.address = request.POST.get('address', '')
        supplier.save()
    return redirect('procurement:supplier_list')

# --- PO BUILDER (Dynamic) ---
from django.http import HttpResponse
from catalogue.models import Product, ProductVariant

@login_required
def product_search(request):
    query = request.GET.get('q', '')
    if len(query) < 2:
        return HttpResponse('')
    
    products = Product.objects.filter(name__icontains=query, approved=True)[:5]
    html = ""
    for p in products:
        has_variants = 'true' if p.has_variants else 'false'
        html += f"""
        <div class='flex items-center justify-between p-4 border-b border-white/[0.04] hover:bg-white/[0.02] cursor-pointer'
             @click='selectProduct({{ id: "{p.id}", name: "{p.name}", image: "{p.image}", cost_price: {p.cost_price or 0}, has_variants: {has_variants}}})'
             onclick='document.getElementById("search-results").innerHTML=""; document.getElementById("search-input").value=""'>
            <div class='flex items-center gap-3'>
                <span class='text-2xl'>{p.image}</span>
                <div>
                   <div class='font-bold text-white text-sm'>{p.name}</div>
                   <div class='text-[10px] text-text-muted font-bold uppercase'>{'Has Variants' if p.has_variants else 'Standard'}</div>
                </div>
            </div>
            <button type='button'
                    class='px-4 py-2 bg-brand-whatsapp/10 text-brand-whatsapp text-[10px] font-bold uppercase tracking-widest rounded-xl hover:bg-brand-whatsapp hover:text-white transition-all'>
                Select
            </button>
        </div>
        """
    return HttpResponse(html)

@login_required
def get_product_variants(request, pk):
    product = get_object_or_404(Product, pk=pk)
    variants = product.variants.all()
    vs = []
    for v in variants:
        vs.append({
            'id': str(v.id),
            'name': v.name,
            'cost_price': float(v.get_cost_price or 0),
            'stock_qty': v.stock_qty
        })
    import json
    return HttpResponse(json.dumps(vs), content_type="application/json")

@login_required
def po_add_item(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == 'POST' and po.status == 'draft':
        product_id = request.POST.get('product_id')
        variant_id = request.POST.get('variant_id')
        product = get_object_or_404(Product, id=product_id)
        qty = int(request.POST.get('qty', 1))
        
        # If variant_id is provided, get variant name for the line item
        v_name = ""
        if variant_id:
            v = get_object_or_404(ProductVariant, id=variant_id, product=product)
            v_name = f" ({v.name})"
            
        unit_cost = float(request.POST.get('unit_cost') or product.cost_price or 0)
        
        items = list(po.items)
        items.append({
            'product_id': str(product.id),
            'variant_id': variant_id,
            'name': f"{product.name}{v_name}",
            'qty': qty,
            'unit_cost': unit_cost,
            'total_cost': round(qty * unit_cost, 2)
        })
        po.items = items
        po.save()
    return redirect('procurement:po_detail', pk=po.id)

@login_required
def po_remove_item(request, pk, index):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status == 'draft':
        items = list(po.items)
        if 0 <= index < len(items):
            items.pop(index)
            po.items = items
            po.save()
    return redirect('procurement:po_detail', pk=po.id)

@login_required
def po_update_qty(request, pk, index):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == 'POST' and po.status == 'draft':
        qty = int(request.POST.get('qty', 1))
        items = list(po.items)
        if 0 <= index < len(items):
            items[index]['qty'] = qty
            items[index]['total_cost'] = round(qty * items[index]['unit_cost'], 2)
            po.items = items
            po.save()
    return redirect('procurement:po_detail', pk=po.id)

# --- PO WORKFLOW ---
from django.db import transaction
from .models import GoodsReceivingNote

@login_required
def po_submit(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status == 'draft' and po.items:
        po.status = 'pending'
        po.save()
        po.log_trail(request.user, "Submitted For Approval")
    return redirect('procurement:po_detail', pk=po.id)

@login_required
def po_approve(request, pk):
    # Basic role check - assuming 'admin' role exists or we check is_staff
    if not request.user.is_staff and getattr(request.user, 'role', '') != 'admin':
        return redirect('procurement:po_detail', pk=pk)
        
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status == 'pending':
        po.status = 'approved'
        po.approved_by = request.user
        po.save()
        po.log_trail(request.user, "Order Approved")
    return redirect('procurement:po_detail', pk=po.id)

@login_required
@transaction.atomic
def po_receive(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status == 'approved':
        # Cycle through items and update stock
        for item in po.items:
            qty = int(item['qty'])
            unit_cost = float(item['unit_cost'])
            
            variant_id = item.get('variant_id')
            if variant_id:
                try:
                    v = ProductVariant.objects.get(id=variant_id)
                    v.stock_qty += qty
                    v.cost_price = unit_cost
                    v.save()
                    # Also update parent cost price if shared
                    v.product.cost_price = unit_cost
                    v.product.save()
                except ProductVariant.DoesNotExist:
                    pass
            else:
                try:
                    product = Product.objects.get(id=item['product_id'])
                    product.stock_qty += qty
                    product.cost_price = unit_cost
                    product.save()
                except Product.DoesNotExist:
                    continue
                
        # Finalize PO status
        po.status = 'received'
        po.save()
        
        # Create Trail
        po.log_trail(request.user, "Goods Received", f"Items added to inventory by {request.user.name}")

        # Create Audit GRN
        GoodsReceivingNote.objects.create(
            po=po,
            received_items=po.items,
            received_by=request.user
        )
        
    return redirect('procurement:po_detail', pk=po.id)

@login_required
@transaction.atomic
def quick_stock_add(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        supplier_id = request.POST.get('supplier_id')
        qty = int(request.POST.get('qty', 0))
        unit_cost = float(request.POST.get('unit_cost', 0))
        
        product = get_object_or_404(Product, id=product_id)
        supplier = get_object_or_404(Supplier, id=supplier_id)
        
        is_admin = request.user.is_staff or getattr(request.user, 'role', '') == 'admin'
        
        # Create PO
        po = PurchaseOrder.objects.create(
            supplier=supplier,
            submitted_by=request.user,
            items=[{
                'product_id': str(product.id),
                'name': product.name,
                'qty': qty,
                'unit_cost': unit_cost,
                'total_cost': round(qty * unit_cost, 2)
            }]
        )
        
        if is_admin:
            po.status = 'received'
            po.approved_by = request.user
            po.save()
            
            # Update Stock
            product.stock_qty += qty
            product.cost_price = unit_cost
            product.save()
            
            po.log_trail(request.user, "Quick Stock Add (Completed)", f"Added {qty} units of {product.name}. Inventory updated directly.")
            
            # Create GRN
            GoodsReceivingNote.objects.create(
                po=po,
                received_items=po.items,
                received_by=request.user
            )
            
            return redirect('procurement:po_list')
        else:
            po.status = 'pending'
            po.save()
            po.log_trail(request.user, "Quick Stock Add (Submitted)", f"Added {qty} units of {product.name}. Pending admin approval.")
            return redirect('procurement:po_list')

    products = Product.objects.filter(approved=True).order_by('name')
    suppliers = Supplier.objects.all().order_by('name')
    return render(request, 'procurement/quick_stock_add.html', {
        'products': products,
        'suppliers': suppliers
    })

@login_required
@transaction.atomic
def buy_stock(request):
    if request.method == 'POST':
        supplier_id = request.POST.get('supplier_id')
        items_json = request.POST.get('items_json')
        
        supplier = get_object_or_404(Supplier, id=supplier_id)
        items = json.loads(items_json) if items_json else []
        
        po = PurchaseOrder.objects.create(
            supplier=supplier,
            submitted_by=request.user,
            status='draft',
            items=items
        )
        
        is_admin = request.user.is_staff or getattr(request.user, 'role', '') == 'admin'
        if is_admin:
            # Immediate approval and receipt
            po.status = 'approved'
            po.approved_by = request.user
            po.save()
            po.log_trail(request.user, "Immediate Purchase Completed")
            return po_receive(request, po.id)
        else:
            po.status = 'pending'
            po.save()
            po.log_trail(request.user, "Order Submitted for Approval")
            return redirect('procurement:po_list')

    suppliers = Supplier.objects.all().order_by('name')
    products = Product.objects.filter(approved=True).order_by('name')
    return render(request, 'procurement/buy_stock.html', {
        'suppliers': suppliers,
        'products': products
    })

@login_required
@transaction.atomic
def quick_approve(request, pk):
    if not request.user.is_staff and getattr(request.user, 'role', '') != 'admin':
        return redirect('procurement:po_list')
        
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status == 'pending':
        po.status = 'approved'
        po.approved_by = request.user
        po.save()
        po.log_trail(request.user, "One-Tap Approval")
        return po_receive(request, po.id)
    return redirect('procurement:po_list')
