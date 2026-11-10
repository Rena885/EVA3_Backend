"""
Context Processors para inyectar indicadores clave (KPIs) y metadatos de
trazabilidad en todas las vistas web y en los templates personalizados de Django Admin.
"""
from django.conf import settings
from django.db.models import F
from .models import (
    Insumo,
    PedidoPersonalizado,
    RutaDespacho,
    DespachoPedido,
)


def dulce_arte_kpis(request):
    """Retorna métricas globales para la barra superior y el panel administrativo."""
    if not request.user.is_authenticated:
        return {
            'AWS_EC2_PUBLIC_IP': getattr(settings, 'AWS_EC2_PUBLIC_IP', 'AWS EC2'),
            'DB_ENGINE_ACTIVE': settings.DATABASES['default']['ENGINE'].split('.')[-1].upper(),
        }

    try:
        insumos_alerta = Insumo.objects.filter(
            activo=True, stock_actual__lte=F('stock_minimo')
        ).count()
        pedidos_en_cocina = PedidoPersonalizado.objects.exclude(
            estado_comercial__in=['ENTREGADO', 'CANCELADO']
        ).count()
        pedidos_listos = PedidoPersonalizado.objects.filter(
            estado_kanban='LISTO',
            estado_comercial__in=['EN_PRODUCCION', 'LISTO_DESPACHO'],
        ).count()
        entregas_pendientes = DespachoPedido.objects.filter(
            estado_entrega__in=['PENDIENTE', 'EN_CAMINO']
        ).count()
        rutas_activas = RutaDespacho.objects.filter(
            estado_ruta__in=['PLANIFICADA', 'EN_RUTA']
        ).count()
        rol_usuario = 'ADMIN' if request.user.is_superuser else 'VENTAS'
        if hasattr(request.user, 'perfil'):
            rol_usuario = request.user.perfil.rol
    except Exception:
        insumos_alerta = 0
        pedidos_en_cocina = 0
        pedidos_listos = 0
        entregas_pendientes = 0
        rutas_activas = 0
        rol_usuario = 'ADMIN'

    return {
        'KPI_INSUMOS_ALERTA': insumos_alerta,
        'KPI_PEDIDOS_COCINA': pedidos_en_cocina,
        'KPI_PEDIDOS_LISTOS': pedidos_listos,
        'KPI_ENTREGAS_PENDIENTES': entregas_pendientes,
        'KPI_RUTAS_ACTIVAS': rutas_activas,
        'ROL_USUARIO_ACTUAL': rol_usuario,
        'AWS_EC2_PUBLIC_IP': getattr(settings, 'AWS_EC2_PUBLIC_IP', 'AWS EC2'),
        'DB_ENGINE_ACTIVE': settings.DATABASES['default']['ENGINE'].split('.')[-1].upper(),
    }
