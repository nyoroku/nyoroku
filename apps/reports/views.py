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
    
    # 2. Fetch all products and variants in bulk to avoid N+1 queries
    products_map = Product.objects.in_bulk(list(product_ids))
    variants_map = ProductVariant.objects.in_bulk(list(product_ids))
    
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
                p_obj = products_map.get(pid) or variants_map.get(pid)
                if p_obj:
                    cost = float(p_obj.get_cost_price) if hasattr(p_obj, 'get_cost_price') else float(p_obj.cost_price or 0)
                    cogs += cost * qty

    top_products = sorted(product_totals.values(), key=lambda x: x['revenue'], reverse=True)[:5]
    
    gross_profit = float(revenue) - cogs
    net_profit = gross_profit - float(expenses)
    tx_count = txs.count()
    avg_basket = float(revenue) / tx_count if tx_count > 0 else 0
    margin = (gross_profit / float(revenue) * 100) if revenue > 0 else 0
    
    # Payment breakdown
    payments = txs.values('payment_method').annotate(total=Sum('total'))
    payment_stats = { p['payment_method']: p['total'] for p in payments }

    # Discount and Tip totals
    total_discounts = float(txs.aggregate(Sum('discount'))['discount__sum'] or 0)
    total_tips = float(txs.aggregate(Sum('tip_total'))['tip_total__sum'] or 0)
    
    # Dynamic Chart Data (Days in Period)
    chart_days = []
    
    from django.db.models.functions import TruncDate
    chart_qs = Transaction.objects.filter(
        created_at__range=(start_date, end_date),
        status='complete'
    ).annotate(day=TruncDate('created_at')).values('day').annotate(daily_rev=Sum('total')).order_by('day')
    
    rev_by_day = {str(d['day']): d['daily_rev'] for d in chart_qs}
    
    # Determine how many days to plot based on the period
    delta = (end_date.date() - start_date.date()).days
    if delta == 0:
        delta = 6 # Default to 7 bars (last 7 days including today) if only today is selected
        plot_start = end_date.date() - timedelta(days=6)
    else:
        plot_start = start_date.date()

    for i in range(delta + 1):
        day = plot_start + timedelta(days=i)
        day_str = day.strftime('%Y-%m-%d')
        chart_days.append({
            'label': day.strftime('%a') if delta <= 14 else day.strftime('%d %b'),
            'value': float(rev_by_day.get(day_str, 0)),
            'is_today': day == end_date.date()
        })

    # Low Stock Alerts
    low_stock_products = Product.objects.filter(approved=True, has_variants=False, stock_qty__lte=F('reorder_level'), stock_qty__gt=0)
    low_stock_variants = ProductVariant.objects.filter(stock_qty__lte=F('reorder_level'), stock_qty__gt=0).select_related('product')

    # Day-of-Week Sales Analysis
    from django.db.models.functions import ExtractWeekDay
    dow_qs = Transaction.objects.filter(
        created_at__range=(start_date, end_date),
        status='complete'
    ).annotate(
        weekday=ExtractWeekDay('created_at')
    ).values('weekday').annotate(
        day_revenue=Sum('total'),
        day_count=Count('id')
    ).order_by('weekday')

    # Django ExtractWeekDay: Sunday=1, Monday=2, ..., Saturday=7
    day_names = {2: 'Mon', 3: 'Tue', 4: 'Wed', 5: 'Thu', 6: 'Fri', 7: 'Sat', 1: 'Sun'}
    day_order = [2, 3, 4, 5, 6, 7, 1]  # Mon to Sun

    dow_data_map = {d['weekday']: d for d in dow_qs}
    dow_chart = []
    for wd in day_order:
        d = dow_data_map.get(wd, {})
        dow_chart.append({
            'label': day_names[wd],
            'revenue': float(d.get('day_revenue', 0) or 0),
            'count': d.get('day_count', 0),
        })

    max_dow_value = max([d['revenue'] for d in dow_chart]) if dow_chart else 1
    if max_dow_value == 0:
        max_dow_value = 1

    max_chart_value = max([d['value'] for d in chart_days]) if chart_days else 1
    if max_chart_value == 0:
        max_chart_value = 1

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
        'max_chart_value': max_chart_value,
        'top_products': top_products,
        'low_stock_products': low_stock_products,
        'low_stock_variants': low_stock_variants,
        'dow_chart': dow_chart,
        'max_dow_value': max_dow_value,
        'total_discounts': total_discounts,
        'total_tips': total_tips,
    }
    
    if request.headers.get('HX-Request'):
        return render(request, 'reports/partials/dashboard_body.html', context)
        
    return render(request, 'reports/dashboard.html', context)
