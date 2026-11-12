"""
Vistas Web Fullstack de Dulce Arte.
Implementa todos los flujos requeridos por el Caso 3 y la Rúbrica de Evaluación:
- Autenticación, manejo de sesiones y control por roles (Criterio 4).
- CRUD completo y Cotizador de Pedidos Personalizados con explosión BOM (Criterio 3 - Func. 1).
- Tablero Kanban Digital del Taller de Cocina (Criterio 3 - Func. 2).
- Gestión de Bodega, Recetas y Descuento Automático de Inventario vía BOM (Criterio 3 - Func. 3).
- Gestión de Rutas de Despacho y Confirmación con Firma Digital / Comprobante Fotográfico (Criterio 3 - Func. 4).
"""

from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Sum, Count, F, Q
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
    MovimientoInventario,
    HistorialKanban,
    RutaDespacho,
    DespachoPedido,
)
from .forms import (
    ClienteForm,
    CategoriaInsumoForm,
    PerfilUsuarioForm,
    InsumoForm,
    ProductoPasteleriaForm,
    ItemBOMForm,
    PedidoPersonalizadoForm,
    InsumoExtraPedidoForm,
    RutaDespachoForm,
    DespachoPedidoForm,
)


# ==============================================================================
# DECORADOR AUXILIAR DE PERMISOS POR ROL (CRITERIO 4 RÚBRICA)
# ==============================================================================
def obtener_rol_usuario(user) -> str:
    if not user.is_authenticated:
        return 'ANONIMO'
    if hasattr(user, 'perfil'):
        return user.perfil.rol
    if user.is_superuser:
        return 'ADMIN'
    return 'VENTAS'


def requiere_roles(*roles_permitidos):
    """Restringe el acceso a vistas operativas según el rol del usuario autenticado."""
    def decorator(view_func):
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            rol_actual = obtener_rol_usuario(request.user)
            if rol_actual == 'ADMIN' or rol_actual in roles_permitidos:
                return view_func(request, *args, **kwargs)
            messages.warning(
                request,
                f"Acceso restringido: Tu rol actual ({rol_actual}) no posee permisos para modificar este módulo. "
                f"Roles autorizados: {', '.join(roles_permitidos)}.",
            )
            return redirect('dashboard')
        return _wrapped_view
    return decorator


# ==============================================================================
# 1. AUTENTICACIÓN, SESIONES Y CAMBIO RÁPIDO DE ROL DEMO
# ==============================================================================
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            nombre = user.get_full_name() or user.username
            messages.success(request, f"¡Bienvenido(a) a Dulce Arte, {nombre}! Sesión iniciada correctamente.")
            next_url = request.GET.get('next') or 'dashboard'
            return redirect(next_url)
        else:
            messages.error(request, "Credenciales incorrectas. Verifica tu usuario y contraseña.")

    usuarios_demo = User.objects.select_related('perfil').filter(is_active=True).order_by('id')[:6]
    return render(request, 'gestion_pasteleria/login.html', {'usuarios_demo': usuarios_demo})


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "Has cerrado sesión de forma segura.")
    return redirect('login')


@login_required
def cambiar_rol_demo_view(request):
    """
    Permite durante la defensa académica cambiar rápidamente el rol operativo
    de la sesión actual para demostrar los permisos de Ventas, Cocina, Bodega, Logística y Admin.
    """
    if request.method == 'POST':
        nuevo_rol = request.POST.get('rol', 'ADMIN')
        roles_validos = dict(PerfilUsuario.ROL_CHOICES)
        if nuevo_rol in roles_validos:
            perfil, _ = PerfilUsuario.objects.get_or_create(usuario=request.user)
            perfil.rol = nuevo_rol
            perfil.save(update_fields=['rol'])
            messages.success(
                request,
                f"Rol de sesión actualizado a: {roles_validos[nuevo_rol]}.",
            )
            referer = request.META.get('HTTP_REFERER', '')
            if nuevo_rol != 'ADMIN' and '/administracion' in referer:
                return redirect('dashboard')
    return redirect(request.META.get('HTTP_REFERER', 'dashboard'))


# ==============================================================================
# 2. DASHBOARD PRINCIPAL END-TO-END (VISTA DE PROCESOS Y ESCENARIOS 4+1)
# ==============================================================================
@login_required
def dashboard_view(request):
    total_pedidos = PedidoPersonalizado.objects.count()
    pedidos_activos = PedidoPersonalizado.objects.exclude(
        estado_comercial__in=['ENTREGADO', 'CANCELADO']
    ).select_related('cliente', 'producto_base')

    ingresos_totales = (
        PedidoPersonalizado.objects.exclude(estado_comercial='CANCELADO').aggregate(
            total=Sum('precio_total')
        )['total']
        or Decimal('0')
    )

    insumos_criticos = Insumo.objects.filter(
        activo=True, stock_actual__lte=F('stock_minimo')
    ).select_related('categoria')

    hoy = timezone.localdate()
    insumos_por_vencer = Insumo.objects.filter(
        activo=True,
        fecha_vencimiento__isnull=False,
        fecha_vencimiento__lte=hoy + timezone.timedelta(days=7),
    ).order_by('fecha_vencimiento')

    # Conteo por etapa Kanban
    resumen_kanban = []
    for codigo, etiqueta in PedidoPersonalizado.ESTADO_KANBAN_CHOICES:
        cantidad = PedidoPersonalizado.objects.filter(
            estado_kanban=codigo
        ).exclude(estado_comercial='CANCELADO').count()
        resumen_kanban.append({
            'codigo': codigo,
            'etiqueta': etiqueta,
            'cantidad': cantidad,
        })

    ultimos_movimientos = MovimientoInventario.objects.select_related(
        'insumo', 'pedido_asociado', 'usuario'
    )[:8]

    entregas_recientes = DespachoPedido.objects.select_related(
        'ruta', 'pedido__cliente', 'pedido__producto_base'
    ).order_by('estado_entrega', 'ruta__fecha_ruta', 'orden_parada')[:6]

    context = {
        'total_pedidos': total_pedidos,
        'pedidos_activos_count': pedidos_activos.count(),
        'pedidos_proximos': pedidos_activos.order_by('fecha_entrega_comprometida')[:6],
        'ingresos_totales': ingresos_totales,
        'insumos_criticos': insumos_criticos,
        'insumos_por_vencer': insumos_por_vencer,
        'resumen_kanban': resumen_kanban,
        'ultimos_movimientos': ultimos_movimientos,
        'entregas_recientes': entregas_recientes,
        'total_clientes': Cliente.objects.count(),
        'total_productos': ProductoPasteleria.objects.filter(activo=True).count(),
    }
    return render(request, 'gestion_pasteleria/dashboard.html', context)


# ==============================================================================
# 3. FUNCIONALIDAD 1: COTIZACIÓN Y REGISTRO DE PEDIDOS PERSONALIZADOS
# ==============================================================================
@requiere_roles('ADMIN', 'VENTAS', 'COCINA', 'BODEGA')
def pedidos_list_view(request):
    estado_kanban = request.GET.get('estado_kanban', '')
    estado_comercial = request.GET.get('estado_comercial', '')
    q = request.GET.get('q', '').strip()

    pedidos = PedidoPersonalizado.objects.select_related(
        'cliente', 'producto_base', 'vendedor', 'pastelero_asignado'
    ).all()

    if estado_kanban:
        pedidos = pedidos.filter(estado_kanban=estado_kanban)
    if estado_comercial:
        pedidos = pedidos.filter(estado_comercial=estado_comercial)
    if q:
        pedidos = pedidos.filter(
            Q(codigo_pedido__icontains=q)
            | Q(cliente__nombre_completo__icontains=q)
            | Q(cliente__rut__icontains=q)
            | Q(producto_base__nombre__icontains=q)
            | Q(sabor_bizcocho__icontains=q)
            | Q(relleno_principal__icontains=q)
        )

    productos_disponibles = ProductoPasteleria.objects.filter(activo=True).prefetch_related('items_bom__insumo').order_by('nombre')
    clientes_disponibles = Cliente.objects.all().order_by('nombre_completo')

    context = {
        'pedidos': pedidos,
        'filtro_kanban': estado_kanban,
        'filtro_comercial': estado_comercial,
        'busqueda': q,
        'estados_kanban': PedidoPersonalizado.ESTADO_KANBAN_CHOICES,
        'estados_comerciales': PedidoPersonalizado.ESTADO_COMERCIAL_CHOICES,
        'productos_disponibles': productos_disponibles,
        'clientes_disponibles': clientes_disponibles,
    }
    return render(request, 'gestion_pasteleria/pedidos_list.html', context)


@requiere_roles('ADMIN', 'VENTAS', 'BODEGA', 'COCINA')
def pedido_crear_view(request):
    if request.method == 'POST':
        form = PedidoPersonalizadoForm(request.POST, request.FILES)
        if form.is_valid():
            pedido = form.save(commit=False)
            pedido.vendedor = request.user
            pedido.save()
            pedido.recalcular_cotizacion(guardar=True)

            # Registrar estado inicial en Historial Kanban
            HistorialKanban.objects.create(
                pedido=pedido,
                estado_anterior='RECIBIDO',
                estado_nuevo=pedido.estado_kanban,
                usuario=request.user,
                comentario='Cotización / venta registrada en el sistema.',
            )

            # Si el usuario agregó un insumo extra opcional en el formulario rápido
            insumo_extra_id = request.POST.get('extra_insumo_id')
            extra_cantidad = request.POST.get('extra_cantidad')
            extra_motivo = request.POST.get('extra_motivo', '').strip()
            if insumo_extra_id and extra_cantidad:
                try:
                    ins_obj = Insumo.objects.get(pk=insumo_extra_id)
                    cant_dec = Decimal(str(extra_cantidad))
                    if cant_dec > 0:
                        InsumoExtraPedido.objects.create(
                            pedido=pedido,
                            insumo=ins_obj,
                            cantidad_extra=cant_dec,
                            motivo=extra_motivo or 'Ingrediente extra de personalización',
                        )
                        pedido.recalcular_cotizacion(guardar=True)
                except Exception:
                    pass

            # Si se solicitó descontar insumos BOM inmediatamente al vender
            descontar_inmediato = request.POST.get('descontar_bom_inmediato') == '1'
            msg_bom = ''
            if descontar_inmediato and (pedido.producto_base.items_bom.exists() or pedido.insumos_extra.exists()):
                try:
                    ok, detalle_bom = pedido.descontar_insumos_bom(usuario=request.user)
                    if ok:
                        msg_bom = f" ({detalle_bom})"
                except ValidationError as exc:
                    messages.warning(
                        request,
                        f"El pedido fue creado, pero el descuento automático BOM quedó pendiente: {exc.message}",
                    )

            messages.success(
                request,
                f"Venta / Pedido {pedido.codigo_pedido} ('{pedido.producto_base.nombre}') creado exitosamente. "
                f"Total: ${pedido.precio_total:,.0f} CLP.{msg_bom}",
            )
            return redirect('pedido_detalle', pk=pedido.pk)
        else:
            errores = '; '.join([f"{k}: {', '.join(v)}" for k, v in form.errors.items()])
            messages.error(request, f"Por favor verifica los datos del pedido: {errores}")
    else:
        initial_data = {}
        prod_pre = request.GET.get('producto')
        if prod_pre:
            prod_obj = ProductoPasteleria.objects.filter(pk=prod_pre, activo=True).first()
            if prod_obj:
                initial_data['producto_base'] = prod_obj.pk
                initial_data['porciones_solicitadas'] = prod_obj.porciones_base
                initial_data['sabor_bizcocho'] = f"Receta {prod_obj.nombre}"
                initial_data['relleno_principal'] = 'Ingredientes según Receta BOM'
                initial_data['cobertura_diseno'] = 'Presentación Estándar'
                initial_data['descripcion_diseno'] = prod_obj.descripcion or f"Elaboración de {prod_obj.nombre}"
        form = PedidoPersonalizadoForm(initial=initial_data)

    productos_catalogo = ProductoPasteleria.objects.filter(activo=True).prefetch_related('items_bom__insumo')
    insumos_disponibles = Insumo.objects.filter(activo=True).order_by('nombre')
    return render(
        request,
        'gestion_pasteleria/pedido_form.html',
        {
            'form': form,
            'titulo': 'Registrar Venta / Nuevo Pedido o Cotización',
            'productos_catalogo': productos_catalogo,
            'insumos_disponibles': insumos_disponibles,
        },
    )


@requiere_roles('ADMIN', 'VENTAS')
def pedido_editar_view(request, pk):
    pedido = get_object_or_404(PedidoPersonalizado, pk=pk)
    if request.method == 'POST':
        form = PedidoPersonalizadoForm(request.POST, request.FILES, instance=pedido)
        if form.is_valid():
            pedido = form.save()
            pedido.recalcular_cotizacion(guardar=True)
            messages.success(
                request,
                f"Pedido {pedido.codigo_pedido} actualizado y cotización recalculada (${pedido.precio_total:,.0f} CLP).",
            )
            return redirect('pedido_detalle', pk=pedido.pk)
    else:
        form = PedidoPersonalizadoForm(instance=pedido)

    productos_catalogo = ProductoPasteleria.objects.filter(activo=True).prefetch_related('items_bom__insumo')
    insumos_disponibles = Insumo.objects.filter(activo=True).order_by('nombre')
    return render(
        request,
        'gestion_pasteleria/pedido_form.html',
        {
            'form': form,
            'pedido': pedido,
            'titulo': f'Editar Pedido Personalizado {pedido.codigo_pedido}',
            'productos_catalogo': productos_catalogo,
            'insumos_disponibles': insumos_disponibles,
        },
    )


@requiere_roles('ADMIN', 'VENTAS', 'COCINA', 'BODEGA')
def pedido_detalle_view(request, pk):
    pedido = get_object_or_404(
        PedidoPersonalizado.objects.select_related(
            'cliente', 'producto_base', 'vendedor', 'pastelero_asignado'
        ).prefetch_related('insumos_extra__insumo', 'historial_kanban__usuario', 'movimientos_inventario__insumo'),
        pk=pk,
    )
    es_factible, faltantes, explosion_bom = pedido.verificar_disponibilidad_bom()
    extra_form = InsumoExtraPedidoForm()
    rol_actual = obtener_rol_usuario(request.user)

    if request.method == 'POST':
        accion = request.POST.get('accion')
        if accion in ('agregar_extra', 'eliminar_extra', 'confirmar_cotizacion') and rol_actual not in ('ADMIN', 'VENTAS'):
            messages.warning(request, "Solo el perfil de Ventas o Administración puede modificar la cotización comercial.")
            return redirect('pedido_detalle', pk=pedido.pk)
        if accion == 'descontar_bom' and rol_actual not in ('ADMIN', 'BODEGA', 'COCINA'):
            messages.warning(request, "Solo Bodega, Cocina o Administración pueden ejecutar el descuento BOM.")
            return redirect('pedido_detalle', pk=pedido.pk)

        if accion == 'agregar_extra':
            extra_form = InsumoExtraPedidoForm(request.POST)
            if extra_form.is_valid():
                extra = extra_form.save(commit=False)
                extra.pedido = pedido
                extra.save()
                pedido.recalcular_cotizacion(guardar=True)
                messages.success(request, f"Ingrediente extra '{extra.insumo.nombre}' añadido a la receta del pedido.")
                return redirect('pedido_detalle', pk=pedido.pk)

        elif accion == 'eliminar_extra':
            extra_id = request.POST.get('extra_id')
            InsumoExtraPedido.objects.filter(pk=extra_id, pedido=pedido).delete()
            pedido.recalcular_cotizacion(guardar=True)
            messages.info(request, "Ingrediente extra eliminado y cotización actualizada.")
            return redirect('pedido_detalle', pk=pedido.pk)

        elif accion == 'descontar_bom':
            try:
                ok, msg = pedido.descontar_insumos_bom(usuario=request.user)
                if ok:
                    messages.success(request, msg)
                else:
                    messages.warning(request, msg)
            except ValidationError as exc:
                messages.error(request, exc.message)
            return redirect('pedido_detalle', pk=pedido.pk)

        elif accion == 'confirmar_cotizacion':
            pedido.estado_comercial = 'CONFIRMADO'
            if pedido.abono_pagado == 0:
                pedido.abono_pagado = (pedido.precio_total * Decimal('0.50')).quantize(Decimal('1'))
            pedido.save(update_fields=['estado_comercial', 'abono_pagado', 'actualizado_en'])
            messages.success(
                request,
                f"Cotización {pedido.codigo_pedido} aprobada y confirmada con abono de ${pedido.abono_pagado:,.0f} CLP.",
            )
            return redirect('pedido_detalle', pk=pedido.pk)

    despacho_asociado = getattr(pedido, 'despacho', None)

    context = {
        'pedido': pedido,
        'es_factible_bom': es_factible,
        'faltantes_bom': faltantes,
        'explosion_bom': explosion_bom,
        'extra_form': extra_form,
        'despacho_asociado': despacho_asociado,
        'estados_kanban': PedidoPersonalizado.ESTADO_KANBAN_CHOICES,
    }
    return render(request, 'gestion_pasteleria/pedido_detalle.html', context)


@requiere_roles('ADMIN', 'VENTAS')
def pedido_eliminar_view(request, pk):
    pedido = get_object_or_404(PedidoPersonalizado, pk=pk)
    if request.method == 'POST':
        codigo = pedido.codigo_pedido
        # Si tenía insumos descontados y se elimina/cancela antes de hornear, revertir stock
        if pedido.insumos_descontados and pedido.estado_kanban in ('RECIBIDO', 'EN_PREPARACION'):
            for mov in pedido.movimientos_inventario.filter(tipo_movimiento='SALIDA_BOM_PEDIDO'):
                ins = mov.insumo
                anterior = ins.stock_actual
                ins.stock_actual = anterior + mov.cantidad
                ins.save(update_fields=['stock_actual', 'actualizado_en'])
                MovimientoInventario.objects.create(
                    insumo=ins,
                    tipo_movimiento='REVERSION_CANCELACION',
                    cantidad=mov.cantidad,
                    stock_anterior=anterior,
                    stock_resultante=ins.stock_actual,
                    usuario=request.user,
                    motivo=f"Reingreso automático por eliminación del pedido {codigo}",
                )
        pedido.delete()
        messages.success(request, f"Pedido {codigo} eliminado correctamente del sistema.")
        return redirect('pedidos_list')

    return render(request, 'gestion_pasteleria/pedido_confirm_delete.html', {'pedido': pedido})


# ==============================================================================
# CRUD COMPLETO DE CLIENTES
# ==============================================================================
@requiere_roles('ADMIN', 'VENTAS')
def clientes_view(request):
    clientes = Cliente.objects.annotate(num_pedidos=Count('pedidos')).order_by('nombre_completo')
    editar_id = request.GET.get('editar')
    instancia_editar = get_object_or_404(Cliente, pk=editar_id) if editar_id else None

    if request.method == 'POST':
        accion = request.POST.get('accion', 'guardar')
        if accion == 'eliminar':
            cliente_del = get_object_or_404(Cliente, pk=request.POST.get('cliente_id'))
            if cliente_del.pedidos.exists():
                messages.error(
                    request,
                    f"No se puede eliminar al cliente {cliente_del.nombre_completo} porque tiene pedidos históricos asociados.",
                )
            else:
                cliente_del.delete()
                messages.success(request, "Cliente eliminado correctamente.")
            return redirect('clientes_list')

        cliente_pk = request.POST.get('cliente_pk')
        instancia = get_object_or_404(Cliente, pk=cliente_pk) if cliente_pk else None
        form = ClienteForm(request.POST, instance=instancia)
        if form.is_valid():
            c = form.save()
            messages.success(request, f"Datos del cliente '{c.nombre_completo}' guardados correctamente.")
            return redirect('clientes_list')
    else:
        form = ClienteForm(instance=instancia_editar)

    return render(
        request,
        'gestion_pasteleria/clientes.html',
        {
            'clientes': clientes,
            'form': form,
            'instancia_editar': instancia_editar,
        },
    )


# ==============================================================================
# 4. FUNCIONALIDAD 2: TABLERO KANBAN DIGITAL DEL TALLER DE COCINA
# ==============================================================================
@requiere_roles('ADMIN', 'COCINA', 'BODEGA')
def kanban_cocina_view(request):
    """
    Tablero Kanban interactivo del Taller de Cocina con las 5 columnas requeridas:
    Recibido -> En Preparación -> Horneado/Decorado -> Control de Calidad -> Listo.
    """
    if request.method == 'POST':
        pedido_id = request.POST.get('pedido_id')
        nuevo_estado = request.POST.get('nuevo_estado')
        comentario = request.POST.get('comentario', '').strip()
        temperatura = request.POST.get('temperatura_refrigeracion_c', '').strip()

        pedido = get_object_or_404(PedidoPersonalizado, pk=pedido_id)
        if temperatura:
            try:
                pedido.temperatura_refrigeracion_c = Decimal(temperatura)
                pedido.save(update_fields=['temperatura_refrigeracion_c'])
            except Exception:
                pass

        try:
            pedido.cambiar_estado_kanban(
                nuevo_estado=nuevo_estado,
                usuario=request.user,
                comentario=comentario,
            )
            messages.success(
                request,
                f"Pedido {pedido.codigo_pedido} movido a '{pedido.get_estado_kanban_display()}'. "
                + ("(Descuento automático de insumos BOM ejecutado)" if pedido.insumos_descontados else ""),
            )
        except ValidationError as exc:
            messages.error(request, f"No se pudo mover {pedido.codigo_pedido}: {exc.message}")
        return redirect('kanban_cocina')

    pedidos_taller = (
        PedidoPersonalizado.objects.exclude(estado_comercial__in=['CANCELADO', 'ENTREGADO'])
        .select_related('cliente', 'producto_base', 'pastelero_asignado')
        .prefetch_related('insumos_extra__insumo')
        .order_by('fecha_entrega_comprometida')
    )

    columnas_definicion = [
        {
            'codigo': 'RECIBIDO',
            'titulo': '1. Recibido',
            'subtitulo': 'Cola de Entrada a Cocina',
            'color': 'info',
            'icono': 'bi-inbox-fill',
        },
        {
            'codigo': 'EN_PREPARACION',
            'titulo': '2. En Preparación',
            'subtitulo': 'Pesaje y Descuento BOM',
            'color': 'warning',
            'icono': 'bi-egg-fried',
        },
        {
            'codigo': 'HORNEADO_DECORADO',
            'titulo': '3. Horneado/Decorado',
            'subtitulo': 'Hornos y Arte en Pasta/Crema',
            'color': 'pink',
            'icono': 'bi-fire',
        },
        {
            'codigo': 'CONTROL_CALIDAD',
            'titulo': '4. Control de Calidad',
            'subtitulo': 'Inspección Sanitaria y Frío',
            'color': 'purple',
            'icono': 'bi-shield-check',
        },
        {
            'codigo': 'LISTO',
            'titulo': '5. Listo',
            'subtitulo': 'Empacado para Despacho/Retiro',
            'color': 'success',
            'icono': 'bi-check2-circle',
        },
    ]

    for col in columnas_definicion:
        col['pedidos'] = [p for p in pedidos_taller if p.estado_kanban == col['codigo']]

    historial_reciente = HistorialKanban.objects.select_related('pedido', 'usuario')[:12]

    return render(
        request,
        'gestion_pasteleria/kanban_cocina.html',
        {
            'columnas': columnas_definicion,
            'historial_reciente': historial_reciente,
            'orden_kanban': PedidoPersonalizado.ORDEN_KANBAN,
        },
    )


# ==============================================================================
# 5. FUNCIONALIDAD 3: BODEGA DE INSUMOS Y LISTA DE MATERIALES (BOM)
# ==============================================================================
def _limpiar_decimal_str(valor, default='0'):
    """Normaliza cadenas numéricas aceptando coma o punto decimal."""
    if valor is None:
        return Decimal(default)
    texto = str(valor).strip().replace(',', '.')
    if not texto:
        return Decimal(default)
    return Decimal(texto)


@requiere_roles('ADMIN', 'BODEGA', 'COCINA', 'VENTAS')
def inventario_bom_view(request):
    """
    Centro integral de Bodega de Insumos, Recetas Base, Configuración de Lista de
    Materiales (BOM), Creación de Productos con su Receta y Venta Rápida.
    """
    tab_activa = request.GET.get('tab', 'insumos')
    editar_insumo_id = request.GET.get('editar_insumo')
    insumo_instancia = get_object_or_404(Insumo, pk=editar_insumo_id) if editar_insumo_id else None

    editar_producto_id = request.GET.get('editar_producto')
    producto_instancia = get_object_or_404(ProductoPasteleria, pk=editar_producto_id) if editar_producto_id else None
    if editar_producto_id:
        tab_activa = 'recetas'

    insumo_form = InsumoForm(instance=insumo_instancia)
    producto_form = ProductoPasteleriaForm(instance=producto_instancia)
    bom_form = ItemBOMForm()

    if request.method == 'POST':
        accion = request.POST.get('accion')
        rol_actual = obtener_rol_usuario(request.user)

        if accion != 'vender_producto_rapido' and rol_actual not in ('ADMIN', 'BODEGA', 'COCINA'):
            messages.warning(
                request,
                "Acceso restringido: Solo Administración, Bodega o Cocina pueden modificar insumos, stock o recetas BOM.",
            )
            return redirect('inventario_bom')

        post_data = request.POST.copy()
        for campo_num in (
            'stock_actual',
            'stock_minimo',
            'costo_unitario',
            'cantidad_requerida',
            'merma_tecnica_pct',
            'precio_base',
            'tiempo_elaboracion_horas',
        ):
            if campo_num in post_data and post_data[campo_num]:
                post_data[campo_num] = str(post_data[campo_num]).strip().replace(',', '.')

        # 1. Crear o Editar Insumo
        if accion == 'guardar_insumo':
            pk_edit = post_data.get('insumo_pk')
            inst = get_object_or_404(Insumo, pk=pk_edit) if pk_edit else None
            es_nuevo = inst is None
            insumo_form = InsumoForm(post_data, instance=inst)
            if insumo_form.is_valid():
                ins = insumo_form.save()
                if es_nuevo and ins.stock_actual > 0:
                    MovimientoInventario.objects.create(
                        insumo=ins,
                        tipo_movimiento='ENTRADA_COMPRA',
                        cantidad=ins.stock_actual,
                        stock_anterior=Decimal('0.000'),
                        stock_resultante=ins.stock_actual,
                        usuario=request.user,
                        motivo=f"Stock inicial registrado al crear insumo '{ins.nombre}' ({ins.codigo_sku})",
                    )
                messages.success(
                    request,
                    f"Insumo '{ins.nombre}' ({ins.codigo_sku}) guardado correctamente en bodega "
                    f"(Stock disponible: {ins.stock_actual} {ins.unidad_medida}).",
                )
                return redirect('/bodega/bom/?tab=insumos')
            else:
                errores = '; '.join([f"{k}: {', '.join(v)}" for k, v in insumo_form.errors.items()])
                messages.error(request, f"No se pudo guardar el insumo. Verifica: {errores}")
                tab_activa = 'insumos'

        # 2. Eliminar Insumo
        elif accion == 'eliminar_insumo':
            ins_del = get_object_or_404(Insumo, pk=request.POST.get('insumo_id'))
            if ins_del.usos_bom.exists() or ins_del.movimientos.exists():
                ins_del.activo = False
                ins_del.save(update_fields=['activo'])
                messages.info(
                    request,
                    f"El insumo '{ins_del.nombre}' posee trazabilidad histórica BOM, por lo que fue desactivado de forma segura.",
                )
            else:
                ins_del.delete()
                messages.success(request, "Insumo eliminado de bodega.")
            return redirect('/bodega/bom/?tab=insumos')

        # 3. Ajuste de Stock / Recepción de Compra o Merma
        elif accion == 'movimiento_stock':
            insumo_obj = get_object_or_404(Insumo, pk=request.POST.get('insumo_id'))
            tipo_mov = request.POST.get('tipo_movimiento', 'ENTRADA_COMPRA')
            motivo = request.POST.get('motivo', 'Ajuste manual en bodega').strip()
            try:
                cantidad = _limpiar_decimal_str(request.POST.get('cantidad', '0'))
                if cantidad <= 0:
                    raise ValueError()
                anterior = insumo_obj.stock_actual
                if tipo_mov == 'AJUSTE_MERMA':
                    if anterior < cantidad:
                        messages.error(
                            request,
                            f"No puedes rebajar {cantidad} {insumo_obj.unidad_medida}; el stock actual es {anterior}.",
                        )
                        return redirect('/bodega/bom/?tab=insumos')
                    insumo_obj.stock_actual = anterior - cantidad
                else:
                    tipo_mov = 'ENTRADA_COMPRA'
                    insumo_obj.stock_actual = anterior + cantidad

                insumo_obj.save(update_fields=['stock_actual', 'actualizado_en'])
                MovimientoInventario.objects.create(
                    insumo=insumo_obj,
                    tipo_movimiento=tipo_mov,
                    cantidad=cantidad,
                    stock_anterior=anterior,
                    stock_resultante=insumo_obj.stock_actual,
                    usuario=request.user,
                    motivo=motivo,
                )
                messages.success(
                    request,
                    f"Movimiento registrado en '{insumo_obj.nombre}'. Nuevo stock: {insumo_obj.stock_actual} {insumo_obj.unidad_medida}.",
                )
            except Exception:
                messages.error(request, "Ingresa una cantidad numérica válida mayor que cero.")
            return redirect('/bodega/bom/?tab=insumos')

        # 4. Agregar o Actualizar Componente en la Lista de Materiales (BOM)
        elif accion == 'agregar_item_bom':
            prod_id = post_data.get('producto')
            ins_id = post_data.get('insumo')
            etapa_val = post_data.get('etapa_uso') or 'RELLENO'
            notas_val = (post_data.get('notas_tecnicas') or '').strip()
            try:
                prod_obj = get_object_or_404(ProductoPasteleria, pk=prod_id)
                ins_obj = get_object_or_404(Insumo, pk=ins_id)
                cant_val = _limpiar_decimal_str(post_data.get('cantidad_requerida', '1'), '1')
                merma_val = _limpiar_decimal_str(post_data.get('merma_tecnica_pct', '0'), '0')
                if cant_val <= 0:
                    cant_val = Decimal('1.000')
                if merma_val < 0:
                    merma_val = Decimal('0.00')

                item, creado = ItemBOM.objects.update_or_create(
                    producto=prod_obj,
                    insumo=ins_obj,
                    etapa_uso=etapa_val,
                    defaults={
                        'cantidad_requerida': cant_val,
                        'merma_tecnica_pct': merma_val,
                        'notas_tecnicas': notas_val,
                    },
                )
                verbo = 'añadido a' if creado else 'actualizado en'
                messages.success(
                    request,
                    f"Ingrediente '{item.insumo.nombre}' ({item.cantidad_con_merma} {item.insumo.unidad_medida}) "
                    f"{verbo} la receta de '{item.producto.nombre}'.",
                )
            except Exception as exc:
                messages.error(request, f"No se pudo vincular el insumo a la receta: {exc}")
            return redirect('/bodega/bom/?tab=recetas')

        # 5. Eliminar Componente BOM
        elif accion == 'eliminar_item_bom':
            item_del = get_object_or_404(ItemBOM, pk=request.POST.get('item_bom_id'))
            nombre_prod = item_del.producto.nombre
            nombre_ins = item_del.insumo.nombre
            item_del.delete()
            messages.info(request, f"Ingrediente '{nombre_ins}' retirado de la receta '{nombre_prod}'.")
            return redirect('/bodega/bom/?tab=recetas')

        # 6. Crear o Editar Producto / Receta Base (con sus ingredientes BOM en un solo paso)
        elif accion == 'guardar_producto':
            pk_prod = post_data.get('producto_pk')
            inst_prod = get_object_or_404(ProductoPasteleria, pk=pk_prod) if pk_prod else None
            producto_form = ProductoPasteleriaForm(post_data, instance=inst_prod)
            if producto_form.is_valid():
                prod = producto_form.save()

                # Procesar ingredientes de la receta enviados junto con el producto
                insumo_ids = request.POST.getlist('receta_insumo_id')
                cantidades = request.POST.getlist('receta_cantidad')
                etapas = request.POST.getlist('receta_etapa')
                mermas = request.POST.getlist('receta_merma')

                insumos_agregados = 0
                for idx, ins_id in enumerate(insumo_ids):
                    if not ins_id or not str(ins_id).strip():
                        continue
                    ins_obj = Insumo.objects.filter(pk=ins_id).first()
                    if not ins_obj:
                        continue
                    cant_raw = cantidades[idx] if idx < len(cantidades) else '1'
                    etapa_raw = etapas[idx] if idx < len(etapas) and etapas[idx] else 'RELLENO'
                    merma_raw = mermas[idx] if idx < len(mermas) else '0'
                    try:
                        cant_dec = _limpiar_decimal_str(cant_raw, '1')
                        if cant_dec <= 0:
                            cant_dec = Decimal('1.000')
                    except Exception:
                        cant_dec = Decimal('1.000')
                    try:
                        merma_dec = _limpiar_decimal_str(merma_raw, '0')
                        if merma_dec < 0:
                            merma_dec = Decimal('0.00')
                    except Exception:
                        merma_dec = Decimal('0.00')

                    ItemBOM.objects.update_or_create(
                        producto=prod,
                        insumo=ins_obj,
                        etapa_uso=etapa_raw,
                        defaults={
                            'cantidad_requerida': cant_dec,
                            'merma_tecnica_pct': merma_dec,
                            'notas_tecnicas': f"Ingrediente receta {prod.nombre}",
                        },
                    )
                    insumos_agregados += 1

                total_bom = prod.items_bom.count()
                messages.success(
                    request,
                    f"Producto y Receta '{prod.nombre}' ({prod.codigo}) guardado exitosamente con "
                    f"{total_bom} ingrediente(s) en su receta BOM. ¡Ya está disponible para vender!",
                )
                return redirect('/bodega/bom/?tab=recetas')
            else:
                errores = '; '.join([f"{k}: {', '.join(v)}" for k, v in producto_form.errors.items()])
                messages.error(request, f"No se pudo guardar el producto/receta: {errores}")
                tab_activa = 'recetas'

        # 7. Eliminar o Desactivar Producto / Receta Base
        elif accion == 'eliminar_producto':
            prod_del = get_object_or_404(ProductoPasteleria, pk=request.POST.get('producto_id'))
            if prod_del.pedidos.exists():
                prod_del.activo = False
                prod_del.save(update_fields=['activo'])
                messages.info(
                    request,
                    f"El producto '{prod_del.nombre}' posee ventas registradas, por lo que fue desactivado del catálogo.",
                )
            else:
                prod_del.delete()
                messages.success(request, "Producto y receta eliminados del catálogo.")
            return redirect('/bodega/bom/?tab=recetas')

        # 8. Venta Rápida de Producto (Descuenta Insumos de la Receta automáticamente)
        elif accion == 'vender_producto_rapido':
            prod_obj = get_object_or_404(ProductoPasteleria, pk=request.POST.get('producto_id'))
            cliente_id = request.POST.get('cliente_id')
            nuevo_cliente_txt = (request.POST.get('nuevo_cliente_nombre') or '').strip()
            next_url = request.POST.get('next_url') or '/bodega/bom/?tab=recetas'
            try:
                cantidad_venta = max(1, int(request.POST.get('cantidad_venta', prod_obj.porciones_base) or 1))
            except Exception:
                cantidad_venta = prod_obj.porciones_base or 1

            if nuevo_cliente_txt:
                cliente_obj = Cliente.objects.filter(nombre_completo__iexact=nuevo_cliente_txt).first()
                if not cliente_obj:
                    correlativo = Cliente.objects.count() + 200
                    rut_auto = f"88.{correlativo:03d}.{correlativo:03d}-K"
                    while Cliente.objects.filter(rut=rut_auto).exists():
                        correlativo += 1
                        rut_auto = f"88.{correlativo:03d}.{correlativo:03d}-K"
                    cliente_obj = Cliente.objects.create(
                        rut=rut_auto,
                        nombre_completo=nuevo_cliente_txt,
                        tipo_cliente='PARTICULAR',
                        email='venta@dulcearte.cl',
                        telefono='+56 9 0000 0000',
                        direccion_habitual='Retiro en Tienda Dulce Arte',
                        comuna='Providencia',
                    )
            elif cliente_id:
                cliente_obj = get_object_or_404(Cliente, pk=cliente_id)
            else:
                cliente_obj, _ = Cliente.objects.get_or_create(
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

            pedido = PedidoPersonalizado.objects.create(
                cliente=cliente_obj,
                producto_base=prod_obj,
                vendedor=request.user,
                pastelero_asignado=request.user,
                porciones_solicitadas=cantidad_venta,
                sabor_bizcocho=f"Receta {prod_obj.nombre}",
                relleno_principal='Ingredientes según Receta BOM',
                cobertura_diseno='Presentación Estándar',
                nivel_complejidad='ESTANDAR',
                descripcion_diseno=f"Venta directa de {cantidad_venta} unidad(es)/porción(es) de {prod_obj.nombre}.",
                fecha_entrega_comprometida=timezone.now() + timezone.timedelta(hours=1),
                modalidad_entrega='RETIRO_TIENDA',
                direccion_entrega=cliente_obj.direccion_habitual or 'Retiro en Tienda Dulce Arte',
                comuna_entrega=cliente_obj.comuna or 'Providencia',
                estado_comercial='CONFIRMADO',
                estado_kanban='RECIBIDO',
                prioridad='NORMAL',
            )
            pedido.recalcular_cotizacion(guardar=True)
            pedido.abono_pagado = pedido.precio_total
            pedido.save(update_fields=['abono_pagado'])

            HistorialKanban.objects.create(
                pedido=pedido,
                estado_anterior='RECIBIDO',
                estado_nuevo='RECIBIDO',
                usuario=request.user,
                comentario=f"Venta registrada: {cantidad_venta}x '{prod_obj.nombre}'.",
            )

            if prod_obj.items_bom.exists():
                try:
                    pedido.cambiar_estado_kanban(
                        'LISTO',
                        usuario=request.user,
                        comentario=f"Venta directa y preparación de '{prod_obj.nombre}' con descuento automático de insumos BOM.",
                    )
                    pedido.estado_comercial = 'ENTREGADO'
                    pedido.save(update_fields=['estado_comercial'])
                    messages.success(
                        request,
                        f"¡Venta realizada exitosamente! Pedido {pedido.codigo_pedido}: {cantidad_venta}x '{prod_obj.nombre}' "
                        f"por ${pedido.precio_total:,.0f} CLP. Se descontaron automáticamente los insumos de la receta en Bodega.",
                    )
                except ValidationError as exc:
                    messages.warning(
                        request,
                        f"Pedido {pedido.codigo_pedido} registrado (${pedido.precio_total:,.0f} CLP), "
                        f"pero no se pudo descontar el stock automáticamente: {exc.message}",
                    )
            else:
                pedido.estado_kanban = 'LISTO'
                pedido.estado_comercial = 'ENTREGADO'
                pedido.save(update_fields=['estado_kanban', 'estado_comercial'])
                messages.success(
                    request,
                    f"¡Venta realizada! Pedido {pedido.codigo_pedido}: {cantidad_venta}x '{prod_obj.nombre}' "
                    f"por ${pedido.precio_total:,.0f} CLP.",
                )
            return redirect(next_url)

    insumos = Insumo.objects.select_related('categoria').filter(activo=True).order_by('nombre')
    productos = ProductoPasteleria.objects.prefetch_related('items_bom__insumo').filter(activo=True).order_by('-id')
    movimientos = MovimientoInventario.objects.select_related(
        'insumo', 'pedido_asociado', 'usuario'
    )[:30]
    categorias = CategoriaInsumo.objects.all()
    clientes = Cliente.objects.all().order_by('nombre_completo')

    valor_total_bodega = sum((i.valor_inventario_total for i in insumos), Decimal('0'))

    return render(
        request,
        'gestion_pasteleria/inventario_bom.html',
        {
            'tab_activa': tab_activa,
            'insumos': insumos,
            'productos': productos,
            'movimientos': movimientos,
            'categorias': categorias,
            'clientes': clientes,
            'valor_total_bodega': valor_total_bodega,
            'insumo_form': insumo_form,
            'insumo_instancia': insumo_instancia,
            'producto_form': producto_form,
            'producto_instancia': producto_instancia,
            'bom_form': bom_form,
            'etapas_bom': ItemBOM.ETAPA_USO_CHOICES,
        },
    )


# ==============================================================================
# 6. FUNCIONALIDAD 4: GESTIÓN DE RUTAS DE DESPACHO Y FIRMA DIGITAL / FOTO
# ==============================================================================
@requiere_roles('ADMIN', 'REPARTIDOR')
def rutas_despacho_view(request):
    """
    Módulo de planificación de Rutas de Despacho, asignación de paradas
    y confirmación en destino con Firma Digital (Canvas HTML5) o Fotografía.
    """
    ruta_form = RutaDespachoForm()
    despacho_form = DespachoPedidoForm()

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'crear_ruta':
            ruta_form = RutaDespachoForm(request.POST)
            if ruta_form.is_valid():
                nueva_ruta = ruta_form.save()
                messages.success(request, f"Ruta de despacho '{nueva_ruta.codigo_ruta}' creada exitosamente.")
                return redirect('rutas_despacho')

        elif accion == 'asignar_pedido_ruta':
            despacho_form = DespachoPedidoForm(request.POST)
            if despacho_form.is_valid():
                despacho = despacho_form.save()
                messages.success(
                    request,
                    f"Pedido {despacho.pedido.codigo_pedido} asignado a la parada #{despacho.orden_parada} de {despacho.ruta.codigo_ruta}.",
                )
                return redirect('rutas_despacho')
            else:
                messages.error(request, "No se pudo asignar el pedido (verifica que no esté ya en otra ruta).")

        elif accion == 'iniciar_ruta':
            ruta_obj = get_object_or_404(RutaDespacho, pk=request.POST.get('ruta_id'))
            ruta_obj.estado_ruta = 'EN_RUTA'
            ruta_obj.save(update_fields=['estado_ruta'])
            ruta_obj.entregas.filter(estado_entrega='PENDIENTE').update(estado_entrega='EN_CAMINO')
            messages.info(request, f"Ruta {ruta_obj.codigo_ruta} iniciada. Pedidos marcados 'En Camino'.")
            return redirect('rutas_despacho')

    rutas = (
        RutaDespacho.objects.select_related('repartidor')
        .prefetch_related('entregas__pedido__cliente', 'entregas__pedido__producto_base')
        .all()
    )

    # Pedidos disponibles para ser asignados a ruta (que no tengan despacho aún)
    pedidos_sin_ruta = PedidoPersonalizado.objects.filter(
        despacho__isnull=True
    ).exclude(estado_comercial='CANCELADO').select_related('cliente')
    despacho_form.fields['pedido'].queryset = pedidos_sin_ruta

    return render(
        request,
        'gestion_pasteleria/rutas_despacho.html',
        {
            'rutas': rutas,
            'ruta_form': ruta_form,
            'despacho_form': despacho_form,
            'pedidos_sin_ruta_count': pedidos_sin_ruta.count(),
        },
    )


@requiere_roles('ADMIN', 'REPARTIDOR')
def confirmar_entrega_view(request, pk):
    """
    Pantalla interactiva de Confirmación de Entrega con Lienzo de Firma Digital
    (Canvas HTML5 -> Base64) y/o carga de Comprobante Fotográfico.
    """
    despacho = get_object_or_404(
        DespachoPedido.objects.select_related('ruta__repartidor', 'pedido__cliente', 'pedido__producto_base'),
        pk=pk,
    )

    if request.method == 'POST':
        nombre_receptor = request.POST.get('nombre_receptor', '').strip()
        rut_receptor = request.POST.get('rut_receptor', '').strip()
        parentesco = request.POST.get('parentesco_o_cargo', 'Cliente Titular').strip()
        firma_base64 = request.POST.get('firma_digital_base64', '').strip()
        foto_archivo = request.FILES.get('comprobante_foto')
        temperatura = request.POST.get('temperatura_entrega_c', '4.2').strip()
        coordenadas = request.POST.get('coordenadas_gps', '-33.4262, -70.6109').strip()
        observaciones = request.POST.get('observaciones_entrega', '').strip()

        try:
            despacho.confirmar_entrega_digital(
                nombre_receptor=nombre_receptor,
                rut_receptor=rut_receptor,
                firma_base64=firma_base64,
                comprobante_archivo=foto_archivo,
                parentesco=parentesco,
                temperatura_c=temperatura or Decimal('4.2'),
                observaciones=observaciones,
                coordenadas=coordenadas,
                usuario=request.user,
            )
            messages.success(
                request,
                f"¡Entrega del pedido {despacho.pedido.codigo_pedido} confirmada exitosamente con respaldo digital!",
            )
            return redirect('confirmar_entrega', pk=despacho.pk)
        except ValidationError as exc:
            messages.error(request, exc.message)

    return render(
        request,
        'gestion_pasteleria/confirmar_entrega.html',
        {'despacho': despacho},
    )


# ==============================================================================
# 7. CENTRO DE ADMINISTRACIÓN INTEGRAL (TODO EN UNA MISMA PÁGINA WEB)
# ==============================================================================
@requiere_roles('ADMIN')
def administracion_unificada_view(request):
    """
    Reúne toda la administración de las 12 tablas del dominio en una sola página
    con pestañas interactivas, filtros y formularios CRUD completos, sin necesidad
    de salir de la interfaz principal ni modificar el Django Admin nativo.
    """
    tab_activa = request.GET.get('tab', 'pedidos')

    if request.method == 'POST':
        accion = request.POST.get('accion', '')

        # 1. Categorías de Insumo
        if accion == 'guardar_categoria':
            cat_form = CategoriaInsumoForm(request.POST)
            if cat_form.is_valid():
                cat_form.save()
                messages.success(request, "Categoría de insumo registrada correctamente.")
            return redirect('/administracion/?tab=bodega')

        elif accion == 'eliminar_categoria':
            cat = get_object_or_404(CategoriaInsumo, pk=request.POST.get('categoria_id'))
            if cat.insumos.exists():
                messages.error(request, "No se puede eliminar una categoría que tiene insumos asociados.")
            else:
                cat.delete()
                messages.success(request, "Categoría eliminada.")
            return redirect('/administracion/?tab=bodega')

        # 2. Usuarios y Perfiles Operativos
        elif accion == 'crear_usuario_rol':
            uname = request.POST.get('username', '').strip()
            pwd = request.POST.get('password', 'dulcearte2026').strip()
            fname = request.POST.get('first_name', '').strip()
            lname = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            rol = request.POST.get('rol', 'VENTAS')
            rut = request.POST.get('rut', '').strip()
            turno = request.POST.get('turno', 'COMPLETO')
            if uname:
                user_obj, created = User.objects.get_or_create(
                    username=uname,
                    defaults={'first_name': fname, 'last_name': lname, 'email': email, 'is_staff': True},
                )
                if created:
                    user_obj.set_password(pwd)
                    user_obj.save()
                PerfilUsuario.objects.update_or_create(
                    usuario=user_obj,
                    defaults={'rol': rol, 'rut': rut, 'turno': turno, 'activo': True},
                )
                messages.success(request, f"Usuario '{uname}' y perfil ({rol}) guardados.")
            return redirect('/administracion/?tab=usuarios')

        elif accion == 'eliminar_ruta':
            ruta_del = get_object_or_404(RutaDespacho, pk=request.POST.get('ruta_id'))
            ruta_del.delete()
            messages.info(request, "Ruta de despacho eliminada.")
            return redirect('/administracion/?tab=logistica')

    context = {
        'tab_activa': tab_activa,
        'pedidos': PedidoPersonalizado.objects.select_related('cliente', 'producto_base').all(),
        'clientes': Cliente.objects.all(),
        'categorias': CategoriaInsumo.objects.all(),
        'insumos': Insumo.objects.select_related('categoria').all(),
        'productos': ProductoPasteleria.objects.prefetch_related('items_bom__insumo').all(),
        'items_bom': ItemBOM.objects.select_related('producto', 'insumo').all(),
        'movimientos': MovimientoInventario.objects.select_related('insumo', 'pedido_asociado', 'usuario')[:30],
        'historial_kanban': HistorialKanban.objects.select_related('pedido', 'usuario')[:30],
        'rutas': RutaDespacho.objects.select_related('repartidor').prefetch_related('entregas__pedido').all(),
        'despachos': DespachoPedido.objects.select_related('ruta', 'pedido__cliente').all(),
        'perfiles': PerfilUsuario.objects.select_related('usuario').all(),
        'cliente_form': ClienteForm(),
        'categoria_form': CategoriaInsumoForm(),
        'insumo_form': InsumoForm(),
        'producto_form': ProductoPasteleriaForm(),
        'bom_form': ItemBOMForm(),
        'ruta_form': RutaDespachoForm(),
        'roles_choices': PerfilUsuario.ROL_CHOICES,
        'turnos_choices': PerfilUsuario.TURNO_CHOICES,
    }
    return render(request, 'gestion_pasteleria/centro_admin.html', context)


# ==============================================================================
# MANEJADOR DE ERROR PERSONALIZADO 404 (PÁGINA NO ENCONTRADA)
# ==============================================================================
def error_404_view(request, exception=None):
    """
    Vista personalizada para el manejo de errores HTTP 404 (Página No Encontrada).
    Retorna respuesta JSON si la petición proviene de un cliente API REST o 'Accept: application/json',
    o la plantilla HTML temática '404.html' para la navegación web.
    """
    accept_header = request.headers.get('Accept', '')
    if request.path.startswith('/api/') or 'application/json' in accept_header:
        from django.http import JsonResponse
        return JsonResponse({
            'error': '404 Not Found',
            'mensaje': f'El recurso o endpoint "{request.path}" no existe en la API REST de Dulce Arte.',
            'status_code': 404,
            'timestamp': timezone.now().isoformat(),
        }, status=404)

    return render(request, '404.html', {
        'path': request.path,
        'request_path': request.path,
        'exception': str(exception) if exception else None,
    }, status=404)


