import csv
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from .models import AuditTrail
from accounts.models import User


@login_required
def audit_trail_list(request):
    if request.user.role not in ('admin', 'manager'):
        return HttpResponse('Unauthorized', status=403)

    entries = AuditTrail.objects.all()

    # Filters
    action = request.GET.get('action', '')
    user_id = request.GET.get('user', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if action:
        entries = entries.filter(action=action)
    if user_id:
        entries = entries.filter(user_id=user_id)
    if date_from:
        entries = entries.filter(created_at__date__gte=date_from)
    if date_to:
        entries = entries.filter(created_at__date__lte=date_to)

    entries = entries[:500]  # Limit for performance
    users = User.objects.all().order_by('name')
    action_choices = AuditTrail.ACTION_CHOICES

    context = {
        'entries': entries,
        'users': users,
        'action_choices': action_choices,
        'active_action': action,
        'active_user': user_id,
        'date_from': date_from,
        'date_to': date_to,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/trail_list.html', context)
    return render(request, 'core/audit_trail.html', context)


@login_required
def audit_trail_export(request):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)

    entries = AuditTrail.objects.all()

    action = request.GET.get('action', '')
    user_id = request.GET.get('user', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    if action:
        entries = entries.filter(action=action)
    if user_id:
        entries = entries.filter(user_id=user_id)
    if date_from:
        entries = entries.filter(created_at__date__gte=date_from)
    if date_to:
        entries = entries.filter(created_at__date__lte=date_to)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="audit_trail.csv"'
    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'Action', 'User', 'Entity', 'Description', 'IP'])

    for e in entries[:5000]:
        writer.writerow([
            e.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            e.get_action_display(),
            e.user.name if e.user else 'System',
            f"{e.entity_type} #{e.entity_id}",
            e.description,
            e.ip_address or '',
        ])
    return response
