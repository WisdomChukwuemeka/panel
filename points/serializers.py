from rest_framework import serializers
from .models import PointReward

class PointRewardSerializer(serializers.ModelSerializer):
    awarded_by_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PointReward
        fields = ["id", "publication", "comment", "awarded_by", "awarded_by_name", "points", "created_at"]
        read_only_fields = ["id", "publication", "awarded_by", "created_at"]

    def get_awarded_by_name(self, obj):  #  correct placement
        if obj.awarded_by:
            return obj.awarded_by.get_full_name() or obj.awarded_by.email
        return "System"
