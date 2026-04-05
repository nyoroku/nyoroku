from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
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
