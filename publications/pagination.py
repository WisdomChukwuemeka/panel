# pagination.py
from rest_framework.pagination import PageNumberPagination

class StandardResultsPagination(PageNumberPagination):
    page_size = 6  # Default items per page
    page_size_query_param = 'page_size'  # Allow frontend to control per-page size (optional)
    max_page_size = 100  # Limit maximum


class DashboardResultsPagination(PageNumberPagination):
    page_size = 3  # Default items per page
    page_size_query_param = 'page_size'  # Allow frontend to control per-page size (optional)
    max_page_size = 1000  # Limit maximum
