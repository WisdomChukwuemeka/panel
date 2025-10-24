from rest_framework import serializers
from .models import UserProfile

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        # include every field in the model
        fields = ['id', 'bio', 'institution', 'affiliation', 'date_joined']
        read_only_fields = ['id', 'date_joined']   # date_joined set automatically
