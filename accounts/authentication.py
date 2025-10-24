# from rest_framework_simplejwt.authentication import JWTAuthentication

# class CookieJWTAuthentication(JWTAuthentication):
#     """
#     Custom authentication class that reads JWT token from cookies.
#     """

#     def authenticate(self, request):
#         # Try to get token from 'access_token' cookie
#         access_token = request.COOKIES.get('access_token')

#         if access_token is None:
#             # Fallback to default header authentication
#             return super().authenticate(request)

#         # Validate the token manually
#         validated_token = self.get_validated_token(access_token)
#         user = self.get_user(validated_token)
#         return (user, validated_token)
