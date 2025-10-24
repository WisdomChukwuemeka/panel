# payments/serializers.py (modified - removed has_paid_for_publication from SubscriptionSerializer; adjusted validation)
from rest_framework import serializers
from .models import Payment, Subscription
from decimal import Decimal

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['reference', 'amount', 'payment_type', 'status', 'created_at', 'metadata']
        read_only_fields = ['reference', 'amount', 'payment_type', 'status', 'created_at', 'metadata']

class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ["user", 'free_reviews_used', "free_reviews_granted"]
        read_only_fields = ["user", "free_reviews_used", "free_reviews_granted"]

# payments/serializers.py (updated)
class InitializePaymentSerializer(serializers.Serializer):
    payment_type = serializers.ChoiceField(choices=['publication_fee', 'review_fee'])
    publication_id = serializers.CharField(required=False, allow_null=True)

    def validate(self, data):
        payment_type = data['payment_type']
        publication_id = data.get('publication_id')
        if payment_type == 'review_fee' and not publication_id:
            raise serializers.ValidationError({'publication_id': 'publication_id is required for review_fee.'})
        return data

        
class RequestRefundSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=100)

    def validate_reference(self, value):
        payment = Payment.objects.filter(reference=value).first()
        if not payment:
            raise serializers.ValidationError("Payment with this reference does not exist.")
        if payment.status != 'success':
            raise serializers.ValidationError("Only successful payments can be refunded.")
        return value