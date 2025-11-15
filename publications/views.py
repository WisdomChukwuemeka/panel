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
from django.db.models import DecimalField
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
        return request.user and request.user.is_authenticated and (request.user.role == 'admin' or request.user.role == 'editor')
    
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
                Q(doi__icontains=search) |
                Q(author__full_name__icontains=search) |
                Q(keywords__icontains=search)   
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

        # --- AUTHOR: Resubmit / Submit For Review (PENDING) ---
        if user == instance.author and data.get('status') == 'pending':
            
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
                    raise serializers.ValidationError("No free reviews available.")
                sub.free_reviews_used += 1
                sub.save()

            serializer.save(status='pending', is_free_review=is_free)
            return

        # --- AUTHOR: Save as draft ---
        if user == instance.author:
            # prevent overriding status or free-review
            data.pop('status', None)
            data.pop('is_free_review', None)
            serializer.save(**data)
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


# --------------------------------------------------------------
#  PublicationStatsView – now returns full paginated monthly data
#  and a list of users who paid both publication_fee + review_fee
# --------------------------------------------------------------
from django.db.models import Q, Sum, Count, Case, When, IntegerField, F, Value
from django.db.models.functions import Coalesce, TruncMonth
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import permissions
from .pagination import DashboardResultsPagination

class PublicationStatsView(APIView):
    permission_classes = [IsEditor]
    pagination_class = DashboardResultsPagination

    def get(self, request):
        # ── 1. Summary Stats ───────────────────────────────────────
        total_publications = Publication.objects.count()
        approved = Publication.objects.filter(status='approved').count()
        rejected = Publication.objects.filter(status='rejected').count()
        under_review = Publication.objects.filter(status='under_review').count()
        draft = Publication.objects.filter(status='draft').count()
        total_likes = Views.objects.filter(user_liked=True).count()
        total_dislikes = Views.objects.filter(user_disliked=True).count()


        # ── 2. Monthly Data (Paginated) ───────────────────────────
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

        monthly_results = [
            {
                'month': item['month'].strftime('%Y-%m') if item['month'] else 'N/A',
                'total': item['total'],
                'approved': item['approved'],
                'rejected': item['rejected'],
                'under_review': item['under_review'],
                'draft': item['draft'],
            } for item in monthly_paginated['results']
        ]

        monthly_data = {
            'count': monthly_paginated['count'],
            'next': monthly_paginated['next'],
            'previous': monthly_paginated['previous'],
            'results': monthly_results
        }

        # ── 3. Editors Actions (Paginated) ─────────────────────────
        editors_actions_qs = Publication.objects.exclude(editor=None)\
            .values('editor__full_name')\
            .annotate(
                approved=Count(Case(When(status='approved', then=1), output_field=IntegerField())),
                rejected=Count(Case(When(status='rejected', then=1), output_field=IntegerField())),
            ).order_by('editor__full_name')

        editors_paginator = self.pagination_class()
        editors_paginator.page_query_param = 'editors_page'
        editors_paginator.page_size_query_param = 'editors_size'
        editors_page = editors_paginator.paginate_queryset(editors_actions_qs, request)
        editors_actions_paginated = editors_paginator.get_paginated_response(editors_page).data
        editors_results = editors_actions_paginated['results']

        # ── 4. Total Payments & Subscriptions ─────────────────────
        total_pub_raw = Payment.objects.filter(
            status='success',
            payment_type='publication_fee'
        ).aggregate(
            total=Coalesce(Sum('amount'), Value(0), output_field=DecimalField(max_digits=14, decimal_places=2))
        )['total']

        # Review Fee: ₦3,000 per review
        total_rev_raw = Payment.objects.filter(
            status='success',
            payment_type='review_fee'
        ).aggregate(
            total=Coalesce(Sum('amount'), Value(0), output_field=DecimalField(max_digits=14, decimal_places=2))
        )['total']

        # Convert to float for frontend
        total_payments = float(total_pub_raw)
        total_subscriptions = float(total_rev_raw)

        # ── 5. ALL PAYMENTS (SUCCESS + PENDING) – PAGINATED ───────
        all_payments_qs = Payment.objects.filter(
            payment_type__in=['publication_fee', 'review_fee']
        ).select_related('user').order_by('-created_at')

        search = request.query_params.get('search')
        if search:
            all_payments_qs = all_payments_qs.filter(
                Q(user__full_name__icontains=search) |
                Q(user__email__icontains=search)
            )

        payments_paginator = self.pagination_class()
        payments_paginator.page_query_param = 'all_payments_page'
        payments_paginator.page_size_query_param = 'all_payments_size'
        payments_page = payments_paginator.paginate_queryset(all_payments_qs, request)
        payments_paginated = payments_paginator.get_paginated_response(payments_page).data

        all_payments_results = [
            {
                'id': p.id,
                'user': p.user.full_name if p.user and hasattr(p.user, 'full_name') else "Unknown",
                'type': p.get_payment_type_display() if hasattr(p, 'get_payment_type_display') else p.payment_type,
                'amount': float(p.amount) if p.amount else 0.0,
                'status': p.status or 'unknown',
                'status_display': p.get_status_display() if hasattr(p, 'get_status_display') else (p.status or 'Unknown'),
                'created_at': p.created_at.strftime('%Y-%m-%d %H:%M') if p.created_at else 'N/A',
            } for p in payments_page
        ]

        all_payments_data = {
            'count': payments_paginated['count'],
            'next': payments_paginated['next'],
            'previous': payments_paginated['previous'],
            'results': all_payments_results,
        }

        # DEBUG: Log actual counts
        logger.info(
            f"[STATS] Publication Fee: ₦{total_payments} "
            f"({Payment.objects.filter(status='success', payment_type='publication_fee').count()} payments) | "
            f"Review Fee: ₦{total_subscriptions} "
            f"{all_payments_results}"
            f"({Payment.objects.filter(status='success', payment_type='review_fee').count()} payments)"
        )

        # ── 5. Review Fee Payment Details (Paginated) ─────────────
        payment_details_qs = Payment.objects.filter(
            status='success', payment_type='review_fee'
        ).values('user__full_name')\
            .annotate(total_amount=Sum('amount'), count=Count('id'))\
            .order_by('user__full_name')

        payments_paginator = self.pagination_class()
        payments_paginator.page_query_param = 'payments_page'
        payments_paginator.page_size_query_param = 'payments_size'
        payments_page = payments_paginator.paginate_queryset(payment_details_qs, request)
        payment_details_paginated = payments_paginator.get_paginated_response(payments_page).data

        payments_results = [
            {
                'user__full_name': item['user__full_name'],
                'total_amount': float(item['total_amount']) if item['total_amount'] else 0.0,
                'count': item['count'],
            } for item in payment_details_paginated['results']
        ]

        # ── 6. Subscription Details (Paginated) ───────────────────
        subscription_details_qs = Subscription.objects.values(
            'user__full_name', 'free_reviews_used', 'free_reviews_granted'
        ).order_by('user__full_name')

        subs_paginator = self.pagination_class()
        subs_paginator.page_query_param = 'subs_page'
        subs_paginator.page_size_query_param = 'subs_size'
        subs_page = subs_paginator.paginate_queryset(subscription_details_qs, request)
        subscription_details_paginated = subs_paginator.get_paginated_response(subs_page).data
        subs_results = subscription_details_paginated['results']

        # ── 7. NEW: Users Who Paid BOTH Fees (with Amounts) ────────
        users_with_both_qs = User.objects.filter(
            payment__payment_type='publication_fee',
            payment__status='success'
        ).annotate(
            pub_fee=Coalesce(
                Sum('payment__amount', filter=Q(payment__payment_type='publication_fee', payment__status='success')),
                Value(0.0, output_field=DecimalField(max_digits=12, decimal_places=2))
            )
        ).filter(
            payment__payment_type='review_fee',
            payment__status='success'
        ).annotate(
            rev_fee=Coalesce(
                Sum('payment__amount', filter=Q(payment__payment_type='review_fee', payment__status='success')),
                Value(0.0, output_field=DecimalField(max_digits=12, decimal_places=2))
            )
        ).annotate(
            total=F('pub_fee') + F('rev_fee')
        ).values('id', 'full_name', 'pub_fee', 'rev_fee', 'total')\
        .order_by('full_name')

        users_paginator = self.pagination_class()
        users_paginator.page_query_param = 'users_page'
        users_paginator.page_size_query_param = 'users_size'
        users_page = users_paginator.paginate_queryset(users_with_both_qs, request)
        users_paginated = users_paginator.get_paginated_response(users_page).data

        users_results = [
            {
                'id': u['id'],
                'full_name': u['full_name'],
                'publication_fee': float(u['pub_fee']),
                'review_fee': float(u['rev_fee']),
                'total': float(u['total']),
            } for u in users_paginated['results']
        ]

        users_data = {
            'count': users_paginated['count'],
            'next': users_paginated['next'],
            'previous': users_paginated['previous'],
            'results': users_results,
        }

        # ── 8. Final Response ─────────────────────────────────────
        data = {
            'total_publications': total_publications,
            'approved': approved,
            'rejected': rejected,
            'under_review': under_review,
            'draft': draft,
            'total_likes': total_likes,
            'total_dislikes': total_dislikes,

            'monthly_data': monthly_data,  # Full paginated object
            'editors_actions': editors_results,
            'total_payments': total_payments,
            'total_subscriptions': total_subscriptions,
            'all_payments': all_payments_data,
            'payment_details': payments_results,
            'subscription_details': subs_results,

            # NEW: Users with both fees + amounts
            'users_with_both_fees': users_data,
        }
        return Response(data)