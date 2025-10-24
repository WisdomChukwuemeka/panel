# payments/views.py
import hmac
import hashlib
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Payment, Subscription
from .serializers import PaymentSerializer, InitializePaymentSerializer, SubscriptionSerializer, RequestRefundSerializer
from publications.models import Publication, Notification
from rest_framework.permissions import AllowAny
import requests
import logging
from decimal import Decimal
from django.urls import reverse
from accounts.models import User
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)

class InitializePublicationPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    @method_decorator(csrf_exempt)  # Add this
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        serializer = InitializePaymentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        payment_type = data['payment_type']
        publication_id = data.get('publication_id')

        # Set amount based on payment_type
        if payment_type == 'publication_fee':
            amount = Decimal('25000.00')  # Explicit 25,000 for publication fee
        elif payment_type == 'review_fee':
            amount = Decimal('3000.00')  # Explicit 3,000 for review fee
            # Verify publication and check free review eligibility
            publication = get_object_or_404(Publication, id=publication_id, author=request.user)
            if publication.rejection_count < 1:
                return Response(
                    {"detail": "Review fee is only applicable after initial rejection."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Check if user has free reviews available
            subscription, _ = Subscription.objects.get_or_create(user=request.user)
            if subscription.has_free_review_available():
                return Response(
                    {"detail": "You have free reviews available. Use them before paying a review fee."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Prepare Paystack payload
        payload = {
            "amount": int(amount * 100),  # Paystack expects amount in kobo
            "email": request.user.email,
            "callback_url": 'https://scholar-ra71.vercel.app/paystack/callback/',
            "metadata": {"publication_id": publication_id} if publication_id else {}
        }

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                "https://api.paystack.co/transaction/initialize",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            resp_data = response.json()

            if resp_data.get('status'):
                # Create Payment record
                payment = Payment.objects.create(
                    user=request.user,
                    reference=resp_data['data']['reference'],
                    payment_type=payment_type,
                    amount=amount,
                    status='pending',
                    paystack_data=resp_data['data'],
                    metadata=payload['metadata']
                )
                return Response({
                    "authorization_url": resp_data['data']['authorization_url'],
                    "reference": payment.reference,
                    "message": "Payment initialized successfully."
                }, status=status.HTTP_200_OK)
            else:
                logger.error(f"Paystack initialization failed: {resp_data}")
                return Response(
                    {"detail": "Failed to initialize payment."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except requests.RequestException as e:
            logger.error(f"Paystack API error: {str(e)}")
            return Response(
                {"detail": "Error communicating with payment gateway."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class VerifyPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        reference = request.data.get('reference')
        if not reference:
            return Response({"detail": "Reference is required."}, status=status.HTTP_400_BAD_REQUEST)

        payment = get_object_or_404(Payment, reference=reference, user=request.user)
        if payment.status == 'success':
            return Response({"detail": "Payment already verified."}, status=status.HTTP_400_BAD_REQUEST)

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.get(
                f"https://api.paystack.co/transaction/verify/{reference}",
                headers=headers
            )
            response.raise_for_status()
            resp_data = response.json()

            if resp_data['status'] and resp_data['data']['status'] == 'success':
                expected_amount = payment.amount * 100  # Convert to kobo
                if resp_data['data']['amount'] == expected_amount:
                    payment.status = 'success'
                    payment.paystack_data = resp_data['data']
                    payment.used = True  # Mark payment as used
                    payment.save()

                    # Handle publication status update
                    if payment.metadata.get('publication_id'):
                        publication = get_object_or_404(
                            Publication,
                            id=payment.metadata['publication_id'],
                            author=request.user
                        )
                        publication.status = 'under_review'
                        publication.save()

                        # For publication_fee, grant free reviews
                        if payment.payment_type == 'publication_fee':
                            subscription, _ = Subscription.objects.get_or_create(user=request.user)
                            if not subscription.free_reviews_granted:
                                subscription.free_reviews_granted = True
                                subscription.save()

                    return Response({
                        "detail": "Payment verified successfully.",
                        "payment": PaymentSerializer(payment).data
                    }, status=status.HTTP_200_OK)
                else:
                    payment.status = 'failed'
                    payment.save()
                    return Response(
                        {"detail": "Payment amount mismatch."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                payment.status = 'failed'
                payment.save()
                return Response(
                    {"detail": "Payment verification failed."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except requests.RequestException as e:
            logger.error(f"Paystack verification error: {str(e)}")
            return Response(
                {"detail": "Error verifying payment."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PaystackWebhookView(APIView):
    permission_classes = []  # Allow Paystack to access without authentication

    def post(self, request):
        # Verify Paystack signature for production
        paystack_signature = request.headers.get('x-paystack-signature')
        if not paystack_signature:
            logger.error("No x-paystack-signature header provided.")
            return Response({"detail": "Missing signature header."}, status=status.HTTP_400_BAD_REQUEST)

        # Compute HMAC SHA512 signature
        secret_key = settings.PAYSTACK_SECRET_KEY.encode('utf-8')
        payload = request.body  # Raw request body as bytes
        computed_signature = hmac.new(
            secret_key,
            payload,
            hashlib.sha512
        ).hexdigest()

        if not hmac.compare_digest(computed_signature, paystack_signature):
            logger.error("Invalid Paystack signature.")
            return Response({"detail": "Invalid signature."}, status=status.HTTP_400_BAD_REQUEST)

        # Process webhook event
        event = request.data.get('event')
        data = request.data.get('data')

        if event == 'charge.success':
            reference = data.get('reference')
            payment = get_object_or_404(Payment, reference=reference)
            if payment.status != 'success':
                expected_amount = payment.amount * 100  # Convert to kobo
                if data['amount'] == expected_amount:
                    payment.status = 'success'
                    payment.paystack_data = data
                    payment.used = True
                    payment.save()

                    # Update publication status
                    if payment.metadata.get('publication_id'):
                        publication = get_object_or_404(
                            Publication,
                            id=payment.metadata['publication_id'],
                            author=payment.user
                        )
                        publication.status = 'under_review'
                        publication.save()

                        # Grant free reviews for publication_fee
                        if payment.payment_type == 'publication_fee':
                            subscription, _ = Subscription.objects.get_or_create(user=payment.user)
                            if not subscription.free_reviews_granted:
                                subscription.free_reviews_granted = True
                                subscription.save()

        return Response({"status": "success"}, status=status.HTTP_200_OK)


# payments/views.py
class PaystackCallbackView(APIView):
    permission_classes = []  # Public endpoint

    def verify_payment(self, reference):
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Paystack verification failed: {str(e)}")
            return {"status": False, "message": str(e)}

    def get(self, request, *args, **kwargs):
        reference = request.GET.get('reference')
        if not reference:
            logger.error("No reference provided in callback")
            return Response({"detail": "Reference not provided."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = Payment.objects.get(reference=reference)
            payment_data = self.verify_payment(reference)
            
            if payment_data.get('status') is True and payment_data.get('data', {}).get('status') == 'success':
                expected_amount = payment.amount * 100  # Convert to kobo
                if payment_data['data']['amount'] == expected_amount:
                    payment.status = 'success'
                    publication = Publication.objects.get(id=payment.metadata['publication_id'])
                    publication.status = 'under_review'
                    publication.save()
                    payment.metadata.update(payment_data.get('data', {}).get('metadata', {}))
                    payment.save()
                    Notification.objects.create(
                        user=payment.user,
                        message=f"Payment {payment.reference} successful. Publication {publication.title} is now under review.",
                        related_publication=publication
                    )
                    return Response(
                        {
                            "detail": "Payment verified successfully.",
                            "payment": PaymentSerializer(payment).data,
                            "redirect_url": f"/publications/{publication.id}"
                        },
                        status=status.HTTP_200_OK
                    )
                else:
                    payment.status = 'failed'
                    payment.save()
                    logger.error(f"Payment amount mismatch for reference {reference}: expected {expected_amount}, got {payment_data['data']['amount']}")
                    return Response({"detail": "Payment amount mismatch."}, status=status.HTTP_400_BAD_REQUEST)
            else:
                payment.status = 'failed'
                payment.save()
                logger.error(f"Payment verification failed for reference {reference}: {payment_data.get('message')}")
                return Response({"detail": "Payment verification failed."}, status=status.HTTP_400_BAD_REQUEST)
        except Payment.DoesNotExist:
            logger.error(f"Payment not found for reference {reference}")
            return Response({"detail": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Callback error for reference {reference}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)            

class RequestRefundView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = RequestRefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reference = serializer.validated_data['reference']
        payment = get_object_or_404(Payment, reference=reference, user=request.user)

        if payment.status != 'success':
            return Response(
                {"detail": "Only successful payments can be refunded."},
                status=status.HTTP_400_BAD_REQUEST
            )

        payment.status = 'refund_requested'
        payment.save()

        # Notify editors
        editors = User.objects.filter(role='editor')
        for editor in editors:
            Notification.objects.create(
                user=editor,
                message=f"Refund requested for payment {reference} by {request.user.full_name} at {timezone.now().strftime('%I:%M %p WAT, %B %d, %Y')}.",
                related_publication_id=payment.metadata.get('publication_id')
            )

        return Response(
            {"detail": "Refund request submitted successfully."},
            status=status.HTTP_200_OK
        )

class PaymentHistoryView(generics.ListAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user).order_by('-created_at')

class PaymentDetailsView(generics.RetrieveAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'reference'

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user)

class SubscriptionView(generics.RetrieveAPIView):
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        subscription, _ = Subscription.objects.get_or_create(user=self.request.user)
        return subscription

class PaymentSuccessRedirectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        reference = request.query_params.get('reference')
        if not reference:
            return Response({"detail": "Reference is required."}, status=status.HTTP_400_BAD_REQUEST)

        payment = get_object_or_404(Payment, reference=reference, user=request.user)
        if payment.status == 'success' and payment.metadata.get('publication_id'):
            redirect_url = reverse('publication-detail', kwargs={'pk': payment.metadata['publication_id']})
            return Response({"redirect_url": redirect_url}, status=status.HTTP_200_OK)
        return Response({"detail": "Invalid payment or publication."}, status=status.HTTP_400_BAD_REQUEST)

class InitializePublicationPaymentWithOverrideView(APIView):
    permission_classes = [permissions.IsAdminUser]  # Restrict to admin for custom amounts

    def post(self, request):
        serializer = InitializePaymentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        payment_type = data['payment_type']
        publication_id = data.get('publication_id')
        amount = data['amount']  # Allow custom amount for admin override

        if payment_type == 'review_fee':
            publication = get_object_or_404(Publication, id=publication_id)
            if publication.rejection_count < 1:
                return Response(
                    {"detail": "Review fee is only applicable after initial rejection."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        payload = {
            "amount": int(amount * 100),
            "email": request.user.email,
            "callback_url": request.build_absolute_uri(reverse('paystack-callback')),
            "metadata": {"publication_id": publication_id} if publication_id else {}
        }

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                "https://api.paystack.co/transaction/initialize",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            resp_data = response.json()

            if resp_data.get('status'):
                payment = Payment.objects.create(
                    user=request.user,
                    reference=resp_data['data']['reference'],
                    payment_type=payment_type,
                    amount=amount,
                    status='pending',
                    paystack_data=resp_data['data'],
                    metadata=payload['metadata']
                )
                return Response({
                    "authorization_url": resp_data['data']['authorization_url'],
                    "reference": payment.reference,
                    "message": "Payment initialized successfully."
                }, status=status.HTTP_200_OK)
            else:
                logger.error(f"Paystack initialization failed: {resp_data}")
                return Response(
                    {"detail": "Failed to initialize payment."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except requests.RequestException as e:
            logger.error(f"Paystack API error: {str(e)}")
            return Response(
                {"detail": "Error communicating with payment gateway."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )