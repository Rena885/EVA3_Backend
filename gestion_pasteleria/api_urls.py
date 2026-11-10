"""
Rutas del API REST (DRF Router) bajo el prefijo /api/v1/.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import (
    ClienteViewSet,
    CategoriaInsumoViewSet,
    InsumoViewSet,
    ProductoPasteleriaViewSet,
    ItemBOMViewSet,
    PedidoPersonalizadoViewSet,
    InsumoExtraPedidoViewSet,
    MovimientoInventarioViewSet,
    RutaDespachoViewSet,
    DespachoPedidoViewSet,
)

router = DefaultRouter()
router.register(r'clientes', ClienteViewSet, basename='api-clientes')
router.register(r'categorias-insumo', CategoriaInsumoViewSet, basename='api-categorias-insumo')
router.register(r'insumos', InsumoViewSet, basename='api-insumos')
router.register(r'productos', ProductoPasteleriaViewSet, basename='api-productos')
router.register(r'items-bom', ItemBOMViewSet, basename='api-items-bom')
router.register(r'pedidos', PedidoPersonalizadoViewSet, basename='api-pedidos')
router.register(r'insumos-extra', InsumoExtraPedidoViewSet, basename='api-insumos-extra')
router.register(r'movimientos-inventario', MovimientoInventarioViewSet, basename='api-movimientos-inventario')
router.register(r'rutas-despacho', RutaDespachoViewSet, basename='api-rutas-despacho')
router.register(r'despachos', DespachoPedidoViewSet, basename='api-despachos')

urlpatterns = [
    path('', include(router.urls)),
]
