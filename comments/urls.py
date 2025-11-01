from django.urls import path
from .views import CommentListCreateView, CommentDetailView

urlpatterns = [
    path("publications/<str:pk>/comments/", CommentListCreateView.as_view(), name="publication-comments"),
    path("publications/<str:pk>/comments/<str:comment_id>/", CommentDetailView.as_view(), name="comment-detail"),
]
