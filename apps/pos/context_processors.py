from .models import CashHandover

def pending_handovers(request):
    if request.user.is_authenticated and request.user.role in ['admin', 'manager']:
        count = CashHandover.objects.filter(status='pending').count()
    else:
        count = 0
    return {
        'pending_handovers_count': count
    }
