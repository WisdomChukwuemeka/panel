from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Conference
from .serializers import ConferenceSerializer
from .permissions import IsAdminUser
from .pagination import StandardResultsSetPagination   # ← ADD THIS


# Anyone authenticated can LIST conferences
class ConferenceListView(generics.ListAPIView):
    queryset = Conference.objects.all()
    serializer_class = ConferenceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination      # ← ADD THIS


# Anyone authenticated can VIEW a conference
class ConferenceDetailView(generics.RetrieveAPIView):
    queryset = Conference.objects.all()
    serializer_class = ConferenceSerializer
    lookup_field = 'id'
    permission_classes = [IsAuthenticated]


# Only Admin can CREATE
class ConferenceCreateView(generics.CreateAPIView):
    queryset = Conference.objects.all()
    serializer_class = ConferenceSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user)


# Only Admin can UPDATE
class ConferenceUpdateView(generics.UpdateAPIView):
    queryset = Conference.objects.all()
    serializer_class = ConferenceSerializer
    lookup_field = 'id'
    permission_classes = [IsAuthenticated, IsAdminUser]


# Only Admin can DELETE
class ConferenceDeleteView(generics.DestroyAPIView):
    queryset = Conference.objects.all()
    lookup_field = 'id'
    permission_classes = [IsAuthenticated, IsAdminUser]
