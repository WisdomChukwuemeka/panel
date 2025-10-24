# File: payments/models.py
from django.db import models
from accounts.models import User
from django.utils import timezone

class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('refund_requested', 'Refund Requested'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reference = models.CharField(max_length=100, unique=True)
    payment_type = models.CharField(max_length=20, choices=[('publication_fee', 'Publication Fee'), ('review_fee', 'Review Fee')])
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    paystack_data = models.JSONField(default=dict)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)
    used = models.BooleanField(default=False)  # Added to track if used for submission

    def __str__(self):
        return f"{self.reference} - {self.payment_type} - {self.status}"

class Subscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    free_reviews_used = models.IntegerField(default=0)
    free_reviews_granted = models.BooleanField(default=False)

    def has_free_review_available(self):
        return self.free_reviews_used < 2 if self.free_reviews_granted else False

    def use_free_review(self):
        if self.has_free_review_available():
            self.free_reviews_used += 1
            self.save()
            return True
        return False