# core/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import Message
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Message)
def handle_message_events(sender, instance, created, **kwargs):
    """
    1. New message → Notify admin
    2. Reply added → Email user
    """
    if created:
        # ── 1. NEW MESSAGE: Notify Admin ─────────────────────
        subject = f"New Contact Message from {instance.full_name}"
        html_message = render_to_string("emails/new_message_admin.html", {
            "message": instance,
            "site_name": "ScholarHub",
        })
        plain_message = strip_tags(html_message)

        try:
            send_mail(
                subject=subject,
                message=plain_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.ADMIN_EMAIL],  # Set in settings.py
                fail_silently=False,
            )
            logger.info(f"Admin notified for message {instance.id}")
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")

    else:
        # ── 2. REPLY ADDED: Email User ───────────────────────
        # Check if reply_text was added/updated
        if instance.reply_text and instance.replied_at:
            # Avoid sending email multiple times
            if not hasattr(instance, "_reply_sent"):
                subject = "We’ve replied to your message!"
                html_message = render_to_string("emails/message_reply_user.html", {
                    "message": instance,
                    "site_name": "ScholarHub",
                })
                plain_message = strip_tags(html_message)

                try:
                    send_mail(
                        subject=subject,
                        message=plain_message,
                        html_message=html_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[instance.email],
                        fail_silently=False,
                    )
                    instance._reply_sent = True  # Prevent duplicate
                    logger.info(f"Reply email sent to {instance.email}")
                except Exception as e:
                    logger.error(f"Failed to send reply email: {e}")