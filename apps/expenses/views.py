from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .models import Expense
from django.db.models import Sum

@login_required
def expense_list(request):
    expenses = Expense.objects.all().order_by('-date', '-created_at')
    
    # Category breakdown
    breakdown = Expense.objects.values('category').annotate(total=Sum('amount'))
    total_expenses = Expense.objects.aggregate(Sum('amount'))['amount__sum'] or 0
    
    context = {
        'expenses': expenses,
        'breakdown': breakdown,
        'total_expenses': total_expenses,
        'categories': Expense.CATEGORY_CHOICES,
    }
    
    return render(request, 'expenses/list.html', context)

@login_required
@require_http_methods(["POST"])
def add_expense(request):
    name = request.POST.get('name')
    category = request.POST.get('category')
    amount = request.POST.get('amount')
    note = request.POST.get('note')
    date = request.POST.get('date')
    
    Expense.objects.create(
        name=name,
        category=category,
        amount=amount,
        note=note,
        date=date or timezone.now().date(),
        recorded_by=request.user
    )
    
    return redirect('expenses:list')

@login_required
@require_http_methods(["DELETE", "POST"])
def delete_expense(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
        
    expense = get_object_or_404(Expense, pk=pk)
    expense.delete()
    
    if request.headers.get('HX-Request'):
        return HttpResponse('')
        
    return redirect('expenses:list')

@login_required
@require_http_methods(["POST"])
def edit_expense(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    
    expense.name = request.POST.get('name')
    expense.category = request.POST.get('category')
    expense.amount = request.POST.get('amount')
    expense.note = request.POST.get('note')
    date_val = request.POST.get('date')
    if date_val:
        expense.date = date_val
        
    expense.save()
    
    return redirect('expenses:list')
