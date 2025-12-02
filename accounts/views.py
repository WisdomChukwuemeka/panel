from rest_framework import generics, permissions, status, views
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from .models import User, Passcode
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from .serializers import UserSerializer, LoginSerializer, BlockSerializer, PasscodeSerializer, PasscodeVerificationSerializer
from django.contrib.auth import authenticate
from .permissions import IsSuperUser
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.exceptions import Throttled
from django.conf import settings
from rest_framework_simplejwt.views import TokenRefreshView
from accounts.authentication import CookieJWTAuthentication
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


access_lifetime = int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())
refresh_lifetime = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())


# ✅ Helper function to set cookies consistently
def set_auth_cookies(response, access_token, refresh_token):
    """
    Set authentication cookies with consistent settings from Django settings
    """
    # Get settings (fallback to sensible defaults)
    secure = getattr(settings, 'SESSION_COOKIE_SECURE', not settings.DEBUG)
    samesite = getattr(settings, 'SESSION_COOKIE_SAMESITE', 'None' if not settings.DEBUG else 'Lax')
    domain = getattr(settings, 'SESSION_COOKIE_DOMAIN', None)
    
    # Access token cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=access_lifetime,
        httponly=True,
        secure=secure,
        samesite=samesite,
        domain=domain,
        path="/",
    )
    
    # Refresh token cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=refresh_lifetime,
        httponly=True,
        secure=secure,
        samesite=samesite,
        domain=domain,
        path="/",
    )
    
    return response


class UserListCreateView(generics.CreateAPIView):
    """
    Only allows POST to create a user. GET is NOT allowed.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        response = Response({
            'user': UserSerializer(user).data,
            'message': 'Registration Successful',
            'role': user.role,
        }, status=status.HTTP_201_CREATED)

        set_auth_cookies(response, access_token, str(refresh))
        return response


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsSuperUser]

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return Response({"status": "success", "data": serializer.data}, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = self.get_serializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"status": "success", "data": serializer.data}, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        user.delete()
        return Response({"status": "success", "message": "User deleted"}, status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_exempt, name='dispatch')
class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        if user.role == 'editor' and not user.is_passcode_verified:
            return Response({"error": "Invalid credentials"}, status=403)

        if not user.is_active:
            return Response({"error": "This account is inactive."}, status=403)

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        # Create response with role at top level (matching frontend expectations)
        response = Response({
            "user": UserSerializer(user).data,
            "role": user.role,  # ✅ This is what frontend expects
        }, status=status.HTTP_200_OK)

        # ✅ Use helper function for consistent cookie settings
        set_auth_cookies(response, access_token, str(refresh))

        return response


class BlockUserView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = BlockSerializer
    permission_classes = [IsSuperUser]

    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        user.is_active = False
        user.save()
        return Response({"message": f"User {user.full_name} has been blocked."}, status=status.HTTP_200_OK)


class UnblockUserView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = BlockSerializer
    permission_classes = [IsSuperUser]

    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        user.is_active = True
        user.save()
        return Response({"message": f"User {user.full_name} has been unblocked."}, status=status.HTTP_200_OK)


class PasscodeListCreateView(generics.ListCreateAPIView):
    queryset = Passcode.objects.all().order_by('-id')
    serializer_class = PasscodeSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]
    authentication_classes = [CookieJWTAuthentication]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class VerifyPasscodeView(APIView):
    serializer_class = PasscodeVerificationSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'verify-passcode'

    def post(self, request, *args, **kwargs):
        try:
            serializer = self.serializer_class(data=request.data)
            if serializer.is_valid():
                passcode = serializer.save()
                return Response(
                    {"message": f"Passcode {passcode.code} verified successfully."},
                    status=status.HTTP_200_OK
                )

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Throttled:
            return Response(
                {"detail": "Too many attempts. Please wait before trying again."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )


class CookieTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            return Response({"detail": "No refresh token"}, status=401)

        # Inject refresh token into request.data for SimpleJWT
        data = request.data.copy()
        data["refresh"] = refresh_token
        request.data.update(data)

        try:
            # Call SimpleJWT's refresh handler
            response = super().post(request, *args, **kwargs)
        except (InvalidToken, TokenError):
            return Response({"detail": "Refresh token expired"}, status=401)

        # If refresh succeeded
        if response.status_code == 200:
            new_access = response.data.get("access")
            new_refresh = response.data.get("refresh")  # Only if rotation enabled

            # Get settings
            secure = getattr(settings, 'SESSION_COOKIE_SECURE', not settings.DEBUG)
            samesite = getattr(settings, 'SESSION_COOKIE_SAMESITE', 'None' if not settings.DEBUG else 'Lax')
            domain = getattr(settings, 'SESSION_COOKIE_DOMAIN', None)

            # Update access token cookie
            response.set_cookie(
                key="access_token",
                value=new_access,
                max_age=access_lifetime,
                httponly=True,
                secure=secure,
                samesite=samesite,
                domain=domain,
                path="/",
            )

            # Update refresh token (only if rotation enabled)
            if new_refresh:
                response.set_cookie(
                    key="refresh_token",
                    value=new_refresh,
                    max_age=refresh_lifetime,
                    httponly=True,
                    secure=secure,
                    samesite=samesite,
                    domain=domain,
                    path="/",
                )

            response.data = {"detail": "Token refreshed"}

        return response


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        response = Response({"message": "Logged out"}, status=200)

        # Get domain setting for consistent cookie deletion
        domain = getattr(settings, 'SESSION_COOKIE_DOMAIN', None)

        response.delete_cookie("access_token", path="/", domain=domain)
        response.delete_cookie("refresh_token", path="/", domain=domain)

        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [CookieJWTAuthentication]

    def get(self, request):
        return Response({
            "id": request.user.id,
            "full_name": request.user.full_name,
            "email": request.user.email,
            "role": request.user.role,
            "is_active": request.user.is_active,
        })