"""
Definición principal de URLs para Dulce Arte.
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from gestion_pasteleria.views import error_404_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('gestion_pasteleria.api_urls')),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('', include('gestion_pasteleria.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Ruta comodín para capturar cualquier URL inexistente tanto en modo DEBUG como en Producción
urlpatterns += [
    re_path(r'^.*$', error_404_view),
]

# Manejador global para excepciones Http404 lanzadas desde las vistas
handler404 = 'gestion_pasteleria.views.error_404_view'


