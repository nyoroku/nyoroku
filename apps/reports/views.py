from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Avg, F
from django.utils import timezone
from datetime import timedelta
from pos.models import Transaction
from expenses.models import Expense
from catalogue.models import Product

@login_required
def dashboard(request):
    if request.user.role != 'admin':
        return render(request, 'reports/locked.html')
        
    period = request.GET.get('period', 'today')
    end_date = timezone.now()
    
    if period == '7days':
        start_date = end_date - timedelta(days=7)
    elif period == '30days':
        start_date = end_date - timedelta(days=30)
    else: # today
        start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)

    # Transactions in period
    txs = Transaction.objects.filter(created_at__range=(start_date, end_date), status='complete')
    exps = Expense.objects.filter(date__range=(start_date.date(), end_date.date()))
    
    # KPIs
    revenue = txs.aggregate(Sum('total'))['total__sum'] or 0
    expenses = exps.aggregate(Sum('amount'))['amount__sum'] or 0
    net_profit = revenue - expenses
    tx_count = txs.count()
    avg_basket = revenue / tx_count if tx_count > 0 else 0
    
    # Margin %
    margin = (net_profit / revenue * 100) if revenue > 0 else 0
    
    # Payment breakdown
    payments = txs.values('payment_method').annotate(total=Sum('total'))
    payment_stats = { p['payment_method']: p['total'] for p in payments }
    
    # 7-day chart data
    chart_days = []
    for i in range(6, -1, -1):
        day = end_date - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        day_rev = Transaction.objects.filter(created_at__range=(day_start, day_end), status='complete').aggregate(Sum('total'))['total__sum'] or 0
        chart_days.append({
            'label': day.strftime('%a'),
            'value': float(day_rev),
            'is_today': i == 0
        })

    # Top products (simplified since items are JSON)
    # In a real app we'd query a line item model, but here let's aggregate from JSON if possible 
    # or just show a placeholder for MVP if JSON aggregation is too complex for SQLite shell.
    # We can do it in Python.
    product_totals = {}
    for tx in txs:
        for item in tx.items:
            pid = item['id']
            qty = int(item['qty'])
            rev = float(item['price']) * qty
            if pid not in product_totals:
                product_totals[pid] = {'name': item['name'], 'qty': 0, 'revenue': 0}
            product_totals[pid]['qty'] += qty
            product_totals[pid]['revenue'] += rev
            
    top_products = sorted(product_totals.values(), key=lambda x: x['revenue'], reverse=True)[:5]

    context = {
        'period': period,
        'revenue': revenue,
        'expenses': expenses,
        'net_profit': net_profit,
        'margin': margin,
        'avg_basket': avg_basket,
        'tx_count': tx_count,
        'payment_stats': payment_stats,
        'chart_days': chart_days,
        'top_products': top_products,
    }
    
    if request.headers.get('HX-Request'):
        return render(request, 'reports/partials/dashboard_body.html', context)
        
    return render(request, 'reports/dashboard.html', context)
