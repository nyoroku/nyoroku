from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from decimal import Decimal
from .models import Promotion, Hamper, HamperComponent
from catalogue.models import Product, Category
from core.models import log_audit


@login_required
def promotion_list(request):
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)
    promos = Promotion.objects.all().select_related('product', 'category')
    now = timezone.now()
    active_count = promos.filter(is_active=True, start_date__lte=now, end_date__gte=now).count()
    return render(request, 'promotions/list.html', {
        'promos': promos,
        'active_count': active_count,
    })


@login_required
@require_http_methods(["GET", "POST"])
def promotion_create(request):
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)

    if request.method == 'POST':
        promo_type = request.POST.get('promo_type')
        product_id = request.POST.get('product_id') or None
        category_id = request.POST.get('category_id') or None

        # Check for conflicts
        if product_id:
            existing = Promotion.objects.filter(
                product_id=product_id, is_active=True,
                end_date__gte=timezone.now(),
            ).first()
            if existing:
                return HttpResponse(
                    f'Conflict: {existing.name} is already active on this product',
                    status=400,
                )

        promo = Promotion.objects.create(
            name=request.POST.get('name', ''),
            promo_type=promo_type,
            product_id=product_id,
            category_id=category_id,
            buy_qty=_int_or_none(request.POST.get('buy_qty')),
            free_qty=_int_or_none(request.POST.get('free_qty')),
            deal_qty=_int_or_none(request.POST.get('deal_qty')),
            deal_price=_dec_or_none(request.POST.get('deal_price')),
            discount_pct=_dec_or_none(request.POST.get('discount_pct')),
            discount_amount=_dec_or_none(request.POST.get('discount_amount')),
            start_date=request.POST.get('start_date'),
            end_date=request.POST.get('end_date'),
            is_active=True,
            created_by=request.user,
        )

        log_audit(
            action='promotion_changed',
            user=request.user,
            entity_type='Promotion',
            entity_id=str(promo.pk),
            description=f'Created promotion: {promo.name}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        return redirect('promotions:list')

    products = Product.objects.filter(is_active=True).order_by('name')
    categories = Category.objects.all().order_by('name')
    return render(request, 'promotions/create.html', {
        'products': products,
        'categories': categories,
        'promo_types': Promotion.PROMO_TYPE_CHOICES,
    })


@login_required
@require_http_methods(["GET", "POST"])
def promotion_edit(request, pk):
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)
    promo = get_object_or_404(Promotion, pk=pk)

    if request.method == 'POST':
        promo.name = request.POST.get('name', promo.name)
        promo.promo_type = request.POST.get('promo_type', promo.promo_type)
        promo.buy_qty = _int_or_none(request.POST.get('buy_qty'))
        promo.free_qty = _int_or_none(request.POST.get('free_qty'))
        promo.deal_qty = _int_or_none(request.POST.get('deal_qty'))
        promo.deal_price = _dec_or_none(request.POST.get('deal_price'))
        promo.discount_pct = _dec_or_none(request.POST.get('discount_pct'))
        promo.discount_amount = _dec_or_none(request.POST.get('discount_amount'))
        promo.start_date = request.POST.get('start_date', promo.start_date)
        promo.end_date = request.POST.get('end_date', promo.end_date)
        promo.save()

        log_audit(
            action='promotion_changed',
            user=request.user,
            entity_type='Promotion',
            entity_id=str(promo.pk),
            description=f'Updated promotion: {promo.name}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        return redirect('promotions:list')

    products = Product.objects.filter(is_active=True).order_by('name')
    categories = Category.objects.all().order_by('name')
    return render(request, 'promotions/edit.html', {
        'promo': promo,
        'products': products,
        'categories': categories,
        'promo_types': Promotion.PROMO_TYPE_CHOICES,
    })


@login_required
@require_http_methods(["POST"])
def promotion_toggle(request, pk):
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)
    promo = get_object_or_404(Promotion, pk=pk)
    promo.is_active = not promo.is_active
    promo.save()
    return redirect('promotions:list')


@login_required
@require_http_methods(["POST", "DELETE"])
def promotion_delete(request, pk):
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)
    promo = get_object_or_404(Promotion, pk=pk)
    log_audit(
        action='promotion_changed',
        user=request.user,
        entity_type='Promotion',
        entity_id=str(promo.pk),
        description=f'Deleted promotion: {promo.name}',
        ip_address=request.META.get('REMOTE_ADDR'),
    )
    promo.delete()
    return redirect('promotions:list')


# ── Hampers ──

@login_required
def hamper_list(request):
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)
    hampers = Hamper.objects.all().prefetch_related('components', 'components__product')
    return render(request, 'promotions/hamper_list.html', {'hampers': hampers})


@login_required
@require_http_methods(["GET", "POST"])
def hamper_create(request):
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)

    if request.method == 'POST':
        import json
        hamper = Hamper.objects.create(
            name=request.POST.get('name', ''),
            sku=request.POST.get('sku', ''),
            image=request.POST.get('image', '🎁'),
            price=Decimal(request.POST.get('price', '0')),
            created_by=request.user,
        )

        components_json = request.POST.get('components_json', '[]')
        try:
            components = json.loads(components_json)
            for comp in components:
                HamperComponent.objects.create(
                    hamper=hamper,
                    product_id=comp['product_id'],
                    quantity=Decimal(str(comp.get('quantity', 1))),
                    use_split=comp.get('use_split', False),
                )
        except (json.JSONDecodeError, KeyError):
            pass

        log_audit(
            action='hamper_changed',
            user=request.user,
            entity_type='Hamper',
            entity_id=str(hamper.pk),
            description=f'Created hamper: {hamper.name}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        return redirect('promotions:hamper_list')

    products = Product.objects.filter(is_active=True).order_by('name')
    return render(request, 'promotions/hamper_create.html', {'products': products})


@login_required
@require_http_methods(["GET", "POST"])
def hamper_edit(request, pk):
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)

    hamper = get_object_or_404(Hamper, pk=pk)

    if request.method == 'POST':
        import json
        hamper.name = request.POST.get('name', hamper.name)
        hamper.sku = request.POST.get('sku', hamper.sku)
        hamper.image = request.POST.get('image', hamper.image)
        hamper.price = Decimal(request.POST.get('price', str(hamper.price)))
        hamper.save()

        components_json = request.POST.get('components_json', '')
        if components_json:
            hamper.components.all().delete()
            try:
                components = json.loads(components_json)
                for comp in components:
                    HamperComponent.objects.create(
                        hamper=hamper,
                        product_id=comp['product_id'],
                        quantity=Decimal(str(comp.get('quantity', 1))),
                        use_split=comp.get('use_split', False),
                    )
            except (json.JSONDecodeError, KeyError):
                pass

        log_audit(
            action='hamper_changed',
            user=request.user,
            entity_type='Hamper',
            entity_id=str(hamper.pk),
            description=f'Updated hamper: {hamper.name}',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        return redirect('promotions:hamper_list')

    products = Product.objects.filter(is_active=True).order_by('name')
    return render(request, 'promotions/hamper_edit.html', {
        'hamper': hamper,
        'products': products,
    })


@login_required
@require_http_methods(["POST", "DELETE"])
def hamper_delete(request, pk):
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)
    hamper = get_object_or_404(Hamper, pk=pk)
    hamper.delete()
    return redirect('promotions:hamper_list')


def _int_or_none(val):
    try:
        return int(val) if val else None
    except (ValueError, TypeError):
        return None

def _dec_or_none(val):
    try:
        return Decimal(val) if val else None
    except Exception:
        return None
