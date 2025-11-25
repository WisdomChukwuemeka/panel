from rest_framework import serializers
from .models import Conference
from publications.models import Publication

class PublicationMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publication
        fields = ["id", "title", "doi"]

class ConferenceSerializer(serializers.ModelSerializer):
    publications = PublicationMiniSerializer(many=True, read_only=True)

    class Meta:
        model = Conference
        fields = [
            "id", "name", "slug", "description", "type", "mode", "status",
            "start_date", "end_date", "location", "website", "banner",
            "organizer", "tags", "created_at", "updated_at", "publications"
        ]
