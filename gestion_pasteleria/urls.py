"""
Rutas Web Fullstack de la aplicación gestion_pasteleria (Dulce Arte).
"""
from django.urls import path
from . import views

urlpatterns = [
    # Autenticación y Sesiones
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('cambiar-rol-demo/', views.cambiar_rol_demo_view, name='cambiar_rol_demo'),

    # Dashboard General End-to-End
    path('', views.dashboard_view, name='dashboard'),

    # Funcionalidad 1: Cotización y Pedidos Personalizados + Clientes
    path('pedidos/', views.pedidos_list_view, name='pedidos_list'),
    path('pedidos/nuevo/', views.pedido_crear_view, name='pedido_crear'),
    path('pedidos/<int:pk>/', views.pedido_detalle_view, name='pedido_detalle'),
    path('pedidos/<int:pk>/editar/', views.pedido_editar_view, name='pedido_editar'),
    path('pedidos/<int:pk>/eliminar/', views.pedido_eliminar_view, name='pedido_eliminar'),
    path('clientes/', views.clientes_view, name='clientes_list'),

    # Funcionalidad 2: Tablero Kanban Digital del Taller de Cocina
    path('cocina/kanban/', views.kanban_cocina_view, name='kanban_cocina'),

    # Funcionalidad 3: Bodega de Insumos y Lista de Materiales (BOM)
    path('bodega/bom/', views.inventario_bom_view, name='inventario_bom'),

    # Funcionalidad 4: Rutas de Despacho y Confirmación con Firma Digital / Foto
    path('logistica/rutas/', views.rutas_despacho_view, name='rutas_despacho'),
    path('logistica/entregas/<int:pk>/confirmar/', views.confirmar_entrega_view, name='confirmar_entrega'),

    # Centro de Administración Integral (Todo el Admin en la misma página web)
    path('administracion/', views.administracion_unificada_view, name='centro_admin'),
]
