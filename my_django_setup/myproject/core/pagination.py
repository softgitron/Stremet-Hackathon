from rest_framework.pagination import PageNumberPagination


class StandardResultsPagination(PageNumberPagination):
    """Standard list pagination: `page`, `page_size` (capped)."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100
