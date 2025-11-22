# tasks/urls.py
from django.urls import path
from .views import (
    TaskListCreateView,
    TaskDetailView,
    TaskReplyView,
    TaskInProgressView,
    EditorSearchView,
)

urlpatterns = [
    path('tasks/', TaskListCreateView.as_view(), name='task-list'),
    path('tasks/<int:pk>/', TaskDetailView.as_view(), name='task-detail'),
    path('tasks/<int:pk>/reply/', TaskReplyView.as_view(), name='task-reply'),
    path('tasks/<int:pk>/in-progress/', TaskInProgressView.as_view(), name='task-in-progress'),
    path('editors/', EditorSearchView.as_view(), name='editor-search'),
]