"""
Serializadores de Django REST Framework (DRF) para el sistema Dulce Arte.
Expone representaciones JSON enriquecidas con propiedades calculadas de BOM,
Kanban y Despacho Logístico.
"""

from rest_framework import serializers
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


class PerfilUsuarioSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='usuario.username', read_only=True)
    nombre_completo = serializers.SerializerMethodField()
    rol_display = serializers.CharField(source='get_rol_display', read_only=True)

    class Meta:
        model = PerfilUsuario
        fields = [
            'id',
            'username',
            'nombre_completo',
            'rol',
            'rol_display',
            'rut',
            'telefono',
            'turno',
            'especialidad_pastelera',
            'activo',
        ]

    def get_nombre_completo(self, obj):
        return obj.usuario.get_full_name() or obj.usuario.username


class ClienteSerializer(serializers.ModelSerializer):
    tipo_cliente_display = serializers.CharField(source='get_tipo_cliente_display', read_only=True)

    class Meta:
        model = Cliente
        fields = '__all__'


class CategoriaInsumoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriaInsumo
        fields = '__all__'


class InsumoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)
    en_alerta_stock = serializers.BooleanField(read_only=True)
    alerta_vencimiento = serializers.CharField(read_only=True)
    dias_para_vencer = serializers.IntegerField(read_only=True)
    valor_inventario_total = serializers.DecimalField(max_digits=14, decimal_places=0, read_only=True)

    class Meta:
        model = Insumo
        fields = '__all__'


class ItemBOMSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source='insumo.nombre', read_only=True)
    insumo_sku = serializers.CharField(source='insumo.codigo_sku', read_only=True)
    unidad_medida = serializers.CharField(source='insumo.unidad_medida', read_only=True)
    etapa_uso_display = serializers.CharField(source='get_etapa_uso_display', read_only=True)
    cantidad_con_merma = serializers.DecimalField(max_digits=10, decimal_places=3, read_only=True)
    costo_linea = serializers.DecimalField(max_digits=12, decimal_places=0, read_only=True)

    class Meta:
        model = ItemBOM
        fields = '__all__'


class ProductoPasteleriaSerializer(serializers.ModelSerializer):
    categoria_display = serializers.CharField(source='get_categoria_producto_display', read_only=True)
    costo_bom_base = serializers.DecimalField(max_digits=12, decimal_places=0, read_only=True)
    margen_bruto_pct = serializers.DecimalField(max_digits=5, decimal_places=1, read_only=True)
    items_bom = ItemBOMSerializer(many=True, read_only=True)

    class Meta:
        model = ProductoPasteleria
        fields = '__all__'


class InsumoExtraPedidoSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source='insumo.nombre', read_only=True)
    unidad_medida = serializers.CharField(source='insumo.unidad_medida', read_only=True)
    costo_extra = serializers.DecimalField(max_digits=12, decimal_places=0, read_only=True)

    class Meta:
        model = InsumoExtraPedido
        fields = '__all__'


class HistorialKanbanSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = HistorialKanban
        fields = '__all__'

    def get_usuario_nombre(self, obj):
        if not obj.usuario:
            return 'Sistema'
        return obj.usuario.get_full_name() or obj.usuario.username


class PedidoPersonalizadoSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre_completo', read_only=True)
    cliente_rut = serializers.CharField(source='cliente.rut', read_only=True)
    producto_nombre = serializers.CharField(source='producto_base.nombre', read_only=True)
    estado_kanban_display = serializers.CharField(source='get_estado_kanban_display', read_only=True)
    estado_comercial_display = serializers.CharField(source='get_estado_comercial_display', read_only=True)
    factor_escala_porciones = serializers.DecimalField(max_digits=8, decimal_places=3, read_only=True)
    porcentaje_avance_kanban = serializers.IntegerField(read_only=True)
    saldo_pendiente = serializers.DecimalField(max_digits=12, decimal_places=0, read_only=True)
    en_riesgo_atraso = serializers.BooleanField(read_only=True)
    insumos_extra = InsumoExtraPedidoSerializer(many=True, read_only=True)
    historial_kanban = HistorialKanbanSerializer(many=True, read_only=True)

    class Meta:
        model = PedidoPersonalizado
        fields = '__all__'
        read_only_fields = ['codigo_pedido', 'fecha_creacion', 'fecha_descuento_bom', 'actualizado_en']


class MovimientoInventarioSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source='insumo.nombre', read_only=True)
    insumo_sku = serializers.CharField(source='insumo.codigo_sku', read_only=True)
    unidad_medida = serializers.CharField(source='insumo.unidad_medida', read_only=True)
    tipo_movimiento_display = serializers.CharField(source='get_tipo_movimiento_display', read_only=True)
    pedido_codigo = serializers.CharField(source='pedido_asociado.codigo_pedido', read_only=True)

    class Meta:
        model = MovimientoInventario
        fields = '__all__'


class DespachoPedidoSerializer(serializers.ModelSerializer):
    pedido_codigo = serializers.CharField(source='pedido.codigo_pedido', read_only=True)
    cliente_nombre = serializers.CharField(source='pedido.cliente.nombre_completo', read_only=True)
    producto_nombre = serializers.CharField(source='pedido.producto_base.nombre', read_only=True)
    estado_entrega_display = serializers.CharField(source='get_estado_entrega_display', read_only=True)
    tiene_respaldo_digital = serializers.BooleanField(read_only=True)

    class Meta:
        model = DespachoPedido
        fields = '__all__'


class RutaDespachoSerializer(serializers.ModelSerializer):
    repartidor_nombre = serializers.SerializerMethodField()
    estado_ruta_display = serializers.CharField(source='get_estado_ruta_display', read_only=True)
    total_paradas = serializers.IntegerField(read_only=True)
    paradas_entregadas = serializers.IntegerField(read_only=True)
    porcentaje_completado = serializers.IntegerField(read_only=True)
    entregas = DespachoPedidoSerializer(many=True, read_only=True)

    class Meta:
        model = RutaDespacho
        fields = '__all__'

    def get_repartidor_nombre(self, obj):
        return obj.repartidor.get_full_name() or obj.repartidor.username
