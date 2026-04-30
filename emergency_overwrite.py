import requests
import json

USERNAME = "elicollections"
TOKEN = "4a2f6bd86df6c5ae4af3d6b8cc780434f4a6765a"
headers = {"Authorization": f"Token {TOKEN}"}
api_base = f"https://www.pythonanywhere.com/api/v0/user/{USERNAME}/files/path/home/{USERNAME}/nyoroku/"

# 1. New login.html content
login_html_content = """{% extends 'base.html' %}
{% load static %}

{% block content %}
<div class="flex flex-col items-center justify-center min-h-[90vh] px-6" 
     x-data="{ 
       step: 'select', 
       selectedUser: null, 
       pin: '', 
       error: false,
       selectUser(user) {
         this.selectedUser = user;
         this.step = 'pin';
         this.pin = '';
         this.error = false;
       },
       goBack() {
         this.step = 'select';
         this.selectedUser = null;
         this.pin = '';
         this.error = false;
       }
     }">
  
  <div class="text-center mb-8">
    <h1 class="font-display font-extrabold text-[42px] tracking-tight text-brand-green leading-none">Jimmy Mini Mart</h1>
    <p class="text-text-muted mt-2 font-medium uppercase tracking-[0.2em] text-[10px]">Point of Sale</p>
  </div>

  <div x-show="step === 'select'" class="w-full max-w-md">
    <h2 class="text-center text-text-primary text-xl font-bold mb-8">Who are you?</h2>
    <div class="grid grid-cols-2 sm:grid-cols-3 gap-6">
      {% for user in users %}
      <button @click="selectUser({ id: '{{ user.id }}', name: '{{ user.name }}', avatar: '{{ user.avatar }}' })"
              class="flex flex-col items-center gap-3 p-4 bg-surface2 border border-border rounded-2xl transition-all scale-100 active:scale-95">
        <div class="w-16 h-16 bg-surface1 rounded-full flex items-center justify-center text-3xl">{{ user.avatar }}</div>
        <span class="text-sm font-semibold text-text-primary truncate w-full text-center">{{ user.name }}</span>
      </button>
      {% endfor %}
    </div>
  </div>

  <div x-show="step === 'pin'" class="flex flex-col items-center w-full">
    <div class="flex flex-col items-center mb-8">
        <div class="w-20 h-20 bg-surface2 rounded-full flex items-center justify-center text-4xl mb-3 shadow-xl">
            <span x-text="selectedUser?.avatar"></span>
        </div>
        <h2 class="text-text-primary text-xl font-bold" x-text="'Welcome back, ' + selectedUser?.name"></h2>
        <button @click="goBack()" class="text-text-muted text-xs font-medium uppercase tracking-widest mt-2 hover:text-brand-green transition-colors flex items-center gap-1">Switch User</button>
    </div>

    <div class="flex gap-6 mb-12" :class="{ 'animate-shake': error }">
      <template x-for="i in 4">
        <div class="w-4 h-4 rounded-full border-2 border-surface2 transition-all duration-200"
             :class="pin.length >= i ? 'bg-brand-green border-brand-green' : ''">
        </div>
      </template>
    </div>

    <form id="pin-form" hx-post="{% url 'accounts:login' %}" hx-swap="none">
      <input type="hidden" name="user_id" :value="selectedUser?.id">
      <input type="hidden" name="pin" :value="pin">
      <div class="grid grid-cols-3 gap-4 max-w-[280px]">
        <template x-for="n in ['1', '2', '3', '4', '5', '6', '7', '8', '9']">
          <button type="button" @click="if(pin.length < 4) { pin += n; if(pin.length === 4) htmx.trigger('#pin-form', 'submit') }" class="w-[76px] h-[76px] bg-surface2 border border-border rounded-[16px] flex items-center justify-center text-[22px] font-semibold text-text-primary active:scale-95 transition-transform">
            <span x-text="n"></span>
          </button>
        </template>
        <div class="col-span-1"></div>
        <button type="button" @click="if(pin.length < 4) { pin += '0'; if(pin.length === 4) htmx.trigger('#pin-form', 'submit') }" class="w-[76px] h-[76px] bg-surface2 border border-border rounded-[16px] flex items-center justify-center text-[22px] font-semibold text-text-primary active:scale-95 transition-transform">0</button>
        <button type="button" @click="pin = ''" class="w-[76px] h-[76px] flex items-center justify-center text-text-muted active:scale-95 transition-transform">Clear</button>
      </div>
    </form>
  </div>
</div>

<script>
  document.addEventListener('htmx:afterRequest', (e) => {
    if (e.detail.xhr.status === 401) {
      const el = document.querySelector('[x-data]');
      const data = Alpine.$data(el);
      data.error = true;
      data.pin = '';
      setTimeout(() => { data.error = false; }, 500);
    }
  });
</script>
{% endblock %}
"""

# 2. New views.py content
views_py_content = """import re
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
        user_id = request.POST.get('user_id')
        pin = request.POST.get('pin', '')
        if not re.fullmatch(r'\\d{4}', pin):
            return HttpResponse('Invalid PIN format', status=400)
        if not user_id:
            return HttpResponse('User not selected', status=400)
        user = get_object_or_404(User, id=user_id, is_active=True)
        if user.check_password(pin):
            login(request, user)
            response = HttpResponse(status=204)
            response['HX-Redirect'] = '/pos/'
            return response
        else:
            return HttpResponse('Incorrect PIN', status=401)

    users = User.objects.filter(is_active=True).order_by('name')
    return render(request, 'accounts/login.html', {'users': users})

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
    if not re.fullmatch(r'\\d{4}', pin):
        return HttpResponse('Invalid PIN', status=400)
    User.objects.create_user(pin=pin, name=name, role=role)
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
"""

print("Overwriting login.html...")
requests.post(api_base + "templates/accounts/login.html", headers=headers, files={"content": login_html_content})
print("Overwriting apps/accounts/views.py...")
requests.post(api_base + "apps/accounts/views.py", headers=headers, files={"content": views_py_content})
print("Reloading WebApp...")
requests.post(f"https://www.pythonanywhere.com/api/v0/user/{USERNAME}/webapps/{USERNAME}.pythonanywhere.com/reload/", headers=headers)
print("Done.")
