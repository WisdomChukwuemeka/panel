# payments/urls.py (unchanged)
from django.urls import path
from .views import (
    InitializePublicationPaymentView,
    VerifyPaymentView,
    SubscriptionView,
    PaystackWebhookView,
    RequestRefundView,
    PaymentHistoryView,
    PaymentDetailsView,
    PaymentSuccessRedirectView,
    InitializePublicationPaymentWithOverrideView,
    PaystackCallbackView
)

urlpatterns = [
    path('payments/initialize/', InitializePublicationPaymentView.as_view(), name='payment_initialize'),
    path('payments/verify/', VerifyPaymentView.as_view(), name='payment_verify'),
    path('payments/webhook/', PaystackWebhookView.as_view(), name='paystack_webhook'),
    path('payments/refund/', RequestRefundView.as_view(), name='payment_refund'),
    path('subscriptions/', SubscriptionView.as_view(), name='subscription'),
    path('payments/history/', PaymentHistoryView.as_view(), name='payment_history'),
    path('payments/details/<str:reference>/', PaymentDetailsView.as_view(), name='payment_details'),
    path('payments/success/', PaymentSuccessRedirectView.as_view(), name='payment_success'),
    path('payments/initialize-override/', InitializePublicationPaymentWithOverrideView.as_view(), name='payment_initialize_override'),
    path('paystack/callback/', PaystackCallbackView.as_view(), name='paystack-callback'),
]