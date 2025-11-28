from rest_framework import generics, permissions, status, views
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import User, Passcode
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserSerializer, LoginSerializer, BlockSerializer, PasscodeSerializer,  PasscodeVerificationSerializer
from django.contrib.auth import authenticate
from .permissions import IsSuperUser  #  import your custom permission
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.exceptions import Throttled
from django.conf import settings
access_lifetime = int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())
refresh_lifetime = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.authentication import JWTAuthentication
from accounts.authentication import CookieJWTAuthentication
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

# -----------------------
# User List & Create
# -----------------------
class UserListCreateView(generics.ListCreateAPIView):
    queryset = User.objects.all().order_by('-id')
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]  # Allow registration

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response({"status": "success", "data": serializer.data}, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)

        # Create the actual Response object FIRST
        response = Response({
            'user': UserSerializer(user).data,
            'message': 'Registration Successful',
            'role': user.role,
        }, status=status.HTTP_201_CREATED)

        # Now safely set cookies
        access_lifetime = int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())
        refresh_lifetime = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())

        response.set_cookie(
            key="access_token",
            value=str(refresh.access_token),
            max_age=access_lifetime,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="None",
            path="/",
            domain=".scholar-panel.vercel.app"
        )
        response.set_cookie(
            key="refresh_token",
            value=str(refresh),
            max_age=refresh_lifetime,
            httponly=True,
            # secure=not settings.DEBUG,
            # samesite="None",
            secure=True,
            samesite="None",
            path="/",
            domain=".scholar-panel.vercel.app"
        )

        return response

        
# User Detail (Retrieve, Update, Delete)
# -----------------------
class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsSuperUser]  #  Only superuser can access

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

        # Create response first!
        response = Response({
            'user': UserSerializer(user).data,
            'message': 'Login successful'
        }, status=status.HTTP_200_OK)

        access_lifetime = int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds())
        refresh_lifetime = int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds())

        response.set_cookie(
            key="access_token",
            value=str(refresh.access_token),
            max_age=access_lifetime,
            httponly=True,
            # secure=not settings.DEBUG,
            # samesite="Lax",
            secure=True,  
            samesite="None",   
            path="/",
            domain=".scholar-panel.vercel.app"
        )
        response.set_cookie(
            key="refresh_token",
            value=str(refresh),
            max_age=refresh_lifetime,
            httponly=True,
            # secure=not settings.DEBUG,
            # samesite="Lax",
            secure=True,    
            samesite="None",   
            path="/",
            domain=".scholar-panel.vercel.app"
        )

        return response  # Now correct

class BlockUserView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = BlockSerializer
    permission_classes = [IsSuperUser]  # ✅ Only superuser

    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        user.is_active = False
        user.save()
        return Response({"message": f"User {user.full_name} has been blocked."}, status=status.HTTP_200_OK)


class UnblockUserView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = BlockSerializer
    permission_classes = [IsSuperUser]  # ✅ Only superuser

    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        user.is_active = True
        user.save()
        return Response({"message": f"User {user.full_name} has been unblocked."}, status=status.HTTP_200_OK)
    
    
class PasscodeListCreateView(generics.ListCreateAPIView):
    queryset = Passcode.objects.all().order_by('-id')
    serializer_class = PasscodeSerializer
    permission_classes = [IsAuthenticated, IsSuperUser]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    

class VerifyPasscodeView(APIView):
    serializer_class = PasscodeVerificationSerializer
    permission_classes = [AllowAny]  # Changed to AllowAny
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
            # ❗ CRITICAL FIX: Tell frontend refresh token is expired
            return Response({"detail": "Refresh token expired"}, status=401)

        # If refresh succeeded
        if response.status_code == 200:
            access_lifetime = int(
                settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()
            )
            refresh_lifetime = int(
                settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()
            )

            # Update access token cookie
            response.set_cookie(
                key="access_token",
                value=response.data["access"],
                max_age=access_lifetime,
                expires=access_lifetime,
                httponly=True,
                # secure=not settings.DEBUG,
                # samesite="None",
                secure=True,
                samesite="None",
                path="/",
                domain=".scholar-panel.vercel.app"
            )

            # Update refresh token (only if rotation enabled)
            if "refresh" in response.data:
                response.set_cookie(
                    key="refresh_token",
                    value=response.data["refresh"],
                    max_age=refresh_lifetime,
                    expires=refresh_lifetime,
                    httponly=True,
                    # secure=not settings.DEBUG,
                    # samesite="Lax",
                    secure=True,
                    samesite="None",
                    path="/",
                    domain=".scholar-panel.vercel.app",
                )

            response.data = {"detail": "Token refreshed"}

        return response
    
# accounts/views.py
class LogoutView(APIView):
    def post(self, request):
        try:
            refresh_token = request.COOKIES.get("refresh_token")
            token = RefreshToken(refresh_token)
            token.blacklist()
        except:
            pass

        response = Response({"message": "Logged out"})
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
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






# from rest_framework import generics, permissions, status, views
# from rest_framework.response import Response
# from rest_framework.views import APIView
# from .models import User, Passcode
# from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
# from rest_framework_simplejwt.tokens import RefreshToken
# from .serializers import UserSerializer, LoginSerializer, BlockSerializer, PasscodeSerializer,  PasscodeVerificationSerializer
# from django.contrib.auth import authenticate
# from .permissions import IsSuperUser  #  import your custom permission
# from rest_framework.throttling import ScopedRateThrottle
# from rest_framework.exceptions import Throttled


# # -----------------------
# # User List & Create
# # -----------------------
# class UserListCreateView(generics.ListCreateAPIView):
#     queryset = User.objects.all().order_by('-id')
#     serializer_class = UserSerializer
#     permission_classes = [permissions.AllowAny]  # Allow registration

#     def list(self, request, *args, **kwargs):
#         serializer = self.get_serializer(self.get_queryset(), many=True)
#         return Response({"status": "success", "data": serializer.data}, status=status.HTTP_200_OK)

#     def create(self, request, *args, **kwargs):
#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         user = serializer.save()
#         if user:
#             refresh = RefreshToken.for_user(user)
#             response_data = {
#                 'user': UserSerializer(user).data,
#                 "refresh": str(refresh),
#                 "access": str(refresh.access_token),
#                 'message': 'Registration Successful',
#                 'role': user.role,
#             }
#             response = Response(response_data, status=status.HTTP_201_CREATED)
#             # NEW: Set cookies (access as HttpOnly for security, refresh optionally in localStorage or another cookie)
#             response.set_cookie(
#                 'access_token', 
#                 str(refresh.access_token), 
#                 httponly=True, 
#                 secure=True,  # Set to False for local dev without HTTPS
#                 samesite='Lax', 
#                 max_age=300  # 5 min expiry, match your access token lifetime
#             )
#             response.set_cookie(
#                 'refresh_token', 
#                 str(refresh), 
#                 httponly=True, 
#                 secure=True, 
#                 samesite='Lax', 
#                 max_age=86400  # 24 hours, match refresh lifetime
#             )
#             return response
        
# # User Detail (Retrieve, Update, Delete)
# # -----------------------
# class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
#     queryset = User.objects.all()
#     serializer_class = UserSerializer
#     permission_classes = [IsSuperUser]  #  Only superuser can access

#     def retrieve(self, request, *args, **kwargs):
#         serializer = self.get_serializer(self.get_object())
#         return Response({"status": "success", "data": serializer.data}, status=status.HTTP_200_OK)

#     def update(self, request, *args, **kwargs):
#         user = self.get_object()
#         serializer = self.get_serializer(user, data=request.data, partial=True)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
#         return Response({"status": "success", "data": serializer.data}, status=status.HTTP_200_OK)

#     def destroy(self, request, *args, **kwargs):
#         user = self.get_object()
#         user.delete()
#         return Response({"status": "success", "message": "User deleted"}, status=status.HTTP_204_NO_CONTENT)
    
# class LoginView(generics.GenericAPIView):
#     serializer_class = LoginSerializer
#     permission_classes = [AllowAny]

#     def post(self, request, *args, **kwargs):
#         serializer = self.serializer_class(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         user = serializer.validated_data['user']

#         # ✅ Block editors without verified passcode
#         if user.role == 'editor' and not user.is_passcode_verified:
#             return Response(
#                 {"error": "Editor must verify passcode before logging in."},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         if not user.is_active:
#             return Response(
#                 {"error": "This account is inactive. Please contact the administrator."},
#                 status=status.HTTP_403_FORBIDDEN
#             )

#         # ✅ Proceed to issue tokens normally
#         refresh = RefreshToken.for_user(user)
#         response_data = {
#             'user': UserSerializer(user).data,
#             'message': 'Login successful',
#             "refresh": str(refresh),
#             "access": str(refresh.access_token),
#         }
#         response = Response(response_data, status=status.HTTP_200_OK)
#         # NEW: Set cookies (access as HttpOnly for security, refresh optionally in localStorage or another cookie)
#         response.set_cookie(
#             'access_token', 
#             str(refresh.access_token), 
#             httponly=True, 
#             secure=True,  # Set to False for local dev without HTTPS
#             samesite='Lax', 
#             max_age=300  # 5 min expiry, match your access token lifetime
#         )
#         response.set_cookie(
#             'refresh_token', 
#             str(refresh), 
#             httponly=True, 
#             secure=True, 
#             samesite='Lax', 
#             max_age=86400  # 24 hours, match refresh lifetime
#         )
#         return response
    

# class BlockUserView(generics.UpdateAPIView):
#     queryset = User.objects.all()
#     serializer_class = BlockSerializer
#     permission_classes = [IsSuperUser]  # ✅ Only superuser

#     def patch(self, request, *args, **kwargs):
#         user = self.get_object()
#         user.is_active = False
#         user.save()
#         return Response({"message": f"User {user.full_name} has been blocked."}, status=status.HTTP_200_OK)


# class UnblockUserView(generics.UpdateAPIView):
#     queryset = User.objects.all()
#     serializer_class = BlockSerializer
#     permission_classes = [IsSuperUser]  # ✅ Only superuser

#     def patch(self, request, *args, **kwargs):
#         user = self.get_object()
#         user.is_active = True
#         user.save()
#         return Response({"message": f"User {user.full_name} has been unblocked."}, status=status.HTTP_200_OK)
    
    
# class PasscodeListCreateView(generics.ListCreateAPIView):
#     queryset = Passcode.objects.all().order_by('-id')
#     serializer_class = PasscodeSerializer
#     permission_classes = [IsAuthenticated, IsSuperUser]

#     def perform_create(self, serializer):
#         serializer.save(created_by=self.request.user)
    
    

# class VerifyPasscodeView(APIView):
#     serializer_class = PasscodeVerificationSerializer
#     permission_classes = [AllowAny]  # Changed to AllowAny
#     throttle_classes = [ScopedRateThrottle]
#     throttle_scope = 'verify-passcode'

#     def post(self, request, *args, **kwargs):
#         try:
#             serializer = self.serializer_class(data=request.data)
#             if serializer.is_valid():
#                 passcode = serializer.save()
#                 return Response(
#                     {"message": f"Passcode {passcode.code} verified successfully."},
#                     status=status.HTTP_200_OK
#                 )

#             return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#         except Throttled:
#             return Response(
#                 {"detail": "Too many attempts. Please wait before trying again."},
#                 status=status.HTTP_429_TOO_MANY_REQUESTS
#             )
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
            
