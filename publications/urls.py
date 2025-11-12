from django.urls import path
from .views import PublicationListCreateView, PublicationAnnotateView, EditorActivitiesView, EditorReviewView, PublicationLikeView, PublicationDislikeView, FreeReviewStatusView, NotificationMarkAllReadView, PublicationUpdateView, PublicationDetailView, NotificationListView, NotificationMarkReadView, NotificationUnreadView, ViewsUpdateView, PublicationStatsView


urlpatterns = [
    path('publications/', PublicationListCreateView.as_view(), name='publication-list-create'),
    path('publications/stats/', PublicationStatsView.as_view(), name='publication-stats'),
    path('publications/<str:pk>/', PublicationDetailView.as_view(), name='publication-detail'),
    # path('publications/<str:id>/update/', PublicationUpdateView.as_view(), name='publication_update'),  # Changed pk to id
    path('publications/<str:id>/update/', PublicationUpdateView.as_view(), name='publication-update'),
    path('publications/<str:id>/review/', EditorReviewView.as_view(), name='publication-review'),
    path('publications/<str:pk>/views/', ViewsUpdateView.as_view(), name='publication-views-update'),
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/<str:pk>/read/', NotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('notifications/unread/', NotificationUnreadView.as_view(), name='notification-unread'),
    path('notifications/mark-all-read/', NotificationMarkAllReadView.as_view(), name='notification-mark-all-read'),
    path('free-review-status/', FreeReviewStatusView.as_view(), name='free-review-status'),
    path('publications/<str:pk>/like/', PublicationLikeView.as_view(), name='publication-like'),
    path('publications/<str:pk>/dislike/', PublicationDislikeView.as_view(), name='publication-dislike'),
    path('publications/<str:id>/annotate/', PublicationAnnotateView.as_view(), name='publication-annotate'),
    path('editor-activities/', EditorActivitiesView.as_view(), name='editor-activities'),
]

