from rest_framework import serializers
from .models import User, Passcode
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
import uuid

# -----------------------
# User Serializer
# -----------------------
class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True, required=True, min_length=6)
    class Meta:
        model = User
        fields = ('id', 'email', 'password', 'confirm_password', 'is_passcode_verified', 'agreement', 'full_name', 'role', 'is_scholar', 'date_joined')
        read_only_fields = ('id', 'is_superuser', 'is_passcode_verified', 'date_joined')
        
    def validate_full_name(self, value):
        if len(value) < 5:
            raise serializers.ValidationError("Full name must be at least 5 characters.")
        return value
    
    def validate_password(self, value):
        if len(value) < 6:
            raise serializers.ValidationError("Password must be at least 6 characters.")
        if (value.isdigit() or value.isalpha()):
            raise serializers.ValidationError("Password must contain both letters and numbers.")
        if (value.islower() or value.isupper()):
            raise serializers.ValidationError("Password must contain both uppercase and lowercase letters.")
        if not any(char in '!@#$%^&*()_+' for char in value):
            raise serializers.ValidationError("Password must contain at least one special character.")
        if value != self.initial_data.get('confirm_password'):
            raise serializers.ValidationError("Passwords do not match.")
        try:
            validate_password(value)
        except serializers.ValidationError as e:
            raise serializers.ValidationError(str(e))
        return value
    
    def validate_email(self, value):
        role = self.initial_data.get('role', '').lower()
        is_scholar = self.initial_data.get('is_scholar', False)

        # Rule for scholars
        if is_scholar:
            allowed = ('.edu', '.org', '.net')
            if not value.lower().endswith(allowed):
                raise serializers.ValidationError(
                    "Scholars must use an email ending in .edu, .org, or .net."
                )

        # Rule for admins
        if role == 'admin':
            if not value.lower().endswith('.com'):
                raise serializers.ValidationError(
                    "Admins must use an email ending in .com."
                )
        else:
            if value.lower().endswith('.com'):
                raise serializers.ValidationError(
                    "Only admins are allowed to use .com emails."
                )

        return value


    def create(self, validated_data):
        # Ensure password meets validation criteria
        validated_data.pop('confirm_password')
        user = User.objects.create_user(
            email = validated_data['email'],
            full_name = validated_data['full_name'],
            is_scholar = validated_data['is_scholar'],
            role = validated_data['role'],
            password = validated_data['password'],
            agreement = validated_data['agreement']
        )
        user.set_password(validated_data['password'])
        user.save()
        return user

    def update(self, instance, validated_data):
        # Allow password update securely
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            user = authenticate(email=email, password=password)
            
            if not user:
                raise serializers.ValidationError("User does not exist")
            if user and not user.check_password(password):
                raise serializers.ValidationError("Incorrect credentials, please try again.")
            attrs['user'] = user
            return attrs
        
        
class BlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'is_active')
        read_only_fields = ('id',)
        
    def update(self, instance, validated_data):
        instance.is_active = validated_data.get('is_active', instance.is_active)
        instance.save()
        return instance


class PasscodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Passcode
        fields = ['id', 'code', 'role', 'created_by', 'is_used', 'is_active', 'created_at']
        read_only_fields = ['code', 'created_by', 'created_at']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        code = str(uuid.uuid4()).replace('-', '')[:12].upper()
        while Passcode.objects.filter(code=code).exists():
            code = str(uuid.uuid4()).replace('-', '')[:12].upper()
        validated_data['code'] = code
        return super().create(validated_data)
    
    
class PasscodeVerificationSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)
    code = serializers.CharField(required=True, min_length=6, max_length=50)
    
    def validate(self, attrs):
        role = attrs.get('role')
        code = attrs.get('code').strip()
        try:
            passcode = Passcode.objects.get(code=code, role=role, is_active=True, is_used=False)
            attrs['passcode'] = passcode
            return attrs
        except Passcode.DoesNotExist:
            raise serializers.ValidationError({"code": "Invalid passcode for the selected role."})
        
        
    def save(self, **kwargs):
        passcode = self.validated_data.get('passcode')

        # ✅ Double check before marking used
        if not passcode.is_used:
            passcode.is_used = True
            passcode.save(update_fields=['is_used'])

        return passcode