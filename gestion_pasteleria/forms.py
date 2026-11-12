"""
Formularios de Django con validaciones de negocio flexibles y estilos Bootstrap 5
para las operaciones CRUD del sistema Dulce Arte (Insumos, Recetas BOM, Productos y Ventas/Pedidos).
"""

from decimal import Decimal
from datetime import timedelta
from django import forms
from django.utils import timezone
from .models import (
    PerfilUsuario,
    Cliente,
    CategoriaInsumo,
    Insumo,
    ProductoPasteleria,
    ItemBOM,
    PedidoPersonalizado,
    InsumoExtraPedido,
    RutaDespacho,
    DespachoPedido,
)


class BootstrapFormMixin:
    """Aplica clases CSS modernas y soporte flexible de decimales a todos los widgets."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault('class', 'form-select')
            else:
                widget.attrs.setdefault('class', 'form-control')
            if isinstance(widget, forms.NumberInput):
                widget.attrs['step'] = 'any'


class ClienteForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            'rut',
            'nombre_completo',
            'tipo_cliente',
            'email',
            'telefono',
            'direccion_habitual',
            'comuna',
            'preferencias_alimentarias',
            'notas',
        ]
        widgets = {
            'rut': forms.TextInput(attrs={'placeholder': 'Ej: 18.456.789-K'}),
            'preferencias_alimentarias': forms.TextInput(
                attrs={'placeholder': 'Ej: Intolerancia a la lactosa, Sin trazas de maní'}
            ),
            'notas': forms.Textarea(attrs={'rows': 2}),
        }


class InsumoForm(BootstrapFormMixin, forms.ModelForm):
    nueva_categoria = forms.CharField(
        required=False,
        label='Nueva Categoría (Opcional)',
        widget=forms.TextInput(
            attrs={'placeholder': 'Ej: Panadería y Sándwiches, Quesos y Fiambres...'}
        ),
    )

    class Meta:
        model = Insumo
        fields = [
            'nombre',
            'codigo_sku',
            'categoria',
            'nueva_categoria',
            'unidad_medida',
            'stock_actual',
            'stock_minimo',
            'costo_unitario',
            'proveedor',
            'lote_actual',
            'fecha_vencimiento',
            'ubicacion_bodega',
            'activo',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej: Queso Gauda, Pan Amasado, Jamón Pierna...'}),
            'codigo_sku': forms.TextInput(attrs={'placeholder': 'Opcional (se genera solo)'}),
            'fecha_vencimiento': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['codigo_sku'].required = False
        self.fields['categoria'].required = False
        self.fields['categoria'].empty_label = 'Panadería, Salados e Insumos Generales (Automática)'
        self.fields['unidad_medida'].required = False
        self.fields['stock_actual'].required = False
        self.fields['stock_minimo'].required = False
        self.fields['costo_unitario'].required = False
        self.fields['proveedor'].required = False
        self.fields['lote_actual'].required = False
        self.fields['ubicacion_bodega'].required = False
        self.fields['activo'].required = False

        if not self.instance.pk:
            self.initial['unidad_medida'] = 'UNIDAD'
            self.initial['stock_actual'] = 50
            self.initial['stock_minimo'] = 5
            self.initial['costo_unitario'] = 1000
            self.initial['activo'] = True

    def clean_codigo_sku(self):
        sku = (self.cleaned_data.get('codigo_sku') or '').strip().upper()
        if not sku:
            return ''
        qs = Insumo.objects.filter(codigo_sku=sku)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            # Si el usuario ingresó un SKU repetido al crear, generar sufijo único automáticamente
            correlativo = Insumo.objects.count() + 1
            candidato = f"{sku[:24]}-{correlativo:02d}"
            while Insumo.objects.filter(codigo_sku=candidato).exclude(pk=self.instance.pk).exists():
                correlativo += 1
                candidato = f"{sku[:24]}-{correlativo:02d}"
            return candidato
        return sku

    def clean(self):
        cleaned = super().clean()
        nueva_cat_nombre = (cleaned.get('nueva_categoria') or '').strip()
        if nueva_cat_nombre:
            cat_obj, _ = CategoriaInsumo.objects.get_or_create(
                nombre=nueva_cat_nombre,
                defaults={
                    'descripcion': f'Categoría creada desde Bodega: {nueva_cat_nombre}',
                    'es_perecible': True,
                    'requiere_cadena_frio': False,
                },
            )
            cleaned['categoria'] = cat_obj
        elif not cleaned.get('categoria'):
            cat_obj, _ = CategoriaInsumo.objects.get_or_create(
                nombre='Panadería, Salados e Insumos Generales',
                defaults={
                    'descripcion': 'Quesos, panes, fiambres, masas e insumos generales de cocina',
                    'es_perecible': True,
                    'requiere_cadena_frio': False,
                },
            )
            cleaned['categoria'] = cat_obj

        if not cleaned.get('unidad_medida'):
            cleaned['unidad_medida'] = 'UNIDAD'
        if cleaned.get('stock_actual') is None:
            cleaned['stock_actual'] = Decimal('50.000')
        if cleaned.get('stock_minimo') is None:
            cleaned['stock_minimo'] = Decimal('5.000')
        if cleaned.get('costo_unitario') is None:
            cleaned['costo_unitario'] = Decimal('1000.00')
        if not cleaned.get('proveedor'):
            cleaned['proveedor'] = 'Distribuidora Gourmet Chile'
        if not cleaned.get('lote_actual'):
            cleaned['lote_actual'] = 'LOTE-2026-A1'
        if not cleaned.get('ubicacion_bodega'):
            cleaned['ubicacion_bodega'] = 'Estante Secos A1'
        if not self.instance.pk:
            cleaned['activo'] = True
        elif 'activo' not in self.data:
            cleaned['activo'] = True

        return cleaned


class ProductoPasteleriaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ProductoPasteleria
        fields = [
            'nombre',
            'codigo',
            'categoria_producto',
            'porciones_base',
            'precio_base',
            'tiempo_elaboracion_horas',
            'requiere_refrigeracion',
            'descripcion',
            'instrucciones_receta',
            'activo',
        ]
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej: Pan con queso y jamón, Torta Tres Leches...'}),
            'codigo': forms.TextInput(attrs={'placeholder': 'Opcional (se genera solo, ej: REC-PAN-004)'}),
            'descripcion': forms.Textarea(
                attrs={'rows': 2, 'placeholder': 'Opcional: descripción de la receta o producto...'}
            ),
            'instrucciones_receta': forms.Textarea(
                attrs={'rows': 2, 'placeholder': 'Opcional: pasos de preparación en cocina...'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['codigo'].required = False
        self.fields['categoria_producto'].required = False
        self.fields['porciones_base'].required = False
        self.fields['precio_base'].required = False
        self.fields['tiempo_elaboracion_horas'].required = False
        self.fields['requiere_refrigeracion'].required = False
        self.fields['descripcion'].required = False
        self.fields['instrucciones_receta'].required = False
        self.fields['activo'].required = False

        if not self.instance.pk:
            self.initial['categoria_producto'] = 'PANADERIA_SANDWICH'
            self.initial['porciones_base'] = 1
            self.initial['precio_base'] = 3500
            self.initial['tiempo_elaboracion_horas'] = 0.5
            self.initial['requiere_refrigeracion'] = False
            self.initial['activo'] = True

    def clean_codigo(self):
        cod = (self.cleaned_data.get('codigo') or '').strip().upper()
        if not cod:
            return ''
        qs = ProductoPasteleria.objects.filter(codigo=cod)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            correlativo = ProductoPasteleria.objects.count() + 1
            candidato = f"{cod[:24]}-{correlativo:02d}"
            while ProductoPasteleria.objects.filter(codigo=candidato).exclude(pk=self.instance.pk).exists():
                correlativo += 1
                candidato = f"{cod[:24]}-{correlativo:02d}"
            return candidato
        return cod

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('categoria_producto'):
            cleaned['categoria_producto'] = 'TORTA_AUTOR'
        if not cleaned.get('porciones_base') or cleaned.get('porciones_base') < 1:
            cleaned['porciones_base'] = 1
        if cleaned.get('precio_base') is None:
            cleaned['precio_base'] = Decimal('3500')
        if cleaned.get('tiempo_elaboracion_horas') is None:
            cleaned['tiempo_elaboracion_horas'] = Decimal('1.0')
        if not cleaned.get('descripcion'):
            nombre = cleaned.get('nombre') or 'Producto'
            cleaned['descripcion'] = f"Receta y producto elaborado en cocina: {nombre}."
        if not self.instance.pk:
            cleaned['activo'] = True
        elif 'activo' not in self.data:
            cleaned['activo'] = True
        return cleaned


class ItemBOMForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ItemBOM
        fields = [
            'producto',
            'insumo',
            'cantidad_requerida',
            'etapa_uso',
            'merma_tecnica_pct',
            'notas_tecnicas',
        ]
        widgets = {
            'notas_tecnicas': forms.TextInput(attrs={'placeholder': 'Opcional: ej. laminado, horneado...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['etapa_uso'].required = False
        self.fields['merma_tecnica_pct'].required = False
        self.fields['notas_tecnicas'].required = False
        if not self.instance.pk:
            self.initial['cantidad_requerida'] = 1
            self.initial['merma_tecnica_pct'] = 0
            self.initial['etapa_uso'] = 'RELLENO'

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('etapa_uso'):
            cleaned['etapa_uso'] = 'BATIDO_MASA'
        if cleaned.get('merma_tecnica_pct') is None:
            cleaned['merma_tecnica_pct'] = Decimal('0.00')
        return cleaned


class PedidoPersonalizadoForm(BootstrapFormMixin, forms.ModelForm):
    nuevo_cliente_nombre = forms.CharField(
        required=False,
        label='O Nombre de Cliente Rápido (Venta Directa)',
        widget=forms.TextInput(
            attrs={'placeholder': 'Ej: Cliente Mesón / Juan Pérez (si no seleccionas cliente de la lista)'}
        ),
    )

    class Meta:
        model = PedidoPersonalizado
        fields = [
            'cliente',
            'nuevo_cliente_nombre',
            'producto_base',
            'pastelero_asignado',
            'porciones_solicitadas',
            'sabor_bizcocho',
            'relleno_principal',
            'cobertura_diseno',
            'nivel_complejidad',
            'dedicatoria_texto',
            'descripcion_diseno',
            'alergias_considerar',
            'imagen_referencia',
            'fecha_entrega_comprometida',
            'modalidad_entrega',
            'direccion_entrega',
            'comuna_entrega',
            'prioridad',
            'estado_comercial',
            'abono_pagado',
        ]
        widgets = {
            'fecha_entrega_comprometida': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'descripcion_diseno': forms.Textarea(
                attrs={
                    'rows': 2,
                    'placeholder': 'Opcional: Detalle de preparación, colores o especificaciones del pedido...',
                }
            ),
            'dedicatoria_texto': forms.TextInput(
                attrs={'placeholder': 'Opcional: Ej. ¡Feliz Cumpleaños!'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cliente'].required = False
        self.fields['cliente'].empty_label = 'Venta Directa en Mesón / Cliente General (Automático)'
        self.fields['porciones_solicitadas'].required = False
        self.fields['sabor_bizcocho'].required = False
        self.fields['relleno_principal'].required = False
        self.fields['cobertura_diseno'].required = False
        self.fields['nivel_complejidad'].required = False
        self.fields['descripcion_diseno'].required = False
        self.fields['fecha_entrega_comprometida'].required = False
        self.fields['modalidad_entrega'].required = False
        self.fields['direccion_entrega'].required = False
        self.fields['comuna_entrega'].required = False
        self.fields['prioridad'].required = False
        self.fields['estado_comercial'].required = False
        self.fields['abono_pagado'].required = False

        self.fields['fecha_entrega_comprometida'].input_formats = [
            '%Y-%m-%dT%H:%M',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
        ]
        if not self.instance.pk:
            entrega_default = (timezone.localtime() + timedelta(days=1)).replace(
                minute=0, second=0, microsecond=0
            )
            self.initial['fecha_entrega_comprometida'] = entrega_default.strftime('%Y-%m-%dT%H:%M')
            self.initial['porciones_solicitadas'] = 1
            self.initial['nivel_complejidad'] = 'ESTANDAR'
            self.initial['modalidad_entrega'] = 'RETIRO_TIENDA'
            self.initial['estado_comercial'] = 'CONFIRMADO'

    def clean(self):
        cleaned = super().clean()
        nuevo_nombre = (cleaned.get('nuevo_cliente_nombre') or '').strip()
        if nuevo_nombre:
            cliente_obj = Cliente.objects.filter(nombre_completo__iexact=nuevo_nombre).first()
            if not cliente_obj:
                correlativo = Cliente.objects.count() + 100
                rut_auto = f"99.{correlativo:03d}.{correlativo:03d}-K"
                while Cliente.objects.filter(rut=rut_auto).exists():
                    correlativo += 1
                    rut_auto = f"99.{correlativo:03d}.{correlativo:03d}-K"
                cliente_obj = Cliente.objects.create(
                    rut=rut_auto,
                    nombre_completo=nuevo_nombre,
                    tipo_cliente='PARTICULAR',
                    email='venta.meson@dulcearte.cl',
                    telefono='+56 9 0000 0000',
                    direccion_habitual='Retiro en Tienda Dulce Arte',
                    comuna='Providencia',
                )
            cleaned['cliente'] = cliente_obj
        elif not cleaned.get('cliente'):
            cliente_general, _ = Cliente.objects.get_or_create(
                rut='11.111.111-1',
                defaults={
                    'nombre_completo': 'Cliente General / Venta en Mesón',
                    'tipo_cliente': 'PARTICULAR',
                    'email': 'meson@dulcearte.cl',
                    'telefono': '+56 9 1111 1111',
                    'direccion_habitual': 'Retiro en Local Dulce Arte',
                    'comuna': 'Providencia',
                },
            )
            cleaned['cliente'] = cliente_general

        prod = cleaned.get('producto_base')
        if not cleaned.get('porciones_solicitadas') or cleaned.get('porciones_solicitadas') < 1:
            cleaned['porciones_solicitadas'] = prod.porciones_base if prod else 1

        if not cleaned.get('sabor_bizcocho'):
            cleaned['sabor_bizcocho'] = f"Masa / Base de {prod.nombre}" if prod else 'Según Receta Base'
        if not cleaned.get('relleno_principal'):
            cleaned['relleno_principal'] = 'Ingredientes según Receta BOM'
        if not cleaned.get('cobertura_diseno'):
            cleaned['cobertura_diseno'] = 'Presentación Estándar'
        if not cleaned.get('nivel_complejidad'):
            cleaned['nivel_complejidad'] = 'ESTANDAR'
        if not cleaned.get('descripcion_diseno'):
            cleaned['descripcion_diseno'] = (
                f"Elaboración y venta de {prod.nombre}." if prod else 'Preparación estándar según receta.'
            )
        if not cleaned.get('fecha_entrega_comprometida'):
            cleaned['fecha_entrega_comprometida'] = timezone.now() + timedelta(hours=2)
        if not cleaned.get('modalidad_entrega'):
            cleaned['modalidad_entrega'] = 'RETIRO_TIENDA'

        cliente_sel = cleaned.get('cliente')
        if not cleaned.get('direccion_entrega'):
            if cleaned.get('modalidad_entrega') == 'RETIRO_TIENDA':
                cleaned['direccion_entrega'] = 'Retiro en Tienda Dulce Arte'
            elif cliente_sel and cliente_sel.direccion_habitual:
                cleaned['direccion_entrega'] = cliente_sel.direccion_habitual
            else:
                cleaned['direccion_entrega'] = 'Retiro en Tienda Dulce Arte'

        if not cleaned.get('comuna_entrega'):
            cleaned['comuna_entrega'] = (
                cliente_sel.comuna if cliente_sel and cliente_sel.comuna else 'Providencia'
            )
        if not cleaned.get('prioridad'):
            cleaned['prioridad'] = 'NORMAL'
        if not cleaned.get('estado_comercial'):
            cleaned['estado_comercial'] = 'CONFIRMADO'
        if cleaned.get('abono_pagado') is None:
            cleaned['abono_pagado'] = Decimal('0')

        return cleaned


class InsumoExtraPedidoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = InsumoExtraPedido
        fields = ['insumo', 'cantidad_extra', 'motivo']


class RutaDespachoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = RutaDespacho
        fields = [
            'codigo_ruta',
            'nombre_ruta',
            'repartidor',
            'vehiculo_patente',
            'vehiculo_refrigerado',
            'temperatura_salida_c',
            'fecha_ruta',
            'hora_salida_programada',
            'estado_ruta',
            'observaciones_logistica',
        ]
        widgets = {
            'fecha_ruta': forms.DateInput(attrs={'type': 'date'}),
            'hora_salida_programada': forms.TimeInput(attrs={'type': 'time'}),
            'observaciones_logistica': forms.Textarea(attrs={'rows': 2}),
        }


class DespachoPedidoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DespachoPedido
        fields = [
            'ruta',
            'pedido',
            'orden_parada',
            'direccion_destino',
            'comuna_destino',
            'telefono_contacto',
            'ventana_horaria',
        ]


class CategoriaInsumoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CategoriaInsumo
        fields = ['nombre', 'descripcion', 'es_perecible', 'requiere_cadena_frio']


class PerfilUsuarioForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PerfilUsuario
        fields = ['usuario', 'rol', 'rut', 'telefono', 'turno', 'especialidad_pastelera', 'activo']
