from django.urls import path
from .views import UserListCreateView, CookieTokenRefreshView, LogoutView, MeView, UserDetailView, LoginView, BlockUserView, UnblockUserView, PasscodeListCreateView, VerifyPasscodeView

urlpatterns = [
    path('register/', UserListCreateView.as_view(), name='user-list-create'),  # GET all users, POST create
    path('login/', LoginView.as_view(), name='login'),
    path('user/<int:pk>/', UserDetailView.as_view(), name='user-detail'),   # GET, PUT/PATCH, DELETE
    path('admin/users/<int:pk>/block/', BlockUserView.as_view(), name='block-user'),
    path('admin/users/<int:pk>/unblock/', UnblockUserView.as_view(), name='unblock-user'),
    path('passcodes/', PasscodeListCreateView.as_view(), name='passcode_list_create'),
    path('verify-passcode/', VerifyPasscodeView.as_view(), name='verify-passcode'),
    path('me/', MeView.as_view(), name='me'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path("token/refresh/", CookieTokenRefreshView.as_view(), name="token_refresh"),
]

