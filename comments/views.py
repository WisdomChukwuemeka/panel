from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Comment
from .serializers import CommentSerializer
from publications.models import Publication, Notification

class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None  # Disable pagination to return all comments

    def get_queryset(self):
        publication_id = self.kwargs["pk"]
        return Comment.objects.filter(publication__id=publication_id).order_by("created_at")

    def perform_create(self, serializer):
        publication = get_object_or_404(Publication, id=self.kwargs["pk"])
        serializer.save(author=self.request.user, publication=publication)

        # Notify the publication author if the commenter is not the author
        if publication.author != self.request.user:
            Notification.objects.create(
                user=publication.author,
                message=f"A new comment has been added to your publication '{publication.title}' by {self.request.user.get_full_name() or self.request.user.email}.",
                related_publication=publication
            )

class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        publication_id = self.kwargs["pk"]
        comment_id = self.kwargs["comment_id"]
        return get_object_or_404(Comment, id=comment_id, publication__id=publication_id)

    def update(self, request, *args, **kwargs):
        comment = self.get_object()
        if comment.author != request.user:
            return Response({"detail": "Not authorized to edit this comment."}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        comment = self.get_object()
        if comment.author != request.user:
            return Response({"detail": "Not authorized to delete this comment."}, status=status.HTTP_403_FORBIDDEN)
        comment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
