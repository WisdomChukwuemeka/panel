from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import exceptions

class CookieJWTAuthentication(JWTAuthentication):
    """
    Extract JWT from HttpOnly cookies instead of Authorization header.
    """

    def authenticate(self, request):
        access_token = request.COOKIES.get("access_token")

        if not access_token:
            return None  # No token means DRF tries the next authentication class

        try:
            validated_token = self.get_validated_token(access_token)
        except Exception:
            raise exceptions.AuthenticationFailed("Invalid or expired access token.")

        user = self.get_user(validated_token)
        return (user, validated_token)
