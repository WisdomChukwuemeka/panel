from django.urls import path
from .views import PublicationListCreateView, FreeReviewStatusView, NotificationMarkAllReadView, PublicationUpdateView, PublicationDetailView, NotificationListView, NotificationMarkReadView, NotificationUnreadView, ViewsUpdateView

urlpatterns = [
    path('publications/', PublicationListCreateView.as_view(), name='publication-list-create'),
    path('publications/<str:pk>/', PublicationDetailView.as_view(), name='publication-detail'),
    path('publications/<str:id>/update/', PublicationUpdateView.as_view(), name='publication_update'),  # Changed pk to id
    path('publications/<str:pk>/views/', ViewsUpdateView.as_view(), name='publication-views-update'),
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/<str:pk>/read/', NotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('notifications/unread/', NotificationUnreadView.as_view(), name='notification-unread'),
    path('notifications/mark-all-read/', NotificationMarkAllReadView.as_view(), name='notification-mark-all-read'),
    path('free-review-status/', FreeReviewStatusView.as_view(), name='free-review-status'),
]