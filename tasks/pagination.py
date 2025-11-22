# tasks/pagination.py
from rest_framework.pagination import PageNumberPagination

class TaskPagination(PageNumberPagination):
    page_size = 10  # Default number of items per page
    page_size_query_param = 'page_size'  # Query param to override page size (e.g., ?page_size=20)
    max_page_size = 100  # Maximum allowed page size to prevent abuse