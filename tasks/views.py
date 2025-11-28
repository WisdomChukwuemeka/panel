# tasks/views.py
from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
from django.contrib.auth import get_user_model
from rest_framework import status


from .models import Task
from .serializers import TaskSerializer, TaskReplySerializer, TaskInProgressSerializer
from .pagination import TaskPagination

User = get_user_model()


class IsAdminOrTaskAssigner(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.role == 'admin' or
            request.user.has_perm('tasks.can_assign_task')
        )



class IsTaskOwner(permissions.BasePermission):
    """Only assigned editor OR admin can access this task"""
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.has_perm('tasks.can_assign_task'):
            return True
        return obj.assigned_to == request.user
    
    
def get_task_queryset(request):
    user = request.user

    # Admin → see ALL tasks
    if user.role == 'admin' or user.is_staff:
        return Task.objects.all().order_by('-created_at')

    # Editor → see ONLY their assigned tasks
    if user.role == 'editor':
        return Task.objects.filter(assigned_to=user).order_by('-created_at')

    # Nobody else → nothing
    return Task.objects.none()



# Editor Search (Admin only)
class EditorSearchView(APIView):
    permission_classes = [IsAdminOrTaskAssigner]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        editors = User.objects.filter(role='editor', is_active=True)

        if q:
            editors = editors.filter(
                Q(email__icontains=q) |
                Q(full_name__icontains=q) 
            )

        editors = editors.order_by('full_name')[:20]

        data = [
            {
                "id": e.id,
                "email": e.email,
                "full_name": e.get_full_name() or e.email,
                "avatar": e.profile.picture.url if hasattr(e, 'profile') and e.profile.picture else None
            }
            for e in editors
        ]
        return Response(data)


# Task List + Create
class TaskListCreateView(generics.ListCreateAPIView):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = TaskPagination

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin' or user.is_staff:
            return Task.objects.all().select_related('assigned_by', 'assigned_to').order_by('-created_at')
        # Editor → only their tasks
        return Task.objects.filter(assigned_to=user).select_related('assigned_by', 'assigned_to').order_by('-created_at')
    # def perform_create(self, serializer):
    #     serializer.save(assigned_by=self.request.user)


# Task Detail
class TaskDetailView(generics.RetrieveAPIView):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsTaskOwner]
    lookup_field = 'pk'

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin' or user.is_staff:
            return Task.objects.all()
        return Task.objects.filter(assigned_to=user)

# Reply & Complete
class TaskReplyView(generics.UpdateAPIView):
    serializer_class = TaskReplySerializer
    permission_classes = [permissions.IsAuthenticated, IsTaskOwner]
    lookup_field = 'pk'

    def get_queryset(self):
        # Only assigned tasks for editors
        user = self.request.user
        if user.role == 'admin' or user.is_staff:
            return Task.objects.all()
        return Task.objects.filter(assigned_to=user)
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial, context={'request': request})
        
        try:
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response({"detail": "Task completed successfully"}, status=status.HTTP_200_OK)
        
        except ValueError as e:
            # Task already completed/rejected
            return Response({"reply_message": [str(e)]}, status=status.HTTP_400_BAD_REQUEST)

        except PermissionError as e:
            # Only assigned editor can complete task
            return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)

        except Exception as e:
            # Catch-all
            return Response({"detail": "Task not assigned to you, try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

# Mark as In Progress
class TaskInProgressView(generics.UpdateAPIView):
    serializer_class = TaskInProgressSerializer
    permission_classes = [permissions.IsAuthenticated, IsTaskOwner]
    lookup_field = 'pk'

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin' or user.is_staff:
            return Task.objects.all()
        return Task.objects.filter(assigned_to=user)