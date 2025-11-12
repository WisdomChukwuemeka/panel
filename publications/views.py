from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework import serializers
from .models import Publication, Notification, Views, ReviewHistory
from .serializers import PublicationSerializer, ReviewHistorySerializer, NotificationSerializer, ViewsSerializer, StatsSerializer
from payments.models import Payment, Subscription
from .pagination import StandardResultsPagination, DashboardResultsPagination
from django.utils import timezone
from django.db import transaction
import logging
from accounts.models import User
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db.models.functions import TruncMonth
from django.db.models import Count, Case, When, IntegerField, Sum

logger = logging.getLogger(__name__)

# Custom permission for editors or authors
class IsAuthorOrEditor(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'editor':
            return True
        return obj.author == request.user

class IsEditor(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.role == 'admin' or request.user.role == 'editor' 

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
            queryset = Publication.objects.all()  # Editors see all publications
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

# views.py
# views.py
# views.py
class PublicationUpdateView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PublicationSerializer
    permission_classes = [permissions.IsAuthenticated, IsAuthorOrEditor]
    lookup_field = 'id'
    queryset = Publication.objects.all()

    def get_queryset(self):
        user = self.request.user
        if user.role == 'editor':
            return Publication.objects.all()
        return Publication.objects.filter(author=user)

    @transaction.atomic
    def perform_update(self, serializer):
        instance = self.get_object()
        user = self.request.user
        data = serializer.validated_data.copy()

        # AUTHOR: Save as Draft
        if user == instance.author:
            data.pop('status', None)
            data.pop('is_free_review', None)
            serializer.save(**data)
            return

        # AUTHOR: Resubmit
        if data.get('status') == 'pending' and user == instance.author:
            if instance.status != 'rejected':
                raise serializers.ValidationError("Only rejected publications can be resubmitted.")

            has_paid = Payment.objects.filter(
                user=user,
                payment_type='review_fee',
                metadata__publication_id=str(instance.id),
                status='success'
            ).exists()

            is_free = data.get('is_free_review', False)
            if not has_paid and not is_free:
                raise serializers.ValidationError("Payment of ₦3,000 required.")

            if is_free:
                sub = Subscription.objects.get(user=user)
                if not sub.has_free_review_available():
                    raise serializers.ValidationError("No free reviews.")
                sub.free_reviews_used += 1
                sub.save()

            serializer.save(status='pending', is_free_review=is_free)
            return

        raise serializers.ValidationError("Use /review/ endpoint.")

# views.py
class EditorReviewView(APIView):
    permission_classes = [IsEditor]

    def post(self, request, id):
        pub = get_object_or_404(Publication, id=id)
        action = request.data.get('action')
        note = request.data.get('rejection_note', '').strip()

        if action not in ['under_review', 'approve', 'reject']:
            return Response({"detail": "Invalid action"}, status=400)

        if action == 'reject' and not note:
            return Response({"detail": "Rejection note required"}, status=400)
   
    # 🔒 Prevent changing Approved or Rejected publications
        if pub.status in ['approved', 'rejected']:
            return Response(
                {"detail": f"Cannot modify a publication that is already {pub.status}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # === FIXED: Now properly indented inside the method ===
        action_map = {
            'under_review': 'under_review',
            'approve': 'approved',
            'reject': 'rejected'
        }
        review_action = action_map[action]

        old_status = pub.status

        if action == 'reject':
            pub.status = 'rejected'
            pub.rejection_count += 1
            pub.rejection_note = note
        elif action == 'approve':
            pub.status = 'approved'
            pub.publication_date = timezone.now()
        else:  # under_review
            pub.status = 'under_review'

        pub.editor = request.user
        pub.save()  # This triggers your save() override too

        # THIS WILL NOW WORK
        ReviewHistory.objects.create(
            publication=pub,
            editor=request.user,
            action=review_action,
            note=note if action == 'reject' else None
        )

        # Notify author
        Notification.objects.create(
            user=pub.author,
            message=f"Your publication '{pub.title}' has been {pub.get_status_display().lower()}.",
            related_publication=pub
        )

        return Response({
            "detail": "Success",
            "status": pub.status,
            "review_history_created": True
        })
        
# views.py (add this new view)
class EditorActivitiesView(generics.ListAPIView):
    serializer_class = ReviewHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        queryset = ReviewHistory.objects.select_related('publication', 'publication__author', 'editor').order_by('-timestamp')
        if self.request.user.role == 'admin':
            editor_id = self.request.query_params.get('editor_id')
            if editor_id:
                queryset = queryset.filter(editor__id=editor_id)
        elif self.request.user.role == 'editor':
            queryset = queryset.filter(editor=self.request.user)
        else:
            raise serializers.ValidationError("You do not have permission to access this resource.")
        
        publication_id = self.request.query_params.get('publication_id')
        if publication_id:
            queryset = queryset.filter(publication__id=publication_id)
        
        from_date = self.request.query_params.get('from_date')
        if from_date:
            queryset = queryset.filter(timestamp__gte=from_date)
        
        to_date = self.request.query_params.get('to_date')
        if to_date:
            queryset = queryset.filter(timestamp__lte=to_date)
        
        action = self.request.query_params.get('action')
        if action:
            queryset = queryset.filter(action=action)
        
        return queryset

        
class ViewsUpdateView(generics.UpdateAPIView):
    serializer_class = ViewsSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = None

    def get_object(self):
        publication = get_object_or_404(Publication, id=self.kwargs['pk'])
        view, created = Views.objects.get_or_create(publication=publication, user=self.request.user)
        return view

class PublicationLikeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        publication = get_object_or_404(Publication, id=pk)
        view, created = Views.objects.get_or_create(publication=publication, user=request.user)

        if view.user_liked:
            # Toggle off like
            view.user_liked = False
        else:
            # Like and remove any existing dislike
            view.user_liked = True
            view.user_disliked = False

        view.save()
        logger.info(f"{request.user.full_name} {'liked' if view.user_liked else 'unliked'} publication {publication.id}")

        return Response({
            "total_likes": publication.total_likes(),
            "total_dislikes": publication.total_dislikes(),
            "user_liked": view.user_liked,
            "user_disliked": view.user_disliked
        }, status=status.HTTP_200_OK)


class PublicationDislikeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        publication = get_object_or_404(Publication, id=pk)
        view, created = Views.objects.get_or_create(publication=publication, user=request.user)

        if view.user_disliked:
            # Toggle off dislike
            view.user_disliked = False
        else:
            # Dislike and remove any existing like
            view.user_disliked = True
            view.user_liked = False

        view.save()
        logger.info(f"{request.user.full_name} {'disliked' if view.user_disliked else 'undisliked'} publication {publication.id}")

        return Response({
            "total_likes": publication.total_likes(),
            "total_dislikes": publication.total_dislikes(),
            "user_liked": view.user_liked,
            "user_disliked": view.user_disliked
        }, status=status.HTTP_200_OK)


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
        
class PublicationAnnotateView(generics.UpdateAPIView):
    serializer_class = PublicationSerializer
    permission_classes = [IsEditor]
    lookup_field = 'id'

    def get_queryset(self):
        return Publication.objects.all()

    def perform_update(self, serializer):
        instance = serializer.instance
        annotated_file = self.request.FILES.get('annotated_file')
        comments = self.request.data.get('editor_comments')

        if annotated_file:
            serializer.save(annotated_file=annotated_file, editor_comments=comments)
        else:
            serializer.save(editor_comments=comments)
        return instance
    
class StatsSerializer(serializers.Serializer):
    total_publications = serializers.IntegerField()
    approved = serializers.IntegerField()
    rejected = serializers.IntegerField()
    under_review = serializers.IntegerField()
    draft = serializers.IntegerField()
    total_likes = serializers.IntegerField()
    total_dislikes = serializers.IntegerField()
    monthly_data = serializers.DictField()
    editors_actions = serializers.DictField()
    total_payments = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_subscriptions = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_details = serializers.DictField()
    subscription_details = serializers.DictField()

class PublicationStatsView(APIView):
    permission_classes = [IsEditor]
    pagination_class = DashboardResultsPagination

    def get(self, request):
        total_publications = Publication.objects.count()
        approved = Publication.objects.filter(status='approved').count()
        rejected = Publication.objects.filter(status='rejected').count()
        under_review = Publication.objects.filter(status='under_review').count()
        draft = Publication.objects.filter(status='draft').count()
        total_likes = Views.objects.filter(user_liked=True).count()
        total_dislikes = Views.objects.filter(user_disliked=True).count()

        # Paginated monthly data
        monthly_qs = Publication.objects.annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            total=Count('id'),
            approved=Count(Case(When(status='approved', then=1), output_field=IntegerField())),
            rejected=Count(Case(When(status='rejected', then=1), output_field=IntegerField())),
            under_review=Count(Case(When(status='under_review', then=1), output_field=IntegerField())),
            draft=Count(Case(When(status='draft', then=1), output_field=IntegerField())),
        ).order_by('month')
        monthly_paginator = self.pagination_class()
        monthly_paginator.page_query_param = 'monthly_page'
        monthly_paginator.page_size_query_param = 'monthly_size'
        monthly_page = monthly_paginator.paginate_queryset(monthly_qs, request)
        monthly_paginated = monthly_paginator.get_paginated_response(monthly_page).data

        # Paginated editors actions
        editors_actions_qs = Publication.objects.exclude(editor=None).values('editor__full_name').annotate(
            approved=Count(Case(When(status='approved', then=1), output_field=IntegerField())),
            rejected=Count(Case(When(status='rejected', then=1), output_field=IntegerField())),
        ).order_by('editor__full_name')
        editors_paginator = self.pagination_class()
        editors_paginator.page_query_param = 'editors_page'
        editors_paginator.page_size_query_param = 'editors_size'
        editors_page = editors_paginator.paginate_queryset(editors_actions_qs, request)
        editors_actions_paginated = editors_paginator.get_paginated_response(editors_page).data

        total_payments = Payment.objects.filter(status='success', payment_type='publication_fee').aggregate(total=Sum('amount'))['total']
        total_subscriptions = Payment.objects.filter(status='success', payment_type='review_fee').aggregate(total=Sum('amount'))['total'] 

        # Paginated payment details
        payment_details_qs = Payment.objects.filter(status='success').values('user__full_name', 'payment_type').annotate(
            total_amount=Sum('amount'), count=Count('id')
        ).order_by('user__full_name')
        payments_paginator = self.pagination_class()
        payments_paginator.page_query_param = 'payments_page'
        payments_paginator.page_size_query_param = 'payments_size'
        payments_page = payments_paginator.paginate_queryset(payment_details_qs, request)
        payment_details_paginated = payments_paginator.get_paginated_response(payments_page).data

        # Paginated subscription details
        subscription_details_qs = Subscription.objects.values('user__full_name', 'free_reviews_used', 'free_reviews_granted').order_by('user__full_name')
        subs_paginator = self.pagination_class()
        subs_paginator.page_query_param = 'subs_page'
        subs_paginator.page_size_query_param = 'subs_size'
        subs_page = subs_paginator.paginate_queryset(subscription_details_qs, request)
        subscription_details_paginated = subs_paginator.get_paginated_response(subs_page).data

        data = {
            'total_publications': total_publications,
            'approved': approved,
            'rejected': rejected,
            'under_review': under_review,
            'draft': draft,
            'total_likes': total_likes,
            'total_dislikes': total_dislikes,
            'monthly_data': monthly_paginated,
            'editors_actions': editors_actions_paginated,
            'total_payments': total_payments,
            'total_subscriptions': total_subscriptions,
            'payment_details': payment_details_paginated,
            'subscription_details': subscription_details_paginated,
        }
        serializer = StatsSerializer(data=data)
        if serializer.is_valid():
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)