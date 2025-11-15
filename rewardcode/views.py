# rewardcodes/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db import models  # ← Required for Sum()
from django.utils import timezone
import uuid

from .models import RewardCode
from .serializers import RewardCodeSerializer
from publications.models import Publication
from points.models import PointReward
from rest_framework import serializers as rest_serializers


class RewardCodeListCreateView(generics.ListCreateAPIView):
    serializer_class = RewardCodeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Only the owner of the publication can see their own codes."""
        publication_id = self.request.query_params.get('publication_id')
        user = self.request.user
        if publication_id:
            try:
                pub = Publication.objects.get(id=publication_id)
            except Publication.DoesNotExist:
                return RewardCode.objects.none()
            if pub.author != user:          # <-- owner only
                return RewardCode.objects.none()
        return RewardCode.objects.filter(user=user).order_by('-created_at')

    # -------------------------------------------------
    # 1. Owner qualifies when *commenters* give them 25 points
    # -------------------------------------------------
    def is_qualified(self, user):
        publication_id = self.request.query_params.get('publication_id')
        if not publication_id:
            return False
        try:
            pub = Publication.objects.get(id=publication_id, author=user)
        except Publication.DoesNotExist:
            return False

        # Points **received** by the owner (sum of PointReward on this pub)
        total = PointReward.objects.filter(publication=pub).aggregate(
            total=models.Sum('points')
        )['total'] or 0
        return total >= 25

    # -------------------------------------------------
    # 2. Create the code for the owner
    # -------------------------------------------------
    def perform_create(self, serializer):
        user = self.request.user
        publication_id = self.request.query_params.get('publication_id')
        if not publication_id:
            raise rest_serializers.ValidationError("publication_id required")

        if not self.is_qualified(user):
            raise rest_serializers.ValidationError(
                "You need at least 25 points on this publication."
            )

        # One active code per owner
        if RewardCode.objects.filter(
            user=user,
            redeemed=False,
            expires_at__gt=timezone.now()
        ).exists():
            raise rest_serializers.ValidationError(
                "You already have an active reward code."
            )

        serializer.save(user=user)


# ------------------------------------------------------------------
# Redeem a code
# ------------------------------------------------------------------
class RedeemCodeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        code_str = request.data.get('code')
        pub_id = request.data.get('publication_id')

        if not code_str or not pub_id:
            return Response(
                {"detail": "Both 'code' and 'publication_id' are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            code_uuid = uuid.UUID(code_str)
        except ValueError:
            return Response(
                {"detail": "Invalid code format."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Find active code belonging to the user
        code = get_object_or_404(
            RewardCode,
            code=code_uuid,
            user=request.user,
            redeemed=False,
            expires_at__gt=timezone.now()
        )

        # Ensure the publication belongs to the user
        pub = get_object_or_404(Publication, id=pub_id, author=request.user)

        # Mark publication as free review (or any reward logic)
        pub.is_free_review = True
        pub.save()

        # Mark code as redeemed
        code.redeemed = True
        code.redeemed_publication = pub
        code.save()

        return Response(
            {"detail": "Code redeemed successfully."},
            status=status.HTTP_200_OK
        )