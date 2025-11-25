from django.urls import path
from .views import (
    ConferenceListView,
    ConferenceCreateView,
    ConferenceDetailView,
    ConferenceUpdateView,
    ConferenceDeleteView
)

urlpatterns = [
    path('conferences/', ConferenceListView.as_view(), name='conference_list'),
    path('conferences/create/', ConferenceCreateView.as_view(), name='conference_create'),
    path('conferences/<uuid:id>/', ConferenceDetailView.as_view(), name='conference_detail'),
    path('conferences/<uuid:id>/update/', ConferenceUpdateView.as_view(), name='conference_update'),
    path('conferences/<uuid:id>/delete/', ConferenceDeleteView.as_view(), name='conference_delete'),
]