import csv
import collections
from decimal import Decimal
from datetime import timedelta, datetime, date
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db.models import Sum, Count, Avg, F, Q, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncDate, ExtractWeekDay
from django.utils import timezone
from pos.models import Sale, SaleLineItem
from expenses.models import Expense
from catalogue.models import Product, Category, Batch
from procurement.models import PurchaseOrder, POLineItem, Supplier, GoodsReceiptItem, GoodsReceipt
from audit_module.models import Stocktake
from pos.models import CashHandover


def _get_date_range(request):
    """Parse date range from request params."""
    # Support both 'range' (new spec) and 'period' (old code)
    range_param = request.GET.get('range') or request.GET.get('period', 'today')
    today_dt = timezone.now()
    today = today_dt.date()

    start_date = None
    end_date = None

    if range_param == 'today':
        start_date = today_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif range_param == '7days':
        start_date = today_dt.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)
        end_date = today_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif range_param == '30days':
        start_date = today_dt.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=29)
        end_date = today_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif range_param == 'month':
        from calendar import monthrange
        start = today.replace(day=1)
        last_day = monthrange(today.year, today.month)[1]
        end = today.replace(day=last_day)
        start_date = timezone.make_aware(datetime.combine(start, datetime.min.time()))
        end_date = timezone.make_aware(datetime.combine(end, datetime.max.time()))
    elif request.GET.get('start') and request.GET.get('end'):
        try:
            start_val = datetime.strptime(request.GET['start'], '%Y-%m-%d').date()
            end_val = datetime.strptime(request.GET['end'], '%Y-%m-%d').date()
            start_date = timezone.make_aware(datetime.combine(start_val, datetime.min.time()))
            end_date = timezone.make_aware(datetime.combine(end_val, datetime.max.time()))
            range_param = 'custom'
        except (ValueError, TypeError):
            pass

    # Fallback to existing parameters
    if start_date is None or end_date is None:
        if request.GET.get('start_date') and request.GET.get('end_date'):
            try:
                start_val = datetime.strptime(request.GET['start_date'], '%Y-%m-%d').date()
                end_val = datetime.strptime(request.GET['end_date'], '%Y-%m-%d').date()
                start_date = timezone.make_aware(datetime.combine(start_val, datetime.min.time()))
                end_date = timezone.make_aware(datetime.combine(end_val, datetime.max.time()))
                range_param = 'custom'
            except (ValueError, TypeError):
                pass

    if start_date is None or end_date is None:
        # Default fallback: today
        start_date = today_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        range_param = 'today'

    return start_date, end_date, range_param


@login_required
def dashboard(request):
    if request.user.role not in ('admin', 'manager'):
        return render(request, 'reports/locked.html')

    start_date, end_date, period = _get_date_range(request)

    sales = Sale.objects.filter(created_at__range=(start_date, end_date), status='complete')
    expenses_qs = Expense.objects.filter(date__range=(start_date.date(), end_date.date()))

    # KPIs
    revenue = sales.aggregate(Sum('total'))['total__sum'] or Decimal('0')
    expenses = expenses_qs.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    tx_count = sales.count()
    avg_basket = float(revenue) / tx_count if tx_count > 0 else 0

    # Total purchases (cost of goods received in the period)
    purchases_total = GoodsReceiptItem.objects.filter(
        receipt__received_at__range=(start_date, end_date),
    ).aggregate(
        total=Sum(F('received_qty') * F('po_line__unit_cost'))
    )['total'] or Decimal('0')

    # COGS from sale line items
    cogs = Decimal('0')
    for li in SaleLineItem.objects.filter(sale__in=sales):
        if li.cost_price_at_sale:
            # Handle bundle-to-base conversion for COGS
            base_qty = li.quantity
            if li.sell_mode == 'bundle' and li.bundle_size_snapshot:
                base_qty = li.quantity * Decimal(str(li.bundle_size_snapshot))
            cogs += li.cost_price_at_sale * base_qty

    gross_profit = float(revenue) - float(cogs)
    net_profit = gross_profit - float(expenses)
    margin = (gross_profit / float(revenue) * 100) if revenue > 0 else 0

    # Payment breakdown
    payments = sales.values('payment_method').annotate(total=Sum('total'))
    payment_stats = {p['payment_method']: p['total'] for p in payments}

    # Top products
    top = SaleLineItem.objects.filter(
        sale__in=sales
    ).values('product__name').annotate(
        total_qty=Sum('quantity'),
        total_revenue=Sum('line_total'),
    ).order_by('-total_revenue')[:5]

    # Chart data
    chart_qs = sales.annotate(day=TruncDate('created_at')).values('day').annotate(
        daily_rev=Sum('total')
    ).order_by('day')
    rev_by_day = {str(d['day']): d['daily_rev'] for d in chart_qs}

    delta = (end_date.date() - start_date.date()).days
    if delta == 0:
        delta = 6
        plot_start = end_date.date() - timedelta(days=6)
    else:
        plot_start = start_date.date()

    chart_days = []
    for i in range(delta + 1):
        day = plot_start + timedelta(days=i)
        day_str = day.strftime('%Y-%m-%d')
        chart_days.append({
            'label': day.strftime('%a') if delta <= 14 else day.strftime('%d %b'),
            'value': float(rev_by_day.get(day_str, 0)),
            'is_today': day == end_date.date(),
        })

    max_chart_value = max([d['value'] for d in chart_days]) if chart_days else 1
    if max_chart_value == 0:
        max_chart_value = 1

    # Day-of-week
    dow_qs = sales.annotate(
        weekday=ExtractWeekDay('created_at')
    ).values('weekday').annotate(
        day_revenue=Sum('total'), day_count=Count('id')
    ).order_by('weekday')

    day_names = {2: 'Mon', 3: 'Tue', 4: 'Wed', 5: 'Thu', 6: 'Fri', 7: 'Sat', 1: 'Sun'}
    day_order = [2, 3, 4, 5, 6, 7, 1]
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

    # Low stock
    low_stock = Product.objects.filter(is_active=True).order_by('stock_qty')
    low_stock = [p for p in low_stock[:20] if p.is_low_stock]

    # Discount total
    total_discounts = float(sales.aggregate(Sum('discount_total'))['discount_total__sum'] or 0)

    context = {
        'period': period,
        'start_date_str': start_date.strftime('%Y-%m-%d'),
        'end_date_str': end_date.strftime('%Y-%m-%d'),
        'revenue': float(revenue),
        'cogs': float(cogs),
        'gross_profit': gross_profit,
        'expenses': float(expenses),
        'purchases': float(purchases_total),
        'net_profit': net_profit,
        'margin': margin,
        'avg_basket': avg_basket,
        'tx_count': tx_count,
        'payment_stats': payment_stats,
        'chart_days': chart_days,
        'max_chart_value': max_chart_value,
        'top_products': top,
        'low_stock': low_stock,
        'dow_chart': dow_chart,
        'max_dow_value': max_dow_value,
        'total_discounts': total_discounts,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'reports/partials/dashboard_body.html', context)
    return render(request, 'reports/dashboard.html', context)


@login_required
def sales_by_category(request):
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)

    start_date, end_date, period = _get_date_range(request)
    sales = Sale.objects.filter(created_at__range=(start_date, end_date), status='complete')

    data = SaleLineItem.objects.filter(
        sale__in=sales
    ).values(
        'product__subcategory__category__name'
    ).annotate(
        total_revenue=Sum('line_total'),
        total_qty=Sum('quantity'),
        item_count=Count('id'),
    ).order_by('-total_revenue')

    return render(request, 'reports/sales_by_category.html', {
        'data': data, 'period': period,
        'start_date_str': request.GET.get('start_date', ''),
        'end_date_str': request.GET.get('end_date', ''),
    })


@login_required
def product_performance(request):
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)

    start_date, end_date, period = _get_date_range(request)
    sales = Sale.objects.filter(created_at__range=(start_date, end_date), status='complete')

    sold_products = SaleLineItem.objects.filter(
        sale__in=sales
    ).values('product__name', 'product__id').annotate(
        total_qty=Sum('quantity'),
        total_revenue=Sum('line_total'),
    ).order_by('-total_revenue')

    # Total quantity and revenue
    total_qty_sold = sum(p['total_qty'] for p in sold_products) if sold_products else Decimal('0')
    total_revenue_sold = sum(p['total_revenue'] for p in sold_products) if sold_products else Decimal('0')
    avg_item_value = (total_revenue_sold / total_qty_sold) if total_qty_sold > 0 else Decimal('0')

    # Zero-sale items
    sold_ids = SaleLineItem.objects.filter(
        sale__in=sales,
    ).values_list('product_id', flat=True).distinct()
    zero_sale = Product.objects.filter(is_active=True).exclude(id__in=sold_ids)[:20]

    return render(request, 'reports/product_performance.html', {
        'sold_products': sold_products,
        'total_qty_sold': total_qty_sold,
        'total_revenue_sold': total_revenue_sold,
        'avg_item_value': avg_item_value,
        'zero_sale': zero_sale,
        'period': period,
        'start_date_str': start_date.strftime('%Y-%m-%d'),
        'end_date_str': end_date.strftime('%Y-%m-%d'),
    })




@login_required
def margin_report(request):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)

    products = Product.objects.filter(is_active=True).select_related(
        'subcategory__category'
    ).order_by('name')

    data = []
    for p in products:
        data.append({
            'product': p,
            'actual_margin': p.gross_margin_pct,
            'bundle_margin': p.bundle_margin_pct,
            'desired_margin': float(p.desired_margin_pct) if p.desired_margin_pct else None,
            'cost': float(p.cost_price) if p.cost_price else 0,
            'sell': float(p.base_unit_price),
            'bundle_sell': float(p.bundle_price) if p.bundle_pricing_enabled else None,
        })

    return render(request, 'reports/margin_report.html', {'data': data})


@login_required
def supplier_spend(request):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)

    start_date, end_date, period = _get_date_range(request)

    data = POLineItem.objects.filter(
        po__created_at__range=(start_date, end_date),
        po__status__in=['fully_received', 'partially_received'],
    ).values('po__supplier__name').annotate(
        total_spend=Sum(F('unit_cost') * F('received_qty')),
        item_count=Count('id'),
    ).order_by('-total_spend')

    return render(request, 'reports/supplier_spend.html', {
        'data': data, 'period': period,
        'start_date_str': request.GET.get('start_date', ''),
        'end_date_str': request.GET.get('end_date', ''),
    })


@login_required
def stock_valuation(request):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)

    products = Product.objects.filter(is_active=True).select_related(
        'subcategory__category'
    ).order_by('subcategory__category__name', 'name')

    total_cost_value = Decimal('0')
    total_retail_value = Decimal('0')
    data = []

    for p in products:
        stock = p.stock_in_weight_unit if p.weight_sell_enabled else p.stock_qty
        cost_val = stock * (p.cost_price or 0)
        retail_val = stock * p.base_unit_price
        
        # If product has bundle pricing, maybe show that potential? 
        # But base unit retail value is usually the standard valuation.
        
        total_cost_value += cost_val
        total_retail_value += retail_val
        data.append({
            'product': p,
            'stock': stock,
            'purchase_unit_equiv': (stock / p.units_per_purchase) if p.units_per_purchase > 1 else None,
            'cost_value': cost_val,
            'retail_value': retail_val,
        })

    return render(request, 'reports/stock_valuation.html', {
        'data': data,
        'total_cost_value': total_cost_value,
        'total_retail_value': total_retail_value,
    })


@login_required
def batch_expiry(request):
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)

    days = int(request.GET.get('days', 30))
    threshold = timezone.now().date() + timedelta(days=days)

    batches = Batch.objects.filter(
        status='active',
        expiry_date__lte=threshold,
    ).select_related('product').order_by('expiry_date')

    return render(request, 'reports/batch_expiry.html', {
        'batches': batches, 'days': days,
    })


@login_required
def po_history(request):
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)

    pos = PurchaseOrder.objects.all().select_related('supplier', 'created_by')
    return render(request, 'reports/po_history.html', {'pos': pos})


@login_required
def promotion_effectiveness(request):
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)

    start_date, end_date, period = _get_date_range(request)

    promo_lines = SaleLineItem.objects.filter(
        sale__created_at__range=(start_date, end_date),
        sale__status='complete',
        promotion__isnull=False,
    ).values('promotion__name').annotate(
        promo_qty=Sum('quantity'),
        promo_revenue=Sum('line_total'),
    ).order_by('-promo_revenue')

    return render(request, 'reports/promotion_effectiveness.html', {
        'promo_lines': promo_lines, 'period': period,
        'start_date_str': request.GET.get('start_date', ''),
        'end_date_str': request.GET.get('end_date', ''),
    })


@login_required
def stock_reconciliation(request):
    """Stock/Revenue reconciliation view — compares system revenue against
    cash handovers, M-Pesa, and in-shop expenses since the last stocktake."""
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)

    # Determine period: since last current stocktake, or fallback to 30 days
    current_stocktake = Stocktake.objects.filter(is_current=True).first()
    if current_stocktake:
        start_date = timezone.make_aware(
            datetime.combine(current_stocktake.conducted_date, datetime.min.time())
        )
        period_label = f"Since stocktake on {current_stocktake.conducted_date.strftime('%d %b %Y')}"
    else:
        start_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=29)
        period_label = "Last 30 days (no stocktake recorded)"

    end_date = timezone.now()

    # System revenue (completed sales)
    sales = Sale.objects.filter(created_at__range=(start_date, end_date), status='complete')
    system_revenue = sales.aggregate(total=Sum('total'))['total'] or Decimal('0')

    # Payment breakdown from sales
    system_cash = Decimal('0')
    system_mpesa = Decimal('0')
    for sale in sales:
        if sale.payment_method == 'cash':
            system_cash += sale.total
        elif sale.payment_method == 'mpesa':
            system_mpesa += sale.total
        elif sale.payment_method == 'split':
            system_cash += sale.cash_amount or Decimal('0')
            system_mpesa += sale.mpesa_amount or Decimal('0')

    # Cash handovers (confirmed)
    handovers = CashHandover.objects.filter(
        created_at__range=(start_date, end_date),
        status='confirmed',
    )
    total_handed_cash = handovers.aggregate(total=Sum('cash_amount'))['total'] or Decimal('0')
    total_handed_mpesa = handovers.aggregate(total=Sum('mpesa_amount'))['total'] or Decimal('0')
    total_in_shop_expenses = handovers.aggregate(total=Sum('in_shop_expenses'))['total'] or Decimal('0')
    total_ad_hoc_purchases = handovers.aggregate(total=Sum('ad_hoc_purchases'))['total'] or Decimal('0')

    # Accounted total = handed cash + handed mpesa + in-shop expenses + ad-hoc purchases
    accounted_total = total_handed_cash + total_handed_mpesa + total_in_shop_expenses + total_ad_hoc_purchases

    # Variance
    variance = accounted_total - system_revenue

    # Expenses from expense module
    expenses_total = Expense.objects.filter(
        date__range=(start_date.date(), end_date.date()),
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    # Purchases in the period
    purchases_total = GoodsReceiptItem.objects.filter(
        receipt__received_at__range=(start_date, end_date),
    ).aggregate(
        total=Sum(F('received_qty') * F('po_line__unit_cost'))
    )['total'] or Decimal('0')

    context = {
        'period_label': period_label,
        'start_date': start_date,
        'end_date': end_date,
        'current_stocktake': current_stocktake,
        'system_revenue': float(system_revenue),
        'system_cash': float(system_cash),
        'system_mpesa': float(system_mpesa),
        'total_handed_cash': float(total_handed_cash),
        'total_handed_mpesa': float(total_handed_mpesa),
        'total_in_shop_expenses': float(total_in_shop_expenses),
        'total_ad_hoc_purchases': float(total_ad_hoc_purchases),
        'accounted_total': float(accounted_total),
        'variance': float(variance),
        'expenses_total': float(expenses_total),
        'purchases_total': float(purchases_total),
        'handover_count': handovers.count(),
        'sales_count': sales.count(),
    }

    return render(request, 'reports/reconciliation.html', context)


# ── CSV Export ──

@login_required
def export_csv(request, report_type):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{report_type}.csv"'
    writer = csv.writer(response)

    if report_type == 'stock_valuation':
        writer.writerow(['Product', 'Category', 'Stock Qty', 'Cost Price', 'Sell Price', 'Cost Value', 'Retail Value'])
        for p in Product.objects.filter(is_active=True).select_related('subcategory__category'):
            stock = p.stock_in_weight_unit if p.weight_sell_enabled else p.stock_qty
            writer.writerow([
                p.name,
                p.subcategory.category.name,
                stock,
                p.cost_price or 0,
                p.base_unit_price,
                stock * (p.cost_price or 0),
                stock * p.base_unit_price,
            ])
    elif report_type == 'sales':
        start_date, end_date, _ = _get_date_range(request)
        writer.writerow(['Receipt', 'Date', 'Cashier', 'Total', 'Payment', 'Status'])
        for s in Sale.objects.filter(created_at__range=(start_date, end_date)):
            writer.writerow([
                s.receipt_number,
                s.created_at.strftime('%Y-%m-%d %H:%M'),
                s.cashier.name,
                s.total,
                s.get_payment_method_display(),
                s.get_status_display(),
            ])

    return response
