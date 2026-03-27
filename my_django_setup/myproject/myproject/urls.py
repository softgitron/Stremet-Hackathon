from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls), # The built-in Django database admin
    
    # Your 4 Custom Apps
    path('', include('home.urls')), 
    path('portal/admin/', include('administrator.urls')),
    path('portal/customer/', include('customer.urls')),
    path('portal/production/', include('manufacturer.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)