import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from .models import User

def logout_view(request):
    logout(request)
    return redirect('accounts:login')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('pos:index')
    
    users = User.objects.filter(is_active=True).order_by('name')
    return render(request, 'accounts/login.html', {'users': users})

@require_http_methods(["POST"])
def pin_auth(request):
    """HTMX endpoint for PIN-based authentication."""
    username = request.POST.get('username', '')
    pin = request.POST.get('pin', '')
    
    if not username or not pin:
        return HttpResponse(
            '<div class="text-brand-red text-xs font-bold text-center animate-shake">Missing credentials</div>',
            status=400
        )
    
    try:
        user = User.objects.get(username=username, is_active=True)
    except User.DoesNotExist:
        return HttpResponse(
            '<div class="text-brand-red text-xs font-bold text-center animate-shake">User not found</div>',
            status=401
        )
        
    if user.locked_until and user.locked_until > timezone.now():
        remaining = int((user.locked_until - timezone.now()).total_seconds() / 60)
        return HttpResponse(
            f'<div class="text-brand-red text-xs font-bold text-center animate-shake">Account locked. Try again in {remaining} min</div>',
            status=401
        )
    
    # Check PIN first, then fall back to password
    if (user.pin_hash and user.check_pin(pin)) or user.check_password(pin):
        login(request, user)
        # Reset lockout counters
        user.failed_pin_attempts = 0
        user.locked_until = None
        user.save(update_fields=['failed_pin_attempts', 'locked_until'])
        
        response = HttpResponse(status=200)
        response['HX-Redirect'] = '/pos/'
        return response
    else:
        user.failed_pin_attempts += 1
        if user.failed_pin_attempts >= 5:
            user.locked_until = timezone.now() + timezone.timedelta(minutes=15)
        user.save(update_fields=['failed_pin_attempts', 'locked_until'])
        
        return HttpResponse(
            '<div class="text-brand-red text-xs font-bold text-center animate-shake">Wrong PIN — try again</div>',
            status=401
        )

@login_required
def user_list(request):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
        
    users = User.objects.all().order_by('name')
    return render(request, 'accounts/user_list.html', {'users': users})

@login_required
@require_http_methods(["POST"])
def add_user(request):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
        
    name = request.POST.get('name')
    role = request.POST.get('role', 'cashier')
    pin = request.POST.get('pin', '1234')
    username = request.POST.get('username')
    avatar = request.POST.get('avatar', '👤')
    
    if not username or not pin:
        return HttpResponse('Username and PIN are required', status=400)
    
    if len(pin) != 4 or not pin.isdigit():
        return HttpResponse('PIN must be exactly 4 digits', status=400)
        
    user = User.objects.create_user(username=username, pin=pin, name=name, role=role)
    user.avatar = avatar
    user.set_pin(pin)
    
    basic_salary = request.POST.get('basic_salary')
    if basic_salary:
        user.basic_salary = basic_salary
        
    user.save()
    return redirect('accounts:user_list')

@login_required
def edit_user_modal(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
        
    user = get_object_or_404(User, pk=pk)
    return render(request, 'accounts/partials/edit_user_modal.html', {'u': user})

@login_required
@require_http_methods(["POST"])
def edit_user(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
        
    user = get_object_or_404(User, pk=pk)
    
    user.name = request.POST.get('name', user.name)
    user.username = request.POST.get('username', user.username)
    user.role = request.POST.get('role', user.role)
    
    pin = request.POST.get('pin')
    if pin and len(pin) == 4 and pin.isdigit():
        user.set_pin(pin)
        
    basic_salary = request.POST.get('basic_salary')
    if basic_salary is not None and basic_salary != '':
        user.basic_salary = basic_salary
        
    user.save()
    return redirect('accounts:user_list')

@login_required
@require_http_methods(["DELETE", "POST"])
def delete_user(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
        
    user = get_object_or_404(User, pk=pk)
    if user.role == 'admin' and User.objects.filter(role='admin').count() <= 1:
        return HttpResponse('Cannot delete last admin', status=400)
        
    user.delete()
    if request.headers.get('HX-Request'):
        return HttpResponse('')
        
    return redirect('accounts:user_list')
