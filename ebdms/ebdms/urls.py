from django.urls import path
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static

from accounts.otp_views import admin_otp_verify
# from rest_framework import routers, serializers, viewsets


urlpatterns = [
    path("otp/verify/", admin_otp_verify, name="admin-otp-verify"),
    path("", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
