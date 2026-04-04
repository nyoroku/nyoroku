import re
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse
from .models import User

def logout_view(request):
    logout(request)
    return redirect('accounts:login')

def pin_login(request):
    if request.user.is_authenticated:
        return redirect('pos:index')
    
    if request.method == 'POST':
        pin = request.POST.get('pin', '')
        # Basic validation
        if not re.fullmatch(r'\d{4}', pin):
            return render(request, 'accounts/partials/pin_error.html', {'error': 'Invalid PIN'})
        
        # Authenticate
        user = User.objects.filter(is_active=True).all()
        # Find user by matching hashed PIN
        authenticated_user = None
        for u in user:
            if u.check_password(pin):
                authenticated_user = u
                break
        
        if authenticated_user:
            login(request, authenticated_user)
            response = HttpResponse(status=204)
            response['HX-Redirect'] = '/pos/'
            return response
        else:
            return HttpResponse('Wrong PIN', status=401)

    return render(request, 'accounts/login.html')

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
    pin = request.POST.get('pin')
    
    if not re.fullmatch(r'\d{4}', pin):
        return HttpResponse('Invalid PIN', status=400)
        
    User.objects.create_user(pin=pin, name=name, role=role)
    return redirect('accounts:user_list')

@login_required
@require_http_methods(["DELETE", "POST"])
def delete_user(request, pk):
    if request.user.role != 'admin':
        return HttpResponse('Unauthorized', status=403)
        
    user = get_object_or_404(User, pk=pk)
    # Don't delete the last admin
    if user.role == 'admin' and User.objects.filter(role='admin').count() <= 1:
        return HttpResponse('Cannot delete last admin', status=400)
        
    user.delete()
    if request.headers.get('HX-Request'):
        return HttpResponse('')
        
    return redirect('accounts:user_list')
