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
        if user:
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                'message': 'Registration Succssfull',
                'role': user.role,
            }, status=status.HTTP_201_CREATED)
# -----------------------
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
    
class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        # ✅ Block editors without verified passcode
        if user.role == 'editor' and not user.is_passcode_verified:
            return Response(
                {"error": "Editor must verify passcode before logging in."},
                status=status.HTTP_403_FORBIDDEN
            )

        if not user.is_active:
            return Response(
                {"error": "This account is inactive. Please contact the administrator."},
                status=status.HTTP_403_FORBIDDEN
            )

        # ✅ Proceed to issue tokens normally
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'message': 'Login successful',
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }, status=status.HTTP_200_OK)

            

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