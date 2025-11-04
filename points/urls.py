from django.urls import path
from .views import PointRewardListCreateView, PointRewardDetailView

urlpatterns = [
path("publications/<str:pk>/pointrewards/", PointRewardListCreateView.as_view(), name="publication-pointrewards"),
path("publications/<str:pk>/pointrewards/<str:point_id>/", PointRewardDetailView.as_view(), name="pointreward-detail"),
]