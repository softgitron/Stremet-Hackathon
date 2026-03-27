from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import AllowAny

urlpatterns = [
    path('admin/', admin.site.urls), # The built-in Django database admin

    # OpenAPI 3.0 + versioned REST API (canonical: /api/v1/)
    path(
        'api/v1/schema/',
        SpectacularAPIView.as_view(permission_classes=[AllowAny]),
        name='api_schema',
    ),
    path(
        'api/v1/docs/',
        SpectacularSwaggerView.as_view(url_name='api_schema', permission_classes=[AllowAny]),
        name='swagger-ui',
    ),
    path('api/v1/', include('core.urls')),
    path('api/docs/', RedirectView.as_view(url='/api/v1/docs/', permanent=False)),
    path('api/schema/', RedirectView.as_view(url='/api/v1/schema/', permanent=False)),

    path('accounts/', include('django.contrib.auth.urls')),

    path('', include('home.urls')),
    path('portal/admin/', include('administrator.urls')),
    path('portal/customer/', include('customer.urls')),
    path('portal/production/', include('manufacturer.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)