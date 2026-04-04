from django.contrib import admin
from .models import User

admin.site.site_header = "Eli Collection Management"
admin.site.site_title = "Eli Collection"
admin.site.index_title = "Welcome to Eli Collection POS Portal"

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'name', 'role', 'avatar', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'name')
    ordering = ('name',)
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('name', 'avatar')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
