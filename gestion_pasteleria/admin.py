"""
Registro limpio y estándar de modelos en el Administrador de Django.
"""

from django.contrib import admin
from .models import (
    PerfilUsuario,
    Cliente,
    CategoriaInsumo,
    Insumo,
    ProductoPasteleria,
    ItemBOM,
    PedidoPersonalizado,
    InsumoExtraPedido,
    MovimientoInventario,
    HistorialKanban,
    RutaDespacho,
    DespachoPedido,
)


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'rol', 'rut', 'telefono', 'turno', 'activo')
    list_filter = ('rol', 'turno', 'activo')
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name', 'rut')


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre_completo', 'rut', 'tipo_cliente', 'telefono', 'email', 'comuna', 'preferencias_alimentarias')
    list_filter = ('tipo_cliente', 'comuna')
    search_fields = ('nombre_completo', 'rut', 'email', 'telefono')


@admin.register(CategoriaInsumo)
class CategoriaInsumoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'es_perecible', 'requiere_cadena_frio')
    list_filter = ('es_perecible', 'requiere_cadena_frio')
    search_fields = ('nombre', 'descripcion')


@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ('codigo_sku', 'nombre', 'categoria', 'stock_actual', 'stock_minimo', 'unidad_medida', 'costo_unitario', 'fecha_vencimiento', 'activo')
    list_filter = ('categoria', 'unidad_medida', 'activo')
    search_fields = ('codigo_sku', 'nombre', 'proveedor', 'lote_actual')


@admin.register(ProductoPasteleria)
class ProductoPasteleriaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'categoria_producto', 'porciones_base', 'precio_base', 'tiempo_elaboracion_horas', 'activo')
    list_filter = ('categoria_producto', 'requiere_refrigeracion', 'activo')
    search_fields = ('codigo', 'nombre', 'descripcion')


@admin.register(ItemBOM)
class ItemBOMAdmin(admin.ModelAdmin):
    list_display = ('producto', 'etapa_uso', 'insumo', 'cantidad_requerida', 'merma_tecnica_pct')
    list_filter = ('etapa_uso', 'producto')
    search_fields = ('producto__nombre', 'insumo__nombre', 'insumo__codigo_sku')


@admin.register(PedidoPersonalizado)
class PedidoPersonalizadoAdmin(admin.ModelAdmin):
    list_display = ('codigo_pedido', 'cliente', 'producto_base', 'porciones_solicitadas', 'estado_kanban', 'estado_comercial', 'insumos_descontados', 'precio_total', 'fecha_entrega_comprometida')
    list_filter = ('estado_kanban', 'estado_comercial', 'insumos_descontados', 'prioridad', 'modalidad_entrega')
    search_fields = ('codigo_pedido', 'cliente__nombre_completo', 'cliente__rut', 'sabor_bizcocho', 'relleno_principal')


@admin.register(InsumoExtraPedido)
class InsumoExtraPedidoAdmin(admin.ModelAdmin):
    list_display = ('pedido', 'insumo', 'cantidad_extra', 'motivo')
    search_fields = ('pedido__codigo_pedido', 'insumo__nombre', 'motivo')


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ('fecha_movimiento', 'tipo_movimiento', 'insumo', 'cantidad', 'stock_anterior', 'stock_resultante', 'pedido_asociado', 'usuario')
    list_filter = ('tipo_movimiento', 'fecha_movimiento')
    search_fields = ('insumo__nombre', 'insumo__codigo_sku', 'pedido_asociado__codigo_pedido', 'motivo')


@admin.register(HistorialKanban)
class HistorialKanbanAdmin(admin.ModelAdmin):
    list_display = ('fecha_cambio', 'pedido', 'estado_anterior', 'estado_nuevo', 'usuario', 'comentario')
    list_filter = ('estado_nuevo', 'fecha_cambio')
    search_fields = ('pedido__codigo_pedido', 'comentario')


@admin.register(RutaDespacho)
class RutaDespachoAdmin(admin.ModelAdmin):
    list_display = ('codigo_ruta', 'nombre_ruta', 'repartidor', 'vehiculo_patente', 'fecha_ruta', 'estado_ruta')
    list_filter = ('estado_ruta', 'vehiculo_refrigerado', 'fecha_ruta')
    search_fields = ('codigo_ruta', 'nombre_ruta', 'vehiculo_patente')


@admin.register(DespachoPedido)
class DespachoPedidoAdmin(admin.ModelAdmin):
    list_display = ('ruta', 'orden_parada', 'pedido', 'comuna_destino', 'ventana_horaria', 'estado_entrega', 'nombre_receptor', 'fecha_hora_confirmacion')
    list_filter = ('estado_entrega', 'comuna_destino')
    search_fields = ('pedido__codigo_pedido', 'direccion_destino', 'nombre_receptor', 'rut_receptor')
