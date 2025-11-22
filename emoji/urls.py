from django.urls import path
from .views import AddOrUpdateReaction

urlpatterns = [
    path('comment/react/', AddOrUpdateReaction.as_view(), name="comment-add-reaction"),
]
