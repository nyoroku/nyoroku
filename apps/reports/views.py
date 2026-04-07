from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Avg, F
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
from pos.models import Transaction
from expenses.models import Expense
from catalogue.models import Product, ProductVariant
import collections

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
    elif period == 'custom':
        start_str = request.GET.get('start_date')
        end_str = request.GET.get('end_date')
        try:
            start_date = timezone.make_aware(datetime.strptime(start_str, '%Y-%m-%d'))
            # End date should be inclusive of the day
            end_date = timezone.make_aware(datetime.strptime(end_str, '%Y-%m-%d')).replace(hour=23, minute=59, second=59)
        except (ValueError, TypeError):
            start_date = end_date - timedelta(days=30)
            period = '30days'
    else: # today
        start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)

    # Transactions in period
    txs = Transaction.objects.filter(created_at__range=(start_date, end_date), status='complete')
    exps = Expense.objects.filter(date__range=(start_date.date(), end_date.date()))
    
    # KPIs
    revenue = txs.aggregate(Sum('total'))['total__sum'] or Decimal('0')
    expenses = exps.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    
    # Optimize COGS and Top Products
    # 1. Collect all product IDs seen across all transactions
    product_ids = set()
    for tx in txs:
        for item in (tx.items or []):
            if isinstance(item, dict) and 'id' in item:
                product_ids.add(item['id'])
    
    # 2. Fetch all products in bulk to avoid N+1 queries
    products_map = Product.objects.in_bulk(list(product_ids))
    
    cogs = 0.0
    product_totals = collections.defaultdict(lambda: {'name': 'Unknown', 'qty': 0, 'revenue': 0})
    
    for tx in txs:
        items = tx.items or []
        for item in items:
            if not isinstance(item, dict): continue
            
            pid = item.get('id')
            qty = int(item.get('qty', 0))
            price = float(item.get('price', 0))
            rev = price * qty
            
            # Top products tracking
            p_stats = product_totals[pid]
            if p_stats['name'] == 'Unknown':
                p_stats['name'] = item.get('name', f"Product #{pid}")
            p_stats['qty'] += qty
            p_stats['revenue'] += rev
            
            # COGS calculation
            if 'cost_price' in item and item['cost_price'] is not None:
                cogs += float(item['cost_price']) * qty
            else:
                p_obj = products_map.get(pid)
                if p_obj:
                    cogs += float(p_obj.cost_price or 0) * qty

    top_products = sorted(product_totals.values(), key=lambda x: x['revenue'], reverse=True)[:5]
    
    gross_profit = float(revenue) - cogs
    net_profit = gross_profit - float(expenses)
    tx_count = txs.count()
    avg_basket = float(revenue) / tx_count if tx_count > 0 else 0
    margin = (gross_profit / float(revenue) * 100) if revenue > 0 else 0
    
    # Payment breakdown
    payments = txs.values('payment_method').annotate(total=Sum('total'))
    payment_stats = { p['payment_method']: p['total'] for p in payments }
    
    # 7-day chart data
    chart_days = []
    # Optimization: One query for all 7 days might be better, but let's keep it simple for now or fetch in bulk.
    # Actually, let's group by date in one query.
    chart_qs = Transaction.objects.filter(
        created_at__gte=end_date - timedelta(days=7),
        status='complete'
    ).extra({'day': 'date(created_at)'}).values('day').annotate(daily_rev=Sum('total')).order_by('day')
    
    rev_by_day = {str(d['day']): d['daily_rev'] for d in chart_qs}
    
    for i in range(6, -1, -1):
        day = end_date - timedelta(days=i)
        day_str = day.strftime('%Y-%m-%d')
        chart_days.append({
            'label': day.strftime('%a'),
            'value': float(rev_by_day.get(day_str, 0)),
            'is_today': i == 0
        })

    # Low Stock Alerts
    low_stock_products = Product.objects.filter(approved=True, has_variants=False, stock_qty__lte=F('reorder_level'), stock_qty__gt=0)
    low_stock_variants = ProductVariant.objects.filter(stock_qty__lte=F('reorder_level'), stock_qty__gt=0).select_related('product')

    context = {
        'period': period,
        'start_date_str': request.GET.get('start_date', ''),
        'end_date_str': request.GET.get('end_date', ''),
        'revenue': float(revenue),
        'cogs': cogs,
        'gross_profit': gross_profit,
        'expenses': float(expenses),
        'net_profit': net_profit,
        'margin': margin,
        'avg_basket': avg_basket,
        'tx_count': tx_count,
        'payment_stats': payment_stats,
        'chart_days': chart_days,
        'top_products': top_products,
        'low_stock_products': low_stock_products,
        'low_stock_variants': low_stock_variants,
    }
    
    if request.headers.get('HX-Request'):
        return render(request, 'reports/partials/dashboard_body.html', context)
        
    return render(request, 'reports/dashboard.html', context)
