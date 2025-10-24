from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework import serializers
from .models import Publication, Notification, Views
from .serializers import PublicationSerializer, NotificationSerializer, ViewsSerializer
from payments.models import Payment, Subscription
from .pagination import StandardResultsPagination, DashboardResultsPagination
from django.utils import timezone
from django.db import transaction
import logging
from accounts.models import User
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

logger = logging.getLogger(__name__)

# Custom permission for editors or authors
class IsAuthorOrEditor(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'editor':
            return True
        return obj.author == request.user

class IsEditor(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'editor'

class PublicationListCreateView(generics.ListCreateAPIView):
    serializer_class = PublicationSerializer
    pagination_class = StandardResultsPagination
    permission_classes = [permissions.IsAuthenticated]
    
    @method_decorator(csrf_exempt)  # Add this
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        search = self.request.query_params.get('search', None)
        if user.role == 'editor':
            return Publication.objects.all()  # Editors see all publications
        else: 
            queryset = Publication.objects.filter(
                Q(author=user) | Q(status='approved')
            )  # Authors and others see their own + approved publications

        # Optional search filter
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) |
                Q(abstract__icontains=search) |
                Q(author__full_name__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user, status='draft')  # Changed to 'draft' initially
        logger.info(f"Publication created by {self.request.user.full_name}: {serializer.instance.id}")

class PublicationDetailView(generics.RetrieveAPIView):
    serializer_class = PublicationSerializer
    pagination_class = StandardResultsPagination
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        user = self.request.user
        logger.info(f"User: {user.full_name}, Role: {user.role}, Fetching publication with pk: {self.kwargs.get('pk')}")
        if user.role == 'editor':
            return Publication.objects.all()
        return Publication.objects.filter(
            Q(author=user) | Q(status='approved')
        )

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        logger.info(f"Retrieved publication: {instance.id}, views: {getattr(instance, 'views', 'N/A')}")
        try:
            view, created = Views.objects.get_or_create(publication=instance, user=request.user)
            if created or not view.viewed:
                views_attr = getattr(instance, 'views', None)
                if views_attr is None:
                    raise AttributeError("Publication model missing 'views' field")
                instance.views += 1
                view.viewed = True
                view.save()
                instance.save()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except AttributeError as e:
            logger.error(f"AttributeError in retrieve: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"Unexpected error in retrieve: {str(e)}")
            return Response({"detail": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PublicationUpdateView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PublicationSerializer
    pagination_class = StandardResultsPagination
    permission_classes = [permissions.IsAuthenticated, IsAuthorOrEditor]
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user
        if user.role == 'editor':
            return Publication.objects.all()
        return Publication.objects.filter(author=user)

    def validate_status_transition(self, instance, new_status):
        valid_transitions = {
            'draft': ['pending'],
            'pending': ['under_review'],
            'under_review': ['approved', 'rejected'],
            'rejected': ['pending'],
            'approved': []
        }
        if new_status != instance.status and new_status not in valid_transitions.get(instance.status, []):
            raise serializers.ValidationError({
                "status": f"Cannot transition from {instance.status} to {new_status}."
            })

    @transaction.atomic
    def perform_update(self, serializer):
        instance = serializer.instance
        old_status = instance.status
        new_status = serializer.validated_data.get('status', old_status)
        is_free_review = serializer.validated_data.get('is_free_review', instance.is_free_review)
        rejection_note = serializer.validated_data.get('rejection_note', instance.rejection_note)

        # Validate status transition
        self.validate_status_transition(instance, new_status)

        # Log update details
        logger.info(f"Updating publication {instance.id} by user {self.request.user.id} ({self.request.user.full_name}): "
                    f"status={new_status}, fields={list(serializer.validated_data.keys())}")

        # Validate editor actions
        if self.request.user.role == 'editor':
            if new_status not in ['under_review', 'approved', 'rejected']:
                raise serializers.ValidationError({
                    "status": "Editors can only set status to 'under_review', 'approved', or 'rejected'."
                })
            if new_status == 'rejected' and not rejection_note:
                raise serializers.ValidationError({
                    "rejection_note": "A rejection note is required when rejecting a publication."
                })
            if new_status == 'rejected':
                instance.rejection_count += 1
            if not instance.editor:
                instance.editor = self.request.user
            if new_status == 'approved':
                instance.publication_date = timezone.now()

        # Handle author submission/resubmission (set to 'pending')
        elif self.request.user == instance.author and new_status == 'pending':
            if instance.rejection_count == 0:
                payment = Payment.objects.filter(
                    user=self.request.user,
                    payment_type='publication_fee',
                    metadata__publication_id=str(instance.id),
                    status='success',
                    used=False
                ).first()
                if not payment:
                    raise serializers.ValidationError({
                        "status": "Payment for publication fee (₦25,000) is required for initial submission."
                    })
                payment.used = True
                payment.save()
                sub, created = Subscription.objects.get_or_create(user=self.request.user)
                sub.free_reviews_granted = True
                sub.save()
            else:
                if is_free_review:
                    sub, created = Subscription.objects.get_or_create(user=self.request.user)
                    if not sub.has_free_review_available():
                        raise serializers.ValidationError({
                            "is_free_review": "No free reviews available."
                        })
                    sub.use_free_review()
                else:
                    payment = Payment.objects.filter(
                        user=self.request.user,
                        payment_type='review_fee',
                        metadata__publication_id=str(instance.id),
                        status='success',
                        used=False
                    ).first()
                    if not payment:
                        raise serializers.ValidationError({
                            "status": "Payment for review fee (₦3,000) is required after free reviews are exhausted."
                        })
                    payment.used = True
                    payment.save()

        # Save editor-specific fields (other fields handled by serializer.update)
        serializer.save(
            editor=instance.editor,
            publication_date=instance.publication_date,
            rejection_count=instance.rejection_count
        )
        print(serializer.errors)  # Add this

        # Create notification for status change
        if new_status != old_status:
            message = f"Your publication '{instance.title}' has been {new_status.replace('_', ' ')}."
            if new_status == 'rejected' and rejection_note:
                message += f" Reason: {rejection_note}"
            Notification.objects.create(
                user=instance.author,
                message=message,
                related_publication=instance
            )
            logger.info(f"Notification created for {instance.author.full_name}: {message}")

            # Notify other editors if approved, rejected, or under_review
            if new_status in ['approved', 'rejected', 'under_review'] and self.request.user.role == 'editor':
                editors = User.objects.filter(role='editor').exclude(id=self.request.user.id)
                notifications = [
                    Notification(
                        user=editor,
                        message=(
                            f"Publication '{instance.title}' was {new_status} by "
                            f"{self.request.user.full_name} at {timezone.now().strftime('%I:%M %p WAT, %B %d, %Y')}."
                            + (f" Reason: {rejection_note}" if new_status == 'rejected' and rejection_note else "")
                        ),
                        related_publication=instance
                    )
                    for editor in editors
                ]
                Notification.objects.bulk_create(notifications)
                logger.info(f"Notifications created for {len(notifications)} editors")

class ViewsUpdateView(generics.UpdateAPIView):
    serializer_class = ViewsSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = None

    def get_object(self):
        publication = get_object_or_404(Publication, id=self.kwargs['pk'])
        view, created = Views.objects.get_or_create(publication=publication, user=self.request.user)
        return view

class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = DashboardResultsPagination

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

class NotificationMarkReadView(generics.UpdateAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(is_read=True)

class NotificationUnreadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({'unread_count': count})

class NotificationMarkAllReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'detail': 'All notifications marked as read.'}, status=status.HTTP_200_OK)

class FreeReviewStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        sub, _ = Subscription.objects.get_or_create(user=request.user)
        return Response({
            'free_reviews_granted': sub.free_reviews_granted,
            'free_reviews_used': sub.free_reviews_used,
            'has_free_review_available': sub.has_free_review_available()
        })