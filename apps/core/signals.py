from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .models import log_audit


@receiver(user_logged_in)
def on_user_login(sender, request, user, **kwargs):
    ip = request.META.get('REMOTE_ADDR', '') if request else ''
    log_audit(
        action='login',
        user=user,
        entity_type='User',
        entity_id=str(user.pk),
        description=f'{user.name} logged in',
        ip_address=ip,
    )


@receiver(user_logged_out)
def on_user_logout(sender, request, user, **kwargs):
    if user:
        ip = request.META.get('REMOTE_ADDR', '') if request else ''
        log_audit(
            action='logout',
            user=user,
            entity_type='User',
            entity_id=str(user.pk),
            description=f'{user.name} logged out',
            ip_address=ip,
        )
