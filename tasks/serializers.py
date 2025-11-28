# tasks/serializers.py
from rest_framework import serializers
from .models import Task
from accounts.models import User
from django.db.models import Q
from django.contrib.auth import get_user_model

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'role']


class TaskSerializer(serializers.ModelSerializer):
    assigned_by = UserSerializer(read_only=True)
    assigned_to = UserSerializer(read_only=True)
    assignee = serializers.CharField(write_only=True, help_text="Email or full name of editor")

    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'status', 'status_display',
            'reply_message', 'replied_at', 'due_date', 'created_at', 'updated_at',
            'assigned_by', 'assigned_to', 'assignee', 'is_overdue'
        ]
        read_only_fields = ['status', 'reply_message', 'replied_at', 'created_at', 'updated_at']

    def validate_assignee(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Editor is required.")

        candidates = User.objects.filter(role='editor', is_active=True)

        if '@' in value:
            candidates = candidates.filter(email__iexact=value)
        else:
            parts = value.split()
            if len(parts) >= 2:
                candidates = candidates.filter(
                    Q(first_name__iexact=parts[0]) & Q(last_name__iexact=" ".join(parts[1:]))
                )
            else:
                candidates = candidates.filter(
                    Q(first_name__icontains=value) | Q(last_name__icontains=value)
                )

        if not candidates.exists():
            raise serializers.ValidationError(f"No active editor found: '{value}'")
        if candidates.count() > 1:
            names = ", ".join([u.get_full_name() or u.email for u in candidates[:3]])
            raise serializers.ValidationError(f"Multiple matches: {names}. Use email.")

        return candidates.first()
    
    
    def validate(self, attrs):
        user = attrs.get("assigned_to")
        title = attrs.get("title")

        if Task.objects.filter(
            assigned_to=user,
            title=title,
            status__in=['pending', 'in_progress']
        ).exists():
            raise serializers.ValidationError(
                "This editor already has an active task with this title."
            )

        return attrs


    def create(self, validated_data):
        editor = validated_data.pop('assignee')
        validated_data['assigned_to'] = editor
        validated_data['assigned_by'] = self.context['request'].user
        return super().create(validated_data)


class TaskReplySerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ['reply_message']

    def validate_reply_message(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Message is required.")
        return value.strip()

    def update(self, instance, validated_data):
        reply = validated_data['reply_message']
        instance.mark_as_completed(reply, by_user=self.context['request'].user)
        return instance


class TaskInProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = []

    def update(self, instance, validated_data):
        instance.mark_as_in_progress(by_user=self.context['request'].user)
        return instance