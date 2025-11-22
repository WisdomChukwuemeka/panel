# comments/views.py
import logging
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import Comment
from .serializers import CommentSerializer
from publications.models import Publication

logger = logging.getLogger(__name__)


class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # keep this

    def get_queryset(self):
        publication_id = self.kwargs["pk"]
        return Comment.objects.filter(
            publication__id=publication_id
        ).order_by("created_at")

    def create(self, request, *args, **kwargs):
        logger.info("Comment create called")
        logger.info("User: %s (auth: %s)", getattr(request.user, "id", None), request.user.is_authenticated)
        logger.info("Content-Type: %s", request.content_type)
        logger.info("REQUEST DATA: %s", dict(request.data))
        logger.info("FILES keys: %s", list(request.FILES.keys()))

        if request.FILES:
            for k, f in request.FILES.items():
                try:
                    size = getattr(f, "size", None)
                except Exception:
                    size = None
                logger.info(" - FILE: %s, name=%s, size=%s, content_type=%s", 
                            k, getattr(f, "name", None), size, getattr(f, "content_type", None))

        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            logger.warning("Serializer invalid: %s", serializer.errors)
            return Response({
                "detail": "Invalid data",
                "errors": serializer.errors,
                "received_files": list(request.FILES.keys()),
                "received_data": dict(request.data),
            }, status=status.HTTP_400_BAD_REQUEST)

        publication = get_object_or_404(Publication, id=self.kwargs["pk"])

        self.perform_create(serializer, publication)
        headers = self.get_success_headers(serializer.data)

        logger.info("Comment created: %s", serializer.data.get("id"))
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer, publication):
        serializer.save(author=self.request.user, publication=publication)

    def get_serializer_context(self):
        return {"request": self.request}


class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        publication_id = self.kwargs["pk"]
        comment_id = self.kwargs["comment_id"]
        return get_object_or_404(Comment, id=comment_id, publication__id=publication_id)

    def get_serializer_context(self):
        return {"request": self.request}

    def update(self, request, *args, **kwargs):
        comment = self.get_object()
        if comment.author != request.user:
            return Response(
                {"detail": "Not authorized to edit this comment."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        comment = self.get_object()
        if comment.author != request.user:
            return Response(
                {"detail": "Not authorized to delete this comment."},
                status=status.HTTP_403_FORBIDDEN
            )
        comment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
