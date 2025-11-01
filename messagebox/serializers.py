from rest_framework import serializers
from .models import Message
from rest_framework.authentication import authenticate

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [ 'id', 'full_name', 'email', 'text', 'created_at']
        read_only_field = ['id', 'created_at']
        