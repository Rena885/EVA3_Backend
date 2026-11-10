"""Configuración WSGI para el despliegue en AWS EC2 con Gunicorn."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dulce_arte_project.settings')
application = get_wsgi_application()
