"""
Vistas de la API REST (Django REST Framework - ViewSets) para Dulce Arte.
Provee CRUD completo y endpoints especializados para:
- Simulación y cálculo de cotizaciones personalizadas
- Explosión y descuento atómico de Lista de Materiales (BOM)
- Transición de estados en el Tablero Kanban digital
- Confirmación de entregas en ruta con Firma Digital (Base64) o Comprobante Fotográfico
"""

from decimal import Decimal, ROUND_HALF_UP
from django.db.models import F
from django.core.exceptions import ValidationError
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import (
    Cliente,
    CategoriaInsumo,
    Insumo,
    ProductoPasteleria,
    ItemBOM,
    PedidoPersonalizado,
    InsumoExtraPedido,
    MovimientoInventario,
    RutaDespacho,
    DespachoPedido,
)
from .serializers import (
    ClienteSerializer,
    CategoriaInsumoSerializer,
    InsumoSerializer,
    ProductoPasteleriaSerializer,
    ItemBOMSerializer,
    PedidoPersonalizadoSerializer,
    InsumoExtraPedidoSerializer,
    MovimientoInventarioSerializer,
    RutaDespachoSerializer,
    DespachoPedidoSerializer,
)


class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['tipo_cliente', 'comuna']
    search_fields = ['nombre_completo', 'rut', 'email', 'telefono', 'preferencias_alimentarias']
    ordering_fields = ['nombre_completo', 'fecha_registro']


class CategoriaInsumoViewSet(viewsets.ModelViewSet):
    queryset = CategoriaInsumo.objects.all()
    serializer_class = CategoriaInsumoSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['es_perecible', 'requiere_cadena_frio']
    search_fields = ['nombre', 'descripcion']


class InsumoViewSet(viewsets.ModelViewSet):
    queryset = Insumo.objects.select_related('categoria').all()
    serializer_class = InsumoSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['categoria', 'unidad_medida', 'activo']
    search_fields = ['codigo_sku', 'nombre', 'proveedor', 'lote_actual']
    ordering_fields = ['nombre', 'stock_actual', 'costo_unitario', 'fecha_vencimiento']

    @action(detail=False, methods=['get'])
    def alertas_criticas(self, request):
        """Retorna todos los insumos con stock menor o igual al stock mínimo."""
        criticos = self.get_queryset().filter(activo=True, stock_actual__lte=F('stock_minimo'))
        serializer = self.get_serializer(criticos, many=True)
        return Response({
            'total_alertas': criticos.count(),
            'insumos_criticos': serializer.data,
        })

    @action(detail=True, methods=['post'])
    def ajustar_stock(self, request, pk=None):
        """
        Registra una Entrada de Compra o Ajuste de Merma en Bodega con trazabilidad en Kardex.
        Payload: { "tipo_movimiento": "ENTRADA_COMPRA" | "AJUSTE_MERMA", "cantidad": "10.5", "motivo": "Factura #123" }
        """
        insumo = self.get_object()
        tipo = request.data.get('tipo_movimiento', 'ENTRADA_COMPRA')
        motivo = request.data.get('motivo', 'Ajuste desde API Bodega')
        try:
            cantidad = Decimal(str(request.data.get('cantidad', '0')))
        except Exception:
            return Response(
                {'error': 'La cantidad ingresada no es válida.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if cantidad <= 0:
            return Response(
                {'error': 'La cantidad debe ser mayor a cero.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stock_anterior = insumo.stock_actual
        if tipo == 'AJUSTE_MERMA':
            if stock_anterior < cantidad:
                return Response(
                    {'error': f'Stock insuficiente para dar de baja {cantidad} {insumo.unidad_medida}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            insumo.stock_actual = stock_anterior - cantidad
        else:
            tipo = 'ENTRADA_COMPRA'
            insumo.stock_actual = stock_anterior + cantidad

        insumo.save(update_fields=['stock_actual', 'actualizado_en'])
        mov = MovimientoInventario.objects.create(
            insumo=insumo,
            tipo_movimiento=tipo,
            cantidad=cantidad,
            stock_anterior=stock_anterior,
            stock_resultante=insumo.stock_actual,
            usuario=request.user,
            motivo=motivo,
        )

        return Response({
            'mensaje': f'Stock actualizado correctamente ({insumo.stock_actual} {insumo.unidad_medida}).',
            'insumo': InsumoSerializer(insumo).data,
            'movimiento_id': mov.id,
        })


class ProductoPasteleriaViewSet(viewsets.ModelViewSet):
    queryset = ProductoPasteleria.objects.prefetch_related('items_bom__insumo').all()
    serializer_class = ProductoPasteleriaSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['categoria_producto', 'requiere_refrigeracion', 'activo']
    search_fields = ['codigo', 'nombre', 'descripcion']


class ItemBOMViewSet(viewsets.ModelViewSet):
    queryset = ItemBOM.objects.select_related('producto', 'insumo').all()
    serializer_class = ItemBOMSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['producto', 'insumo', 'etapa_uso']


class PedidoPersonalizadoViewSet(viewsets.ModelViewSet):
    queryset = (
        PedidoPersonalizado.objects.select_related('cliente', 'producto_base', 'vendedor', 'pastelero_asignado')
        .prefetch_related('insumos_extra__insumo', 'historial_kanban')
        .all()
    )
    serializer_class = PedidoPersonalizadoSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = [
        'estado_kanban',
        'estado_comercial',
        'prioridad',
        'insumos_descontados',
        'modalidad_entrega',
    ]
    search_fields = ['codigo_pedido', 'cliente__nombre_completo', 'cliente__rut', 'sabor_bizcocho', 'relleno_principal']
    ordering_fields = ['fecha_entrega_comprometida', 'fecha_creacion', 'precio_total']

    def perform_create(self, serializer):
        pedido = serializer.save(vendedor=self.request.user)
        pedido.recalcular_cotizacion(guardar=True)

    @action(detail=True, methods=['get'])
    def explosion_bom(self, request, pk=None):
        """Retorna el desglose completo de Lista de Materiales (BOM) y factibilidad de stock."""
        pedido = self.get_object()
        es_factible, faltantes, explosion = pedido.verificar_disponibilidad_bom()
        return Response({
            'codigo_pedido': pedido.codigo_pedido,
            'producto_base': pedido.producto_base.nombre,
            'porciones_solicitadas': pedido.porciones_solicitadas,
            'factor_escala_porciones': str(pedido.factor_escala_porciones),
            'insumos_descontados': pedido.insumos_descontados,
            'es_factible_stock': es_factible,
            'cantidad_faltantes': len(faltantes),
            'explosion_materiales': explosion,
        })

    @action(detail=True, methods=['post'])
    def descontar_bom(self, request, pk=None):
        """Ejecuta manualmente o desde cocina el descuento atómico de insumos BOM en PostgreSQL."""
        pedido = self.get_object()
        try:
            realizado, mensaje = pedido.descontar_insumos_bom(usuario=request.user)
            return Response({
                'exito': realizado,
                'mensaje': mensaje,
                'pedido': PedidoPersonalizadoSerializer(pedido).data,
            })
        except ValidationError as exc:
            return Response(
                {'exito': False, 'error': exc.message},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=True, methods=['post'])
    def mover_kanban(self, request, pk=None):
        """
        Endpoint consumido por el Tablero Kanban interactivo (Drag & Drop / Botones de Cocina).
        Payload: { "nuevo_estado": "EN_PREPARACION", "comentario": "Iniciando batido" }
        """
        pedido = self.get_object()
        nuevo_estado = request.data.get('nuevo_estado')
        comentario = request.data.get('comentario', '')
        temperatura = request.data.get('temperatura_refrigeracion_c')

        if temperatura is not None and str(temperatura).strip() != '':
            try:
                pedido.temperatura_refrigeracion_c = Decimal(str(temperatura))
                pedido.save(update_fields=['temperatura_refrigeracion_c'])
            except Exception:
                pass

        try:
            pedido.cambiar_estado_kanban(
                nuevo_estado=nuevo_estado,
                usuario=request.user,
                comentario=comentario,
            )
            return Response({
                'exito': True,
                'mensaje': (
                    f"Pedido {pedido.codigo_pedido} movido a '{pedido.get_estado_kanban_display()}'. "
                    + ("Insumos BOM descontados de bodega." if pedido.insumos_descontados else "")
                ),
                'pedido': PedidoPersonalizadoSerializer(pedido).data,
            })
        except ValidationError as exc:
            return Response(
                {'exito': False, 'error': exc.message},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=['post'])
    def simular_cotizacion(self, request):
        """
        Simulador en tiempo real para el Cotizador de Pedidos Personalizados (Funcionalidad 1).
        Calcula precio sugerido, costo BOM y verifica disponibilidad de stock antes de guardar.
        """
        producto_id = request.data.get('producto_base_id')
        porciones = int(request.data.get('porciones_solicitadas', 15))
        complejidad = request.data.get('nivel_complejidad', 'PERSONALIZADO_MEDIO')
        modalidad = request.data.get('modalidad_entrega', 'DESPACHO_DOMICILIO')

        try:
            producto = ProductoPasteleria.objects.prefetch_related('items_bom__insumo').get(pk=producto_id)
        except ProductoPasteleria.DoesNotExist:
            return Response({'error': 'Producto base no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        factor_escala = (Decimal(str(max(porciones, 1))) / Decimal(str(max(producto.porciones_base, 1)))).quantize(
            Decimal('0.001'), rounding=ROUND_HALF_UP
        )
        mapa_comp = {
            'ESTANDAR': Decimal('1.00'),
            'PERSONALIZADO_MEDIO': Decimal('1.25'),
            'ALTA_ESCULTURAL': Decimal('1.50'),
        }
        factor_comp = mapa_comp.get(complejidad, Decimal('1.25'))

        desglose_bom = []
        costo_bom_total = Decimal('0')
        stock_factible = True

        for item in producto.items_bom.all():
            insumo = item.insumo
            requerido = (item.cantidad_con_merma * factor_escala).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
            disponible = insumo.stock_actual
            suficiente = disponible >= requerido
            if not suficiente:
                stock_factible = False
            subtotal = (requerido * insumo.costo_unitario).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            costo_bom_total += subtotal
            desglose_bom.append({
                'insumo': insumo.nombre,
                'sku': insumo.codigo_sku,
                'etapa': item.get_etapa_uso_display(),
                'cantidad_requerida': str(requerido),
                'stock_disponible': str(disponible),
                'unidad': insumo.unidad_medida,
                'suficiente': suficiente,
                'costo_subtotal': int(subtotal),
            })

        precio_proporcional = (producto.precio_base * factor_escala).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        recargo_diseno = (precio_proporcional * (factor_comp - Decimal('1.00'))).quantize(
            Decimal('1'), rounding=ROUND_HALF_UP
        )
        costo_despacho = Decimal('5000') if modalidad == 'DESPACHO_DOMICILIO' else Decimal('0')
        precio_total = precio_proporcional + recargo_diseno + costo_despacho
        abono_sugerido = (precio_total * Decimal('0.50')).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

        return Response({
            'producto': producto.nombre,
            'porciones_base': producto.porciones_base,
            'porciones_solicitadas': porciones,
            'factor_escala': str(factor_escala),
            'costo_bom_estimado': int(costo_bom_total),
            'precio_base_proporcional': int(precio_proporcional),
            'recargo_complejidad': int(recargo_diseno),
            'costo_despacho': int(costo_despacho),
            'precio_total_cotizado': int(precio_total),
            'abono_minimo_50pct': int(abono_sugerido),
            'stock_factible': stock_factible,
            'desglose_bom': desglose_bom,
        })


class InsumoExtraPedidoViewSet(viewsets.ModelViewSet):
    queryset = InsumoExtraPedido.objects.select_related('pedido', 'insumo').all()
    serializer_class = InsumoExtraPedidoSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['pedido', 'insumo']


class MovimientoInventarioViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MovimientoInventario.objects.select_related('insumo', 'pedido_asociado', 'usuario').all()
    serializer_class = MovimientoInventarioSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['insumo', 'tipo_movimiento', 'pedido_asociado']
    search_fields = ['insumo__nombre', 'insumo__codigo_sku', 'pedido_asociado__codigo_pedido', 'motivo']


class RutaDespachoViewSet(viewsets.ModelViewSet):
    queryset = RutaDespacho.objects.select_related('repartidor').prefetch_related('entregas__pedido__cliente').all()
    serializer_class = RutaDespachoSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['estado_ruta', 'fecha_ruta', 'repartidor']
    search_fields = ['codigo_ruta', 'nombre_ruta', 'vehiculo_patente']


class DespachoPedidoViewSet(viewsets.ModelViewSet):
    queryset = DespachoPedido.objects.select_related('ruta', 'pedido__cliente', 'pedido__producto_base').all()
    serializer_class = DespachoPedidoSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['ruta', 'estado_entrega', 'comuna_destino']
    search_fields = ['pedido__codigo_pedido', 'direccion_destino', 'nombre_receptor', 'rut_receptor']

    @action(detail=True, methods=['post'])
    def confirmar_entrega(self, request, pk=None):
        """
        Confirma la entrega de una parada en ruta mediante Firma Digital (Canvas Base64)
        o Comprobante Fotográfico (Funcionalidad 4).
        """
        despacho = self.get_object()
        nombre_receptor = request.data.get('nombre_receptor', '')
        rut_receptor = request.data.get('rut_receptor', '')
        parentesco = request.data.get('parentesco_o_cargo', 'Cliente Titular')
        firma_base64 = request.data.get('firma_digital_base64', '')
        foto_archivo = request.FILES.get('comprobante_foto')
        temperatura = request.data.get('temperatura_entrega_c', '4.2')
        observaciones = request.data.get('observaciones_entrega', '')
        coordenadas = request.data.get('coordenadas_gps', '-33.4262, -70.6109')

        try:
            despacho.confirmar_entrega_digital(
                nombre_receptor=nombre_receptor,
                rut_receptor=rut_receptor,
                firma_base64=firma_base64,
                comprobante_archivo=foto_archivo,
                parentesco=parentesco,
                temperatura_c=temperatura,
                observaciones=observaciones,
                coordenadas=coordenadas,
                usuario=request.user,
            )
            return Response({
                'exito': True,
                'mensaje': f'Entrega del pedido {despacho.pedido.codigo_pedido} confirmada exitosamente con respaldo digital.',
                'despacho': DespachoPedidoSerializer(despacho).data,
            })
        except ValidationError as exc:
            return Response(
                {'exito': False, 'error': exc.message},
                status=status.HTTP_400_BAD_REQUEST,
            )
