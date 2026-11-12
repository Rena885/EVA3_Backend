"""
Modelos del Dominio - Proyecto 3: Pastelería Artesanal "Dulce Arte"
Sistema de Trazabilidad End-to-End y Gestión de Pedidos Personalizados.

Implementa la Vista Lógica y de Procesos del Paradigma 4+1:
1. Seguridad y Perfiles por Rol Operativo (PerfilUsuario).
2. Clientes y Cotización de Pedidos Personalizados (Cliente, PedidoPersonalizado, InsumoExtraPedido).
3. Inventario de Bodega y Lista de Materiales - BOM (CategoriaInsumo, Insumo, ProductoPasteleria, ItemBOM, MovimientoInventario).
4. Taller de Cocina y Flujo Kanban Digital (PedidoPersonalizado.estado_kanban, HistorialKanban).
5. Logística de Rutas de Despacho y Confirmación con Firma Digital / Comprobante (RutaDespacho, DespachoPedido).
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.utils import timezone


# ==============================================================================
# 1. SEGURIDAD, ROLES Y GESTIÓN DE USUARIOS
# ==============================================================================
class PerfilUsuario(models.Model):
    """Extiende el usuario de Django con roles operativos del negocio pastelero."""
    ROL_CHOICES = [
        ('ADMIN', 'Administrador General'),
        ('VENTAS', 'Ejecutivo de Ventas y Cotizaciones'),
        ('COCINA', 'Maestro Pastelero / Taller de Cocina'),
        ('BODEGA', 'Encargado de Bodega e Inventario BOM'),
        ('REPARTIDOR', 'Repartidor / Logística de Despacho'),
    ]

    TURNO_CHOICES = [
        ('MANANA', 'Turno Mañana (07:00 - 15:00)'),
        ('TARDE', 'Turno Tarde (12:00 - 20:00)'),
        ('COMPLETO', 'Jornada Completa'),
    ]

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='perfil',
        verbose_name='Usuario del Sistema'
    )
    rol = models.CharField(
        max_length=20,
        choices=ROL_CHOICES,
        default='VENTAS',
        verbose_name='Rol Operativo'
    )
    rut = models.CharField(
        max_length=15,
        blank=True,
        verbose_name='RUT Trabajador'
    )
    telefono = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Teléfono de Contacto'
    )
    turno = models.CharField(
        max_length=15,
        choices=TURNO_CHOICES,
        default='COMPLETO',
        verbose_name='Turno Asignado'
    )
    especialidad_pastelera = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Especialidad (Fondant, Chocolatería, Masas, Logística)'
    )
    activo = models.BooleanField(default=True, verbose_name='Personal Activo')

    class Meta:
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuarios'
        ordering = ['rol', 'usuario__first_name']

    def __str__(self):
        nombre = self.usuario.get_full_name() or self.usuario.username
        return f"{nombre} ({self.get_rol_display()})"


# ==============================================================================
# 2. CLIENTES DE LA PASTELERÍA
# ==============================================================================
class Cliente(models.Model):
    """Registro de clientes particulares y corporativos de Dulce Arte."""
    TIPO_CLIENTE_CHOICES = [
        ('PARTICULAR', 'Cliente Particular / Celebración'),
        ('EVENTO_NOVIOS', 'Matrimonio / Banquetería'),
        ('CORPORATIVO', 'Empresa / Convenio Corporativo'),
    ]

    rut = models.CharField(
        max_length=15,
        unique=True,
        verbose_name='RUT Cliente'
    )
    nombre_completo = models.CharField(
        max_length=150,
        verbose_name='Nombre Completo o Razón Social'
    )
    tipo_cliente = models.CharField(
        max_length=20,
        choices=TIPO_CLIENTE_CHOICES,
        default='PARTICULAR',
        verbose_name='Tipo de Cliente'
    )
    email = models.EmailField(verbose_name='Correo Electrónico')
    telefono = models.CharField(max_length=25, verbose_name='Teléfono / WhatsApp')
    direccion_habitual = models.CharField(
        max_length=220,
        verbose_name='Dirección Habitual de Entrega'
    )
    comuna = models.CharField(
        max_length=80,
        default='Providencia',
        verbose_name='Comuna'
    )
    preferencias_alimentarias = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Restricciones o Alergias (Sin Gluten, Sin Lactosa, Vegano, Nueces)'
    )
    notas = models.TextField(blank=True, verbose_name='Notas e Historial del Cliente')
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Registro')

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['nombre_completo']

    def __str__(self):
        return f"{self.nombre_completo} ({self.rut})"


# ==============================================================================
# 3. BODEGA DE INSUMOS Y LISTA DE MATERIALES (BOM - BILL OF MATERIALS)
# ==============================================================================
class CategoriaInsumo(models.Model):
    """Clasificación de materias primas y materiales de empaque/decoración."""
    nombre = models.CharField(max_length=80, unique=True, verbose_name='Nombre Categoría')
    descripcion = models.CharField(max_length=220, blank=True, verbose_name='Descripción')
    es_perecible = models.BooleanField(
        default=True,
        verbose_name='¿Contiene Insumos Perecibles?'
    )
    requiere_cadena_frio = models.BooleanField(
        default=False,
        verbose_name='¿Requiere Cadena de Frío (2°C - 6°C)?'
    )

    class Meta:
        verbose_name = 'Categoría de Insumo'
        verbose_name_plural = 'Categorías de Insumos'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Insumo(models.Model):
    """
    Materia prima o insumo de bodega controlado mediante Lista de Materiales (BOM).
    Controla stock actual, punto de reorden (stock mínimo), lote y vencimiento.
    """
    UNIDAD_CHOICES = [
        ('KG', 'Kilogramos (kg)'),
        ('GR', 'Gramos (g)'),
        ('LT', 'Litros (L)'),
        ('ML', 'Mililitros (ml)'),
        ('UNIDAD', 'Unidades (un)'),
    ]

    codigo_sku = models.CharField(
        max_length=30,
        unique=True,
        blank=True,
        verbose_name='Código SKU'
    )
    nombre = models.CharField(max_length=120, verbose_name='Nombre del Insumo')
    categoria = models.ForeignKey(
        CategoriaInsumo,
        on_delete=models.PROTECT,
        related_name='insumos',
        verbose_name='Categoría'
    )
    unidad_medida = models.CharField(
        max_length=10,
        choices=UNIDAD_CHOICES,
        default='KG',
        verbose_name='Unidad de Medida'
    )
    stock_actual = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal('0.000'),
        validators=[MinValueValidator(Decimal('0.000'))],
        verbose_name='Stock Disponible'
    )
    stock_minimo = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal('5.000'),
        validators=[MinValueValidator(Decimal('0.000'))],
        verbose_name='Stock Mínimo Crítico'
    )
    costo_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('1000.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Costo Unitario (CLP)'
    )
    proveedor = models.CharField(
        max_length=120,
        blank=True,
        default='Distribuidora Gourmet Chile',
        verbose_name='Proveedor Principal'
    )
    lote_actual = models.CharField(
        max_length=50,
        blank=True,
        default='LOTE-2026-A1',
        verbose_name='Código de Lote'
    )
    fecha_vencimiento = models.DateField(
        null=True,
        blank=True,
        verbose_name='Fecha de Vencimiento (Perecibles)'
    )
    ubicacion_bodega = models.CharField(
        max_length=60,
        blank=True,
        default='Estante Secos A1',
        verbose_name='Ubicación en Bodega / Cámara Frío'
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name='Última Actualización')

    class Meta:
        verbose_name = 'Insumo de Bodega'
        verbose_name_plural = 'Insumos de Bodega'
        ordering = ['nombre']

    def __str__(self):
        return f"[{self.codigo_sku}] {self.nombre} ({self.stock_actual} {self.unidad_medida})"

    def save(self, *args, **kwargs):
        if not self.codigo_sku or not self.codigo_sku.strip():
            letras = ''.join(ch for ch in (self.nombre or '').upper() if ch.isalpha())
            prefijo = (letras[:3] if len(letras) >= 3 else (letras + 'INS')[:3])
            correlativo = Insumo.objects.count() + 1
            candidato = f"INS-{prefijo}-{correlativo:03d}"
            while Insumo.objects.filter(codigo_sku=candidato).exclude(pk=self.pk).exists():
                correlativo += 1
                candidato = f"INS-{prefijo}-{correlativo:03d}"
            self.codigo_sku = candidato
        else:
            self.codigo_sku = self.codigo_sku.strip().upper()

        if not self.categoria_id:
            cat_default, _ = CategoriaInsumo.objects.get_or_create(
                nombre='Panadería, Salados e Insumos Generales',
                defaults={
                    'descripcion': 'Quesos, panes, fiambres, masas e insumos generales de cocina',
                    'es_perecible': True,
                    'requiere_cadena_frio': False,
                },
            )
            self.categoria = cat_default

        if not self.proveedor or not self.proveedor.strip():
            self.proveedor = 'Distribuidora Gourmet Chile'
        if not self.lote_actual or not self.lote_actual.strip():
            self.lote_actual = 'LOTE-2026-A1'
        if not self.ubicacion_bodega or not self.ubicacion_bodega.strip():
            self.ubicacion_bodega = 'Estante Secos A1'

        super().save(*args, **kwargs)

    @property
    def en_alerta_stock(self) -> bool:
        """Retorna True si el stock actual está por debajo o igual al stock mínimo."""
        return self.stock_actual <= self.stock_minimo

    @property
    def dias_para_vencer(self):
        """Retorna los días restantes hasta el vencimiento del lote actual."""
        if not self.fecha_vencimiento:
            return None
        hoy = timezone.localdate()
        return (self.fecha_vencimiento - hoy).days

    @property
    def alerta_vencimiento(self) -> str:
        """Clasifica el riesgo de perecibilidad: VENCIDO, POR_VENCER (<=7 días), OK."""
        dias = self.dias_para_vencer
        if dias is None:
            return 'NO_PERECIBLE'
        if dias < 0:
            return 'VENCIDO'
        if dias <= 7:
            return 'POR_VENCER'
        return 'OK'

    @property
    def valor_inventario_total(self) -> Decimal:
        """Valorización financiera del stock actual en CLP."""
        return (self.stock_actual * self.costo_unitario).quantize(
            Decimal('1'), rounding=ROUND_HALF_UP
        )


class ProductoPasteleria(models.Model):
    """
    Catálogo de Recetas Base y Productos de Pastelería sobre los cuales se
    define la Lista de Materiales (BOM) estándar.
    """
    CATEGORIA_PRODUCTO_CHOICES = [
        ('TORTA_AUTOR', 'Torta de Autor / Personalizada'),
        ('TORTA_CLASICA', 'Torta Tradicional Chilena & Europea'),
        ('NOVIOS_EVENTOS', 'Torta de Novios / Alta Pastelería Escultural'),
        ('SIN_ALERGENOS', 'Línea Keto / Vegana / Sin Gluten'),
        ('PANADERIA_SANDWICH', 'Panadería, Sándwiches y Salados'),
        ('PASTELERIA_INDIVIDUAL', 'Pastelería Individual y Cafetería'),
    ]

    codigo = models.CharField(
        max_length=30,
        unique=True,
        blank=True,
        verbose_name='Código Receta'
    )
    nombre = models.CharField(max_length=140, verbose_name='Nombre del Producto Base')
    categoria_producto = models.CharField(
        max_length=25,
        choices=CATEGORIA_PRODUCTO_CHOICES,
        default='TORTA_AUTOR',
        verbose_name='Línea / Categoría de Producto'
    )
    descripcion = models.TextField(
        blank=True,
        default='Elaboración artesanal según receta base y Lista de Materiales (BOM).',
        verbose_name='Descripción Técnica y Gastronómica'
    )
    porciones_base = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name='Rendimiento Base (Unidades o Porciones)'
    )
    precio_base = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        default=Decimal('38000'),
        verbose_name='Precio Base Venta (CLP)'
    )
    tiempo_elaboracion_horas = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        default=Decimal('1.0'),
        verbose_name='Tiempo Estimado en Cocina (Horas)'
    )
    requiere_refrigeracion = models.BooleanField(
        default=True,
        verbose_name='Requiere Refrigeración Continua'
    )
    instrucciones_receta = models.TextField(
        blank=True,
        verbose_name='Protocolo Estándar de Elaboración en Cocina'
    )
    activo = models.BooleanField(default=True, verbose_name='Disponible en Catálogo')

    class Meta:
        verbose_name = 'Producto / Receta Base'
        verbose_name_plural = 'Productos y Recetas Base (Catálogo BOM)'
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} (Base {self.porciones_base} porc. - ${self.precio_base:,.0f})"

    def save(self, *args, **kwargs):
        if not self.codigo or not self.codigo.strip():
            letras = ''.join(ch for ch in (self.nombre or '').upper() if ch.isalpha())
            prefijo = (letras[:4] if len(letras) >= 4 else (letras + 'PROD')[:4])
            correlativo = ProductoPasteleria.objects.count() + 1
            candidato = f"REC-{prefijo}-{correlativo:03d}"
            while ProductoPasteleria.objects.filter(codigo=candidato).exclude(pk=self.pk).exists():
                correlativo += 1
                candidato = f"REC-{prefijo}-{correlativo:03d}"
            self.codigo = candidato
        else:
            self.codigo = self.codigo.strip().upper()

        if not self.descripcion or not self.descripcion.strip():
            self.descripcion = f"Receta y producto de catálogo: {self.nombre}."

        super().save(*args, **kwargs)

    @property
    def costo_bom_base(self) -> Decimal:
        """Suma el costo de todos los insumos definidos en el BOM para las porciones base."""
        total = Decimal('0.00')
        for item in self.items_bom.select_related('insumo').all():
            total += item.costo_linea
        return total.quantize(Decimal('1'), rounding=ROUND_HALF_UP)

    @property
    def margen_bruto_pct(self) -> Decimal:
        """Porcentaje de margen bruto sobre el precio base."""
        if not self.precio_base or self.precio_base <= 0:
            return Decimal('0.0')
        costo = self.costo_bom_base
        margen = ((self.precio_base - costo) / self.precio_base) * Decimal('100')
        return margen.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)


class ItemBOM(models.Model):
    """
    Línea de Lista de Materiales (Bill of Materials - BOM).
    Vincula una receta base (ProductoPasteleria) con la cantidad exacta de cada
    Insumo requerida para elaborar las `porciones_base` del producto.
    """
    ETAPA_USO_CHOICES = [
        ('BATIDO_MASA', 'Batido y Bizcocho'),
        ('ALMIBAR_REMOJO', 'Almíbar y Remojo'),
        ('RELLENO', 'Relleno Pastelero'),
        ('COBERTURA_DECORACION', 'Cobertura, Ganache y Decoración'),
        ('PACKAGING', 'Base y Caja Térmica de Transporte'),
    ]

    producto = models.ForeignKey(
        ProductoPasteleria,
        on_delete=models.CASCADE,
        related_name='items_bom',
        verbose_name='Producto / Receta Base'
    )
    insumo = models.ForeignKey(
        Insumo,
        on_delete=models.PROTECT,
        related_name='usos_bom',
        verbose_name='Insumo Requerido'
    )
    cantidad_requerida = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        verbose_name='Cantidad Neta (según Porciones Base)'
    )
    merma_tecnica_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('3.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Merma Técnica de Cocina (%)'
    )
    etapa_uso = models.CharField(
        max_length=25,
        choices=ETAPA_USO_CHOICES,
        default='BATIDO_MASA',
        verbose_name='Etapa de Uso en Receta'
    )
    notas_tecnicas = models.CharField(
        max_length=160,
        blank=True,
        verbose_name='Especificación Técnica'
    )

    class Meta:
        verbose_name = 'Componente de Lista de Materiales (BOM)'
        verbose_name_plural = 'Componentes de Lista de Materiales (BOM)'
        unique_together = ('producto', 'insumo', 'etapa_uso')
        ordering = ['producto', 'etapa_uso', 'insumo__nombre']

    def __str__(self):
        return (
            f"{self.producto.nombre} -> {self.insumo.nombre}: "
            f"{self.cantidad_con_merma} {self.insumo.unidad_medida}"
        )

    @property
    def cantidad_con_merma(self) -> Decimal:
        """Cantidad bruta a descontar de bodega incluyendo el porcentaje de merma."""
        factor_merma = Decimal('1.00') + (self.merma_tecnica_pct / Decimal('100.00'))
        return (self.cantidad_requerida * factor_merma).quantize(
            Decimal('0.001'), rounding=ROUND_HALF_UP
        )

    @property
    def costo_linea(self) -> Decimal:
        """Costo monetario de este componente en la receta base."""
        return (self.cantidad_con_merma * self.insumo.costo_unitario).quantize(
            Decimal('1'), rounding=ROUND_HALF_UP
        )


# ==============================================================================
# 4. COTIZACIÓN, PEDIDOS PERSONALIZADOS Y FLUJO KANBAN DE COCINA
# ==============================================================================
class PedidoPersonalizado(models.Model):
    """
    Entidad central de Trazabilidad End-to-End de Dulce Arte:
    - Funcionalidad 1: Cotización y registro de pedidos personalizados.
    - Funcionalidad 2: Tablero Kanban digital para el taller de cocina.
    - Funcionalidad 3: Descuento automático de inventario vía BOM al entrar en preparación.
    """
    ESTADO_COMERCIAL_CHOICES = [
        ('COTIZACION', '1. En Cotización / Pendiente Aprobación'),
        ('CONFIRMADO', '2. Pedido Confirmado (Abono Recibido)'),
        ('EN_PRODUCCION', '3. En Producción en Taller de Cocina'),
        ('LISTO_DESPACHO', '4. Listo para Despacho / Retiro'),
        ('ENTREGADO', '5. Entregado y Cerrado'),
        ('CANCELADO', 'Cancelado'),
    ]

    # Las 5 columnas exactas requeridas por el caso para el Tablero Kanban
    ESTADO_KANBAN_CHOICES = [
        ('RECIBIDO', 'Recibido'),
        ('EN_PREPARACION', 'En Preparación'),
        ('HORNEADO_DECORADO', 'Horneado/Decorado'),
        ('CONTROL_CALIDAD', 'Control de Calidad'),
        ('LISTO', 'Listo'),
    ]

    ORDEN_KANBAN = [
        'RECIBIDO',
        'EN_PREPARACION',
        'HORNEADO_DECORADO',
        'CONTROL_CALIDAD',
        'LISTO',
    ]

    COMPLEJIDAD_CHOICES = [
        ('ESTANDAR', 'Estándar / Decoración Clásica (Factor 1.0x)'),
        ('PERSONALIZADO_MEDIO', 'Diseño Temático Personalizado (Factor 1.25x)'),
        ('ALTA_ESCULTURAL', 'Alta Complejidad / Modelado 3D o Fondant (Factor 1.50x)'),
    ]

    PRIORIDAD_CHOICES = [
        ('BAJA', 'Baja'),
        ('NORMAL', 'Normal'),
        ('ALTA', 'Alta'),
        ('URGENTE', 'Urgente / Evento Fecha Fija'),
    ]

    MODALIDAD_ENTREGA_CHOICES = [
        ('DESPACHO_DOMICILIO', 'Despacho Refrigerado a Domicilio'),
        ('RETIRO_TIENDA', 'Retiro en Tienda Dulce Arte'),
    ]

    codigo_pedido = models.CharField(
        max_length=25,
        unique=True,
        editable=False,
        verbose_name='Código de Seguimiento'
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='pedidos',
        verbose_name='Cliente'
    )
    producto_base = models.ForeignKey(
        ProductoPasteleria,
        on_delete=models.PROTECT,
        related_name='pedidos',
        verbose_name='Receta / Producto Base (BOM)'
    )
    vendedor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pedidos_vendidos',
        verbose_name='Ejecutivo de Ventas'
    )
    pastelero_asignado = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pedidos_cocina',
        verbose_name='Maestro Pastelero Asignado'
    )

    # Atributos de Personalización Pastelera (Funcionalidad 1)
    porciones_solicitadas = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name='Cantidad de Unidades / Porciones Solicitadas'
    )
    sabor_bizcocho = models.CharField(
        max_length=100,
        blank=True,
        default='Bizcocho Vainilla Bourbon de Madagascar',
        verbose_name='Sabor de Bizcocho / Masa'
    )
    relleno_principal = models.CharField(
        max_length=120,
        blank=True,
        default='Ganache de Chocolate Belga 70% y Frambuesas Frescas',
        verbose_name='Relleno Principal y Capas'
    )
    cobertura_diseno = models.CharField(
        max_length=120,
        blank=True,
        default='Buttercream de Merengue Suizo con Flores Naturales',
        verbose_name='Cobertura y Estilo de Decoración'
    )
    nivel_complejidad = models.CharField(
        max_length=25,
        choices=COMPLEJIDAD_CHOICES,
        default='PERSONALIZADO_MEDIO',
        verbose_name='Complejidad de Diseño Artístico'
    )
    dedicatoria_texto = models.CharField(
        max_length=140,
        blank=True,
        verbose_name='Mensaje o Dedicatoria en Placa de Chocolate'
    )
    descripcion_diseno = models.TextField(
        blank=True,
        default='Preparación estándar según receta base y Lista de Materiales (BOM).',
        verbose_name='Especificaciones Detalladas del Diseño y Colores'
    )
    alergias_considerar = models.CharField(
        max_length=180,
        blank=True,
        verbose_name='Restricciones / Alergias Alimentarias del Pedido'
    )
    imagen_referencia = models.ImageField(
        upload_to='bocetos_pedidos/',
        null=True,
        blank=True,
        verbose_name='Imagen / Boceto de Referencia'
    )

    # Planificación Temporal y Logística
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Cotización')
    fecha_entrega_comprometida = models.DateTimeField(
        default=timezone.now,
        verbose_name='Fecha y Hora Comprometida de Entrega'
    )
    modalidad_entrega = models.CharField(
        max_length=25,
        choices=MODALIDAD_ENTREGA_CHOICES,
        default='DESPACHO_DOMICILIO',
        verbose_name='Modalidad de Entrega'
    )
    direccion_entrega = models.CharField(
        max_length=220,
        blank=True,
        default='Retiro en Tienda Dulce Arte',
        verbose_name='Dirección de Entrega'
    )
    comuna_entrega = models.CharField(
        max_length=80,
        blank=True,
        default='Providencia',
        verbose_name='Comuna de Entrega'
    )

    # Estados de Trazabilidad Comercial y Kanban de Cocina
    estado_comercial = models.CharField(
        max_length=20,
        choices=ESTADO_COMERCIAL_CHOICES,
        default='COTIZACION',
        verbose_name='Estado Comercial'
    )
    estado_kanban = models.CharField(
        max_length=25,
        choices=ESTADO_KANBAN_CHOICES,
        default='RECIBIDO',
        verbose_name='Etapa en Tablero Kanban Cocina'
    )
    prioridad = models.CharField(
        max_length=12,
        choices=PRIORIDAD_CHOICES,
        default='NORMAL',
        verbose_name='Prioridad en Taller'
    )

    # Control de Descuento Automático de Inventario BOM (Funcionalidad 3)
    insumos_descontados = models.BooleanField(
        default=False,
        verbose_name='¿Insumos BOM Descontados de Bodega?'
    )
    fecha_descuento_bom = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha/Hora de Descuento BOM'
    )

    # Control de Calidad en Cocina (Etapa CONTROL_CALIDAD -> LISTO)
    aprobado_calidad = models.BooleanField(
        default=False,
        verbose_name='Aprobado por Control de Calidad'
    )
    temperatura_refrigeracion_c = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        default=Decimal('4.0'),
        verbose_name='Temperatura Cámara Frío (°C)'
    )
    observaciones_calidad = models.TextField(
        blank=True,
        verbose_name='Observaciones de Control de Calidad y Cocina'
    )

    # Valores Financieros de la Cotización (CLP)
    costo_insumos_estimado = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=Decimal('0'),
        verbose_name='Costo Insumos BOM Calculado (CLP)'
    )
    recargo_diseno = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=Decimal('0'),
        verbose_name='Recargo por Complejidad de Diseño (CLP)'
    )
    costo_despacho = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        default=Decimal('5000'),
        verbose_name='Tarifa Despacho Refrigerado (CLP)'
    )
    precio_total = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=Decimal('0'),
        verbose_name='Precio Total Cotizado (CLP)'
    )
    abono_pagado = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=Decimal('0'),
        verbose_name='Abono Pagado por Cliente (CLP)'
    )

    actualizado_en = models.DateTimeField(auto_now=True, verbose_name='Última Modificación')

    class Meta:
        verbose_name = 'Pedido Personalizado'
        verbose_name_plural = 'Pedidos Personalizados y Cotizaciones'
        ordering = ['fecha_entrega_comprometida', '-prioridad']

    def __str__(self):
        return f"{self.codigo_pedido} - {self.cliente.nombre_completo} ({self.get_estado_kanban_display()})"

    @property
    def factor_escala_porciones(self) -> Decimal:
        """
        Factor multiplicador de la receta base según las porciones solicitadas.
        Ej: Si el producto base es de 15 porciones y el cliente pide 30, el factor es 2.000.
        """
        base = Decimal(str(max(self.producto_base.porciones_base, 1)))
        solicitadas = Decimal(str(max(self.porciones_solicitadas, 1)))
        return (solicitadas / base).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)

    @property
    def factor_complejidad(self) -> Decimal:
        """Retorna el multiplicador comercial según el nivel de complejidad artística."""
        mapa = {
            'ESTANDAR': Decimal('1.00'),
            'PERSONALIZADO_MEDIO': Decimal('1.25'),
            'ALTA_ESCULTURAL': Decimal('1.50'),
        }
        return mapa.get(self.nivel_complejidad, Decimal('1.00'))

    @property
    def saldo_pendiente(self) -> Decimal:
        """Monto restante por pagar al momento de la entrega."""
        return max(Decimal('0'), self.precio_total - self.abono_pagado)

    @property
    def porcentaje_avance_kanban(self) -> int:
        """Porcentaje visual de progreso en el taller de cocina."""
        mapa_avance = {
            'RECIBIDO': 15,
            'EN_PREPARACION': 40,
            'HORNEADO_DECORADO': 65,
            'CONTROL_CALIDAD': 85,
            'LISTO': 100,
        }
        return mapa_avance.get(self.estado_kanban, 0)

    @property
    def horas_restantes_entrega(self) -> float:
        """Horas restantes hasta la fecha/hora comprometida de entrega."""
        delta = self.fecha_entrega_comprometida - timezone.now()
        return round(delta.total_seconds() / 3600, 1)

    @property
    def en_riesgo_atraso(self) -> bool:
        """Alerta si faltan menos de 6 horas para la entrega y aún no está LISTO."""
        return (
            self.estado_kanban != 'LISTO'
            and self.estado_comercial not in ('ENTREGADO', 'CANCELADO')
            and self.horas_restantes_entrega < 6.0
        )

    def obtener_explosion_bom(self):
        """
        Calcula la Explosión de Materiales (BOM) completa del pedido personalizado:
        Combina los `ItemBOM` de la receta base (escalados por `factor_escala_porciones`
        más merma técnica) y los `InsumoExtraPedido` agregados por personalización.

        Retorna una lista de diccionarios con el desglose por insumo y su factibilidad en bodega.
        """
        factor = self.factor_escala_porciones
        agrupado = {}

        # 1. Insumos de la Lista de Materiales (BOM) estándar del producto base
        for item in self.producto_base.items_bom.select_related('insumo').all():
            insumo = item.insumo
            cantidad_escalada = (item.cantidad_con_merma * factor).quantize(
                Decimal('0.001'), rounding=ROUND_HALF_UP
            )
            if insumo.id not in agrupado:
                agrupado[insumo.id] = {
                    'insumo': insumo,
                    'cantidad_bom_base': Decimal('0.000'),
                    'cantidad_extra': Decimal('0.000'),
                    'cantidad_total': Decimal('0.000'),
                    'detalle_etapas': [],
                }
            agrupado[insumo.id]['cantidad_bom_base'] += cantidad_escalada
            agrupado[insumo.id]['cantidad_total'] += cantidad_escalada
            agrupado[insumo.id]['detalle_etapas'].append(
                f"{item.get_etapa_uso_display()} ({cantidad_escalada} {insumo.unidad_medida})"
            )

        # 2. Insumos extra específicos de la personalización (si el pedido ya fue guardado)
        if self.pk:
            for extra in self.insumos_extra.select_related('insumo').all():
                insumo = extra.insumo
                cant_extra = extra.cantidad_extra.quantize(
                    Decimal('0.001'), rounding=ROUND_HALF_UP
                )
                if insumo.id not in agrupado:
                    agrupado[insumo.id] = {
                        'insumo': insumo,
                        'cantidad_bom_base': Decimal('0.000'),
                        'cantidad_extra': Decimal('0.000'),
                        'cantidad_total': Decimal('0.000'),
                        'detalle_etapas': [],
                    }
                agrupado[insumo.id]['cantidad_extra'] += cant_extra
                agrupado[insumo.id]['cantidad_total'] += cant_extra
                agrupado[insumo.id]['detalle_etapas'].append(
                    f"Extra Personalización: {extra.motivo} ({cant_extra} {insumo.unidad_medida})"
                )

        resultado = []
        for data in agrupado.values():
            insumo = data['insumo']
            requerido = data['cantidad_total']
            disponible = insumo.stock_actual
            deficit = max(Decimal('0.000'), requerido - disponible)
            costo_total_insumo = (requerido * insumo.costo_unitario).quantize(
                Decimal('1'), rounding=ROUND_HALF_UP
            )
            resultado.append({
                'insumo_id': insumo.id,
                'codigo_sku': insumo.codigo_sku,
                'nombre_insumo': insumo.nombre,
                'unidad_medida': insumo.unidad_medida,
                'cantidad_bom_base': data['cantidad_bom_base'],
                'cantidad_extra': data['cantidad_extra'],
                'cantidad_requerida': requerido,
                'stock_disponible': disponible,
                'stock_suficiente': disponible >= requerido or self.insumos_descontados,
                'deficit': deficit,
                'costo_unitario': insumo.costo_unitario,
                'costo_subtotal': costo_total_insumo,
                'origen_uso': ', '.join(data['detalle_etapas']),
            })
        return resultado

    def verificar_disponibilidad_bom(self):
        """
        Verifica si existe stock suficiente en bodega para cubrir toda la Lista de Materiales.
        Retorna `(es_factible: bool, faltantes: list, explosion: list)`.
        """
        explosion = self.obtener_explosion_bom()
        faltantes = [item for item in explosion if not item['stock_suficiente']]
        return (len(faltantes) == 0, faltantes, explosion)

    def recalcular_cotizacion(self, guardar=True):
        """
        Calcula automáticamente los montos de cotización del pedido personalizado:
        - Costo de insumos BOM (escalado por porciones + insumos extra)
        - Precio base proporcional a las porciones
        - Recargo por complejidad de diseño artístico
        - Costo de despacho (0 si es retiro en tienda)
        """
        explosion = self.obtener_explosion_bom()
        costo_bom = sum(
            (item['costo_subtotal'] for item in explosion), Decimal('0')
        ).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

        precio_proporcional = (
            self.producto_base.precio_base * self.factor_escala_porciones
        ).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

        # Sumar valor comercial de insumos extra (costo * 1.5 margen)
        recargo_extras = Decimal('0')
        if self.pk:
            for extra in self.insumos_extra.select_related('insumo').all():
                recargo_extras += (
                    extra.cantidad_extra * extra.insumo.costo_unitario * Decimal('1.5')
                )
        recargo_extras = recargo_extras.quantize(Decimal('1'), rounding=ROUND_HALF_UP)

        recargo_comp = (
            precio_proporcional * (self.factor_complejidad - Decimal('1.00'))
        ).quantize(Decimal('1'), rounding=ROUND_HALF_UP)

        despacho = (
            self.costo_despacho
            if self.modalidad_entrega == 'DESPACHO_DOMICILIO'
            else Decimal('0')
        )

        self.costo_insumos_estimado = costo_bom
        self.recargo_diseno = recargo_comp + recargo_extras
        self.costo_despacho = despacho
        self.precio_total = precio_proporcional + self.recargo_diseno + despacho

        if guardar and self.pk:
            PedidoPersonalizado.objects.filter(pk=self.pk).update(
                costo_insumos_estimado=self.costo_insumos_estimado,
                recargo_diseno=self.recargo_diseno,
                costo_despacho=self.costo_despacho,
                precio_total=self.precio_total,
            )
        return self.precio_total

    def save(self, *args, **kwargs):
        if not self.codigo_pedido:
            anio = timezone.now().year
            ultimo = PedidoPersonalizado.objects.filter(
                codigo_pedido__startswith=f"DA-{anio}-"
            ).order_by('-id').first()
            correlativo = 1
            if ultimo:
                try:
                    correlativo = int(ultimo.codigo_pedido.split('-')[-1]) + 1
                except (ValueError, IndexError):
                    correlativo = PedidoPersonalizado.objects.count() + 1
            self.codigo_pedido = f"DA-{anio}-{correlativo:04d}"

        if (not self.direccion_entrega or not self.direccion_entrega.strip()) and self.cliente_id:
            self.direccion_entrega = self.cliente.direccion_habitual or 'Retiro en Tienda Dulce Arte'
            self.comuna_entrega = self.cliente.comuna or 'Providencia'
        elif not self.direccion_entrega or not self.direccion_entrega.strip():
            self.direccion_entrega = 'Retiro en Tienda Dulce Arte'

        if not self.comuna_entrega or not self.comuna_entrega.strip():
            self.comuna_entrega = self.cliente.comuna if self.cliente_id and self.cliente.comuna else 'Providencia'

        if not self.sabor_bizcocho or not self.sabor_bizcocho.strip():
            self.sabor_bizcocho = 'Según Receta Base'
        if not self.relleno_principal or not self.relleno_principal.strip():
            self.relleno_principal = 'Según Receta BOM'
        if not self.cobertura_diseno or not self.cobertura_diseno.strip():
            self.cobertura_diseno = 'Presentación Estándar'
        if not self.descripcion_diseno or not self.descripcion_diseno.strip():
            nombre_prod = self.producto_base.nombre if self.producto_base_id else 'Producto'
            self.descripcion_diseno = f"Preparación estándar según receta de {nombre_prod}."

        # Calcular valores antes del primer guardado
        if self.producto_base_id:
            factor = self.factor_escala_porciones
            precio_prop = (self.producto_base.precio_base * factor).quantize(
                Decimal('1'), rounding=ROUND_HALF_UP
            )
            recargo_comp = (
                precio_prop * (self.factor_complejidad - Decimal('1.00'))
            ).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            despacho = (
                self.costo_despacho
                if self.modalidad_entrega == 'DESPACHO_DOMICILIO'
                else Decimal('0')
            )
            if not self.precio_total or self.precio_total == Decimal('0'):
                self.recargo_diseno = recargo_comp
                self.costo_despacho = despacho
                self.precio_total = precio_prop + recargo_comp + despacho

        super().save(*args, **kwargs)

    @transaction.atomic
    def descontar_insumos_bom(self, usuario=None):
        """
        Regla de Negocio Crítica (Funcionalidad 3):
        Ejecuta el descuento atómico de todos los insumos del BOM (receta base escalada +
        insumos extra de personalización) desde la bodega y genera los registros de
        trazabilidad en `MovimientoInventario`.
        """
        if self.insumos_descontados:
            return False, "Los insumos BOM de este pedido ya fueron descontados previamente."

        explosion = self.obtener_explosion_bom()
        if not explosion:
            raise ValidationError(
                f"El producto base '{self.producto_base.nombre}' no tiene componentes configurados en su Lista de Materiales (BOM)."
            )

        # Bloqueo pesimista (select_for_update) sobre los insumos involucrados
        insumo_ids = [item['insumo_id'] for item in explosion]
        insumos_bloqueados = {
            ins.id: ins
            for ins in Insumo.objects.select_for_update().filter(id__in=insumo_ids)
        }

        faltantes = []
        for item in explosion:
            insumo_bd = insumos_bloqueados[item['insumo_id']]
            if insumo_bd.stock_actual < item['cantidad_requerida']:
                deficit = item['cantidad_requerida'] - insumo_bd.stock_actual
                faltantes.append(
                    f"{insumo_bd.nombre}: requiere {item['cantidad_requerida']} {insumo_bd.unidad_medida}, "
                    f"disponible {insumo_bd.stock_actual} {insumo_bd.unidad_medida} (Déficit: {deficit} {insumo_bd.unidad_medida})"
                )

        if faltantes:
            raise ValidationError(
                "Stock insuficiente en bodega para ejecutar la Lista de Materiales (BOM): "
                + " | ".join(faltantes)
            )

        # Aplicar descuento y registrar movimientos de inventario (Kardex)
        for item in explosion:
            insumo_bd = insumos_bloqueados[item['insumo_id']]
            stock_previo = insumo_bd.stock_actual
            cantidad_salida = item['cantidad_requerida']
            insumo_bd.stock_actual = stock_previo - cantidad_salida
            insumo_bd.save(update_fields=['stock_actual', 'actualizado_en'])

            MovimientoInventario.objects.create(
                insumo=insumo_bd,
                tipo_movimiento='SALIDA_BOM_PEDIDO',
                cantidad=cantidad_salida,
                stock_anterior=stock_previo,
                stock_resultante=insumo_bd.stock_actual,
                pedido_asociado=self,
                usuario=usuario,
                motivo=(
                    f"Descuento automático BOM Pedido {self.codigo_pedido} "
                    f"({self.porciones_solicitadas} porc. {self.producto_base.nombre}) - {item['origen_uso']}"
                ),
            )

        self.insumos_descontados = True
        self.fecha_descuento_bom = timezone.now()
        if self.estado_comercial in ('COTIZACION', 'CONFIRMADO'):
            self.estado_comercial = 'EN_PRODUCCION'
        self.save(
            update_fields=[
                'insumos_descontados',
                'fecha_descuento_bom',
                'estado_comercial',
                'actualizado_en',
            ]
        )
        return True, f"Se descontaron exitosamente {len(explosion)} insumos de bodega según BOM."

    @transaction.atomic
    def cambiar_estado_kanban(self, nuevo_estado: str, usuario=None, comentario: str = ""):
        """
        Regla de Negocio Crítica (Funcionalidad 2 y 3):
        Transiciona el pedido en el Tablero Kanban del taller de cocina:
        `RECIBIDO` -> `EN_PREPARACION` -> `HORNEADO_DECORADO` -> `CONTROL_CALIDAD` -> `LISTO`.
        - Al pasar a `EN_PREPARACION` (o etapa posterior), descuenta automáticamente los insumos BOM si aún no se han descontado.
        - Al pasar a `LISTO`, marca control de calidad aprobado y actualiza estado comercial a `LISTO_DESPACHO`.
        - Registra la trazabilidad en `HistorialKanban`.
        """
        estados_validos = dict(self.ESTADO_KANBAN_CHOICES)
        if nuevo_estado not in estados_validos:
            raise ValidationError(f"Estado Kanban '{nuevo_estado}' no es válido.")

        if self.estado_comercial == 'CANCELADO':
            raise ValidationError("No se puede mover en el Kanban un pedido que está Cancelado.")

        estado_anterior = self.estado_kanban
        mensaje_bom = ""

        # Si avanza desde RECIBIDO hacia preparación/cocina y no tiene BOM descontado, descontar automáticamente
        if nuevo_estado in ('EN_PREPARACION', 'HORNEADO_DECORADO', 'CONTROL_CALIDAD', 'LISTO'):
            if not self.insumos_descontados:
                _, mensaje_bom = self.descontar_insumos_bom(usuario=usuario)

        self.estado_kanban = nuevo_estado

        if nuevo_estado in ('EN_PREPARACION', 'HORNEADO_DECORADO', 'CONTROL_CALIDAD'):
            self.estado_comercial = 'EN_PRODUCCION'
        elif nuevo_estado == 'LISTO':
            self.aprobado_calidad = True
            if self.estado_comercial != 'ENTREGADO':
                self.estado_comercial = 'LISTO_DESPACHO'

        if usuario and not self.pastelero_asignado:
            self.pastelero_asignado = usuario

        self.save()

        detalle_comentario = comentario or f"Cambio de etapa en taller a {estados_validos[nuevo_estado]}."
        if mensaje_bom:
            detalle_comentario = f"{detalle_comentario} [{mensaje_bom}]"

        HistorialKanban.objects.create(
            pedido=self,
            estado_anterior=estado_anterior,
            estado_nuevo=nuevo_estado,
            usuario=usuario,
            comentario=detalle_comentario,
        )
        return self


class InsumoExtraPedido(models.Model):
    """
    Ingredientes o materiales decorativos adicionales solicitados para personalizar un pedido,
    que se suman a la Lista de Materiales (BOM) base al cotizar y descontar inventario.
    """
    pedido = models.ForeignKey(
        PedidoPersonalizado,
        on_delete=models.CASCADE,
        related_name='insumos_extra',
        verbose_name='Pedido Personalizado'
    )
    insumo = models.ForeignKey(
        Insumo,
        on_delete=models.PROTECT,
        related_name='extras_pedidos',
        verbose_name='Insumo Adicional'
    )
    cantidad_extra = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        verbose_name='Cantidad Adicional'
    )
    motivo = models.CharField(
        max_length=140,
        default='Personalización de relleno / decoración especial',
        verbose_name='Especificación de Uso'
    )

    class Meta:
        verbose_name = 'Insumo Extra de Personalización'
        verbose_name_plural = 'Insumos Extra de Personalización'

    def __str__(self):
        return f"{self.pedido.codigo_pedido} + {self.cantidad_extra} {self.insumo.unidad_medida} de {self.insumo.nombre}"

    @property
    def costo_extra(self) -> Decimal:
        return (self.cantidad_extra * self.insumo.costo_unitario).quantize(
            Decimal('1'), rounding=ROUND_HALF_UP
        )


class MovimientoInventario(models.Model):
    """
    Kardex de Bodega (Funcionalidad 3):
    Registra de forma inmutable cada entrada de compra, salida automática por BOM de pedido,
    ajuste por merma/vencimiento o reversión.
    """
    TIPO_MOVIMIENTO_CHOICES = [
        ('ENTRADA_COMPRA', 'Entrada por Compra / Recepción Proveedor'),
        ('SALIDA_BOM_PEDIDO', 'Salida Automática por Lista de Materiales (BOM)'),
        ('AJUSTE_MERMA', 'Baja por Merma de Cocina o Vencimiento'),
        ('REVERSION_CANCELACION', 'Reingreso por Cancelación de Pedido'),
    ]

    insumo = models.ForeignKey(
        Insumo,
        on_delete=models.PROTECT,
        related_name='movimientos',
        verbose_name='Insumo'
    )
    tipo_movimiento = models.CharField(
        max_length=25,
        choices=TIPO_MOVIMIENTO_CHOICES,
        verbose_name='Tipo de Movimiento'
    )
    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name='Cantidad Movida'
    )
    stock_anterior = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name='Stock Antes del Movimiento'
    )
    stock_resultante = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name='Stock Resultante en Bodega'
    )
    pedido_asociado = models.ForeignKey(
        PedidoPersonalizado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos_inventario',
        verbose_name='Pedido Asociado (Trazabilidad BOM)'
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Responsable'
    )
    motivo = models.CharField(max_length=255, verbose_name='Glosa / Detalle de Trazabilidad')
    fecha_movimiento = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha y Hora Exacta'
    )

    class Meta:
        verbose_name = 'Movimiento de Inventario (Kardex BOM)'
        verbose_name_plural = 'Movimientos de Inventario (Kardex BOM)'
        ordering = ['-fecha_movimiento', '-id']

    def __str__(self):
        return (
            f"[{self.get_tipo_movimiento_display()}] {self.insumo.nombre}: "
            f"{self.cantidad} {self.insumo.unidad_medida} (Saldo: {self.stock_resultante})"
        )


class HistorialKanban(models.Model):
    """Bitácora de auditoría para los tiempos y cambios de etapa en el taller de cocina."""
    pedido = models.ForeignKey(
        PedidoPersonalizado,
        on_delete=models.CASCADE,
        related_name='historial_kanban',
        verbose_name='Pedido'
    )
    estado_anterior = models.CharField(
        max_length=25,
        choices=PedidoPersonalizado.ESTADO_KANBAN_CHOICES,
        verbose_name='Etapa Anterior'
    )
    estado_nuevo = models.CharField(
        max_length=25,
        choices=PedidoPersonalizado.ESTADO_KANBAN_CHOICES,
        verbose_name='Nueva Etapa Kanban'
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Pastelero / Usuario'
    )
    comentario = models.TextField(blank=True, verbose_name='Detalle Técnico / Observación')
    fecha_cambio = models.DateTimeField(auto_now_add=True, verbose_name='Fecha y Hora de Transición')

    class Meta:
        verbose_name = 'Historial de Flujo Kanban'
        verbose_name_plural = 'Historial de Flujo Kanban'
        ordering = ['-fecha_cambio', '-id']

    def __str__(self):
        return f"{self.pedido.codigo_pedido}: {self.estado_anterior} -> {self.estado_nuevo}"


# ==============================================================================
# 5. LOGÍSTICA DE RUTAS DE DESPACHO Y CONFIRMACIÓN CON FIRMA DIGITAL / FOTO
# ==============================================================================
class RutaDespacho(models.Model):
    """
    Hoja de Ruta de Despacho (Funcionalidad 4):
    Agrupa entregas por zona geográfica, repartidor y vehículo refrigerado.
    """
    ESTADO_RUTA_CHOICES = [
        ('PLANIFICADA', 'Planificada en Centro de Despacho'),
        ('EN_RUTA', 'En Ruta / Reparto Activo'),
        ('COMPLETADA', 'Ruta Completada'),
        ('CANCELADA', 'Cancelada'),
    ]

    codigo_ruta = models.CharField(
        max_length=25,
        unique=True,
        verbose_name='Código de Ruta'
    )
    nombre_ruta = models.CharField(
        max_length=120,
        verbose_name='Nombre / Sector de la Ruta'
    )
    repartidor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='rutas_asignadas',
        verbose_name='Repartidor Asignado'
    )
    vehiculo_patente = models.CharField(
        max_length=20,
        default='KRTW-88',
        verbose_name='Patente Vehículo'
    )
    vehiculo_refrigerado = models.BooleanField(
        default=True,
        verbose_name='Vehículo con Cámara Isotérmica (2°C - 6°C)'
    )
    temperatura_salida_c = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=Decimal('4.2'),
        verbose_name='Temperatura Cámara al Salir (°C)'
    )
    fecha_ruta = models.DateField(
        default=timezone.localdate,
        verbose_name='Fecha de Despacho'
    )
    hora_salida_programada = models.TimeField(
        default='09:30',
        verbose_name='Hora de Salida Programada'
    )
    estado_ruta = models.CharField(
        max_length=20,
        choices=ESTADO_RUTA_CHOICES,
        default='PLANIFICADA',
        verbose_name='Estado de la Ruta'
    )
    observaciones_logistica = models.TextField(
        blank=True,
        verbose_name='Instrucciones de Ruta y Estiba'
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ruta de Despacho'
        verbose_name_plural = 'Rutas de Despacho'
        ordering = ['-fecha_ruta', '-id']

    def __str__(self):
        return f"[{self.codigo_ruta}] {self.nombre_ruta} ({self.fecha_ruta})"

    @property
    def total_paradas(self) -> int:
        return self.entregas.count()

    @property
    def paradas_entregadas(self) -> int:
        return self.entregas.filter(estado_entrega='ENTREGADO').count()

    @property
    def porcentaje_completado(self) -> int:
        total = self.total_paradas
        if total == 0:
            return 0
        return int(round((self.paradas_entregadas / total) * 100))


class DespachoPedido(models.Model):
    """
    Parada individual de entrega dentro de una Ruta de Despacho (Funcionalidad 4).
    Permite confirmar la recepción final mediante Firma Digital (Canvas Base64)
    y/o Comprobante Fotográfico.
    """
    ESTADO_ENTREGA_CHOICES = [
        ('PENDIENTE', 'Pendiente de Salida'),
        ('EN_CAMINO', 'En Camino al Destino'),
        ('ENTREGADO', 'Entregado y Confirmado'),
        ('INCIDENCIA', 'Incidencia / Intento Fallido'),
    ]

    ruta = models.ForeignKey(
        RutaDespacho,
        on_delete=models.CASCADE,
        related_name='entregas',
        verbose_name='Ruta de Despacho'
    )
    pedido = models.OneToOneField(
        PedidoPersonalizado,
        on_delete=models.CASCADE,
        related_name='despacho',
        verbose_name='Pedido Asociado'
    )
    orden_parada = models.PositiveIntegerField(
        default=1,
        verbose_name='Orden de Parada en Ruta'
    )
    direccion_destino = models.CharField(
        max_length=220,
        verbose_name='Dirección Exacta de Entrega'
    )
    comuna_destino = models.CharField(
        max_length=80,
        verbose_name='Comuna'
    )
    telefono_contacto = models.CharField(
        max_length=30,
        verbose_name='Teléfono Receptor'
    )
    ventana_horaria = models.CharField(
        max_length=40,
        default='10:00 - 12:00',
        verbose_name='Ventana Horaria Comprometida'
    )
    estado_entrega = models.CharField(
        max_length=20,
        choices=ESTADO_ENTREGA_CHOICES,
        default='PENDIENTE',
        verbose_name='Estado de Entrega'
    )

    # Confirmación de Entrega con Firma Digital o Comprobante Fotográfico
    nombre_receptor = models.CharField(
        max_length=140,
        blank=True,
        verbose_name='Nombre Completo de Quien Recibe'
    )
    rut_receptor = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='RUT de Quien Recibe'
    )
    parentesco_o_cargo = models.CharField(
        max_length=60,
        blank=True,
        default='Cliente Titular',
        verbose_name='Relación con el Cliente (Titular, Familiar, Recepción Evento)'
    )
    firma_digital_base64 = models.TextField(
        blank=True,
        verbose_name='Firma Digital del Receptor (Data URI PNG Base64)'
    )
    comprobante_foto = models.ImageField(
        upload_to='comprobantes_entrega/',
        null=True,
        blank=True,
        verbose_name='Fotografía de Comprobante de Entrega'
    )
    temperatura_entrega_c = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        default=Decimal('4.5'),
        verbose_name='Temperatura del Producto al Entregar (°C)'
    )
    coordenadas_gps = models.CharField(
        max_length=60,
        blank=True,
        default='-33.4262, -70.6109',
        verbose_name='Georreferencia GPS de Entrega'
    )
    fecha_hora_confirmacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha y Hora Exacta de Confirmación'
    )
    observaciones_entrega = models.TextField(
        blank=True,
        verbose_name='Acta de Conformidad / Observaciones del Repartidor'
    )

    class Meta:
        verbose_name = 'Despacho y Confirmación de Pedido'
        verbose_name_plural = 'Despachos y Confirmaciones de Pedidos'
        ordering = ['ruta', 'orden_parada']

    def __str__(self):
        return (
            f"Parada #{self.orden_parada} [{self.ruta.codigo_ruta}] - "
            f"{self.pedido.codigo_pedido} ({self.get_estado_entrega_display()})"
        )

    @property
    def tiene_respaldo_digital(self) -> bool:
        """Verifica si cuenta con firma digital trazada o fotografía de comprobante."""
        return bool(self.firma_digital_base64 or self.comprobante_foto)

    @transaction.atomic
    def confirmar_entrega_digital(
        self,
        nombre_receptor: str,
        rut_receptor: str,
        firma_base64: str = "",
        comprobante_archivo=None,
        parentesco: str = "Cliente Titular",
        temperatura_c=None,
        observaciones: str = "",
        coordenadas: str = "",
        usuario=None,
    ):
        """
        Regla de Negocio Crítica (Funcionalidad 4):
        Confirma la entrega de un pedido exigiendo obligatoriamente Firma Digital
        (Canvas HTML5) o Comprobante Fotográfico, junto con la identificación del receptor.
        Actualiza el estado del pedido a ENTREGADO y cierra la Ruta si todas las paradas finalizaron.
        """
        if not nombre_receptor or not rut_receptor:
            raise ValidationError(
                "Debe indicar el nombre completo y RUT de la persona que recibe el pedido."
            )

        tiene_firma = bool(firma_base64 and firma_base64.strip().startswith('data:image/'))
        tiene_foto = bool(comprobante_archivo or self.comprobante_foto)

        if not tiene_firma and not tiene_foto:
            raise ValidationError(
                "Para confirmar la entrega es obligatorio adjuntar la Firma Digital del receptor "
                "o una Fotografía de Comprobante de Entrega."
            )

        self.nombre_receptor = nombre_receptor.strip()
        self.rut_receptor = rut_receptor.strip()
        self.parentesco_o_cargo = parentesco or 'Cliente Titular'
        if tiene_firma:
            self.firma_digital_base64 = firma_base64.strip()
        if comprobante_archivo:
            self.comprobante_foto = comprobante_archivo
        if temperatura_c is not None:
            self.temperatura_entrega_c = Decimal(str(temperatura_c))
        if coordenadas:
            self.coordenadas_gps = coordenadas
        self.observaciones_entrega = observaciones
        self.estado_entrega = 'ENTREGADO'
        self.fecha_hora_confirmacion = timezone.now()
        self.save()

        # Actualizar estado comercial y Kanban del pedido
        pedido = self.pedido
        if pedido.estado_kanban != 'LISTO':
            pedido.cambiar_estado_kanban(
                'LISTO',
                usuario=usuario,
                comentario="Marcado como LISTO al confirmar recepción conforme en destino.",
            )
        pedido.estado_comercial = 'ENTREGADO'
        pedido.abono_pagado = pedido.precio_total  # Pago total liquidado contra entrega
        pedido.save(update_fields=['estado_comercial', 'abono_pagado', 'actualizado_en'])

        # Si todas las entregas de la ruta están ENTREGADO, completar la ruta automáticamente
        ruta = self.ruta
        pendientes = ruta.entregas.exclude(estado_entrega='ENTREGADO').exists()
        if not pendientes:
            ruta.estado_ruta = 'COMPLETADA'
            ruta.save(update_fields=['estado_ruta'])
        elif ruta.estado_ruta == 'PLANIFICADA':
            ruta.estado_ruta = 'EN_RUTA'
            ruta.save(update_fields=['estado_ruta'])

        return self
