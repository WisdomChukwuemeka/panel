from rest_framework import serializers
from .models import UserProfile

class UserProfileSerializer(serializers.ModelSerializer):
    profile_image = serializers.ImageField(required=False, allow_null=True)
    class Meta:
        model = UserProfile
        # include every field in the model
        fields = ['id', 'name', 'bio', 'institution', 'affiliation', 'profile_image', 'date_joined']
        read_only_fields = ['id', 'date_joined']   # date_joined set automatically
        
    def validate_profile_image(self, value):
        max_size = 10 * 1024 * 1024  # 10 MB
        if value and hasattr(value, 'size') and value.size > max_size:
            raise serializers.ValidationError("Image file too large (max 10 MB). Please upload a smaller file.")
        if value and hasattr(value, 'size') and value.size < 2 * 1024:  # 10 KB
            raise serializers.ValidationError("Image file too small (min 10 KB). Please upload a larger file.")
        if value and hasattr(value, 'name'):
            valid_extensions = ['.jpg', '.jpeg', '.png']
            if not any(value.name.lower().endswith(ext) for ext in valid_extensions):
                raise serializers.ValidationError(f"Unsupported file extension. Allowed extensions are: {', '.join(valid_extensions)}")
        return value
    
    def get_profile_image(self, obj):
        if obj.profile_image:
            try:
                return obj.profile_image.url  # Full Cloudinary URL
            except Exception:
                return None
        return None
    
    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['profile_image'] = instance.profile_image.url if instance.profile_image else None
        return ret
    
    