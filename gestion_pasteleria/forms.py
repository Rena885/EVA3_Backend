"""
Formularios de Django con validaciones de negocio y estilos Bootstrap 5
para las operaciones CRUD del sistema Dulce Arte.
"""

from django import forms
from django.utils import timezone
from datetime import timedelta
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
    """Aplica clases CSS modernas a todos los widgets del formulario."""
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
    class Meta:
        model = Insumo
        fields = [
            'codigo_sku',
            'nombre',
            'categoria',
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
            'fecha_vencimiento': forms.DateInput(attrs={'type': 'date'}),
        }


class ProductoPasteleriaForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ProductoPasteleria
        fields = [
            'codigo',
            'nombre',
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
            'descripcion': forms.Textarea(attrs={'rows': 2}),
            'instrucciones_receta': forms.Textarea(attrs={'rows': 3}),
        }


class ItemBOMForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ItemBOM
        fields = [
            'producto',
            'etapa_uso',
            'insumo',
            'cantidad_requerida',
            'merma_tecnica_pct',
            'notas_tecnicas',
        ]


class PedidoPersonalizadoForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = PedidoPersonalizado
        fields = [
            'cliente',
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
                    'rows': 3,
                    'placeholder': 'Detalle colores, pisos, flores, figuras modeladas o temática del evento...',
                }
            ),
            'dedicatoria_texto': forms.TextInput(
                attrs={'placeholder': 'Ej: ¡Feliz Aniversario Camila & Diego!'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha_entrega_comprometida'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S']
        if not self.instance.pk:
            entrega_default = (timezone.localtime() + timedelta(days=2)).replace(
                minute=0, second=0, microsecond=0
            )
            self.initial['fecha_entrega_comprometida'] = entrega_default.strftime('%Y-%m-%dT%H:%M')


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

