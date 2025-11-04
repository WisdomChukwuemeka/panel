from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import PointReward
from .serializers import PointRewardSerializer
from publications.models import Publication

class PointRewardListCreateView(generics.ListCreateAPIView):
    serializer_class = PointRewardSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # Disable pagination to return all comments

    def get_queryset(self):
        publication_id = self.kwargs["pk"]
        return PointReward.objects.filter(publication__id=publication_id).order_by("created_at")


    def perform_create(self, serializer):
        publication = get_object_or_404(Publication, id=self.kwargs["pk"])
        serializer.save(publication=publication, awarded_by=self.request.user)

class PointRewardDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PointReward.objects.all()
    serializer_class = PointRewardSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        publication_id = self.kwargs["pk"]
        point_id = self.kwargs["point_id"]
        return get_object_or_404(PointReward, id=point_id, publication__id=publication_id)

    def update(self, request, *args, **kwargs):
        point_reward = self.get_object()
        if point_reward.awarded_by != request.user:
            return Response({"detail": "Not authorized to edit this point reward."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        point_reward = self.get_object()
        if point_reward.awarded_by != request.user:
            return Response({"detail": "Not authorized to delete this point reward."}, status=status.HTTP_403_FORBIDDEN)
        point_reward.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)