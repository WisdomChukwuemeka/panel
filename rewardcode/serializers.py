# rewardcodes/serializers.py
from rest_framework import serializers
from .models import RewardCode
from django.utils import timezone

class RewardCodeSerializer(serializers.ModelSerializer):
    is_expired = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = RewardCode
        fields = ['id', 'code', 'created_at', 'expires_at', 'redeemed', 'is_expired']
        read_only_fields = fields

    def get_is_expired(self, obj):
        return obj.expires_at < timezone.now() and not obj.redeemed