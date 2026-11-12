"""
Suite de Pruebas Automatizadas (Unitarias y de Integración API DRF)
para verificar las 4 funcionalidades clave de Dulce Arte.
"""

from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    PerfilUsuario,
    Cliente,
    CategoriaInsumo,
    Insumo,
    ProductoPasteleria,
    ItemBOM,
    PedidoPersonalizado,
    MovimientoInventario,
    RutaDespacho,
    DespachoPedido,
)


class DulceArteBusinessLogicTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='chef_test', password='password123')
        self.cliente = Cliente.objects.create(
            rut='12.345.678-9',
            nombre_completo='Cliente Prueba',
            email='cliente@test.cl',
            telefono='+56911112222',
            direccion_habitual='Av. Providencia 1234',
            comuna='Providencia',
        )
        self.cat = CategoriaInsumo.objects.create(nombre='Chocolatería')
        self.insumo_choco = Insumo.objects.create(
            codigo_sku='SKU-CHOCO-1',
            nombre='Chocolate Belga 70%',
            categoria=self.cat,
            unidad_medida='KG',
            stock_actual=Decimal('10.000'),
            stock_minimo=Decimal('2.000'),
            costo_unitario=Decimal('15000'),
        )
        self.producto = ProductoPasteleria.objects.create(
            codigo='PROD-001',
            nombre='Torta Belga',
            porciones_base=15,
            precio_base=Decimal('45000'),
            descripcion='Receta de prueba',
        )
        # Requiere 1.000 kg neto + 0% merma para 15 porciones
        ItemBOM.objects.create(
            producto=self.producto,
            insumo=self.insumo_choco,
            cantidad_requerida=Decimal('1.000'),
            merma_tecnica_pct=Decimal('0.00'),
            etapa_uso='RELLENO',
        )

    def test_cotizacion_y_descuento_automatico_bom_en_kanban(self):
        """
        Verifica Funcionalidad 1, 2 y 3:
        Un pedido de 30 porciones (factor 2.0x sobre base 15) debe descontar
        exactamente 2.000 KG de Chocolate Belga al pasar a EN_PREPARACION en el Kanban.
        """
        pedido = PedidoPersonalizado.objects.create(
            cliente=self.cliente,
            producto_base=self.producto,
            porciones_solicitadas=30,
            nivel_complejidad='ESTANDAR',
            descripcion_diseno='Diseño clásico',
            fecha_entrega_comprometida=timezone.now() + timedelta(days=2),
        )
        self.assertEqual(pedido.factor_escala_porciones, Decimal('2.000'))
        self.assertFalse(pedido.insumos_descontados)

        # Mover en Kanban a EN_PREPARACION dispara el descuento automático BOM
        pedido.cambiar_estado_kanban('EN_PREPARACION', usuario=self.user)
        self.insumo_choco.refresh_from_db()

        self.assertTrue(pedido.insumos_descontados)
        self.assertEqual(self.insumo_choco.stock_actual, Decimal('8.000'))
        self.assertEqual(
            MovimientoInventario.objects.filter(pedido_asociado=pedido, tipo_movimiento='SALIDA_BOM_PEDIDO').count(),
            1,
        )

    def test_bloqueo_kanban_por_stock_insuficiente_bom(self):
        """Verifica que el sistema impida iniciar preparación si falta stock en bodega."""
        self.insumo_choco.stock_actual = Decimal('0.500')
        self.insumo_choco.save()

        pedido = PedidoPersonalizado.objects.create(
            cliente=self.cliente,
            producto_base=self.producto,
            porciones_solicitadas=15,
            descripcion_diseno='Diseño prueba',
            fecha_entrega_comprometida=timezone.now() + timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            pedido.cambiar_estado_kanban('EN_PREPARACION', usuario=self.user)

    def test_confirmacion_despacho_con_firma_digital(self):
        """Verifica Funcionalidad 4: Confirmación de entrega en ruta con Firma Digital Base64."""
        pedido = PedidoPersonalizado.objects.create(
            cliente=self.cliente,
            producto_base=self.producto,
            porciones_solicitadas=15,
            descripcion_diseno='Diseño entrega',
            fecha_entrega_comprometida=timezone.now() + timedelta(hours=5),
        )
        ruta = RutaDespacho.objects.create(
            codigo_ruta='RUTA-TEST-01',
            nombre_ruta='Ruta Test',
            repartidor=self.user,
        )
        despacho = DespachoPedido.objects.create(
            ruta=ruta,
            pedido=pedido,
            orden_parada=1,
            direccion_destino='Av. Providencia 1234',
            comuna_destino='Providencia',
            telefono_contacto='+56911112222',
        )

        # Sin firma ni foto debe lanzar ValidationError
        with self.assertRaises(ValidationError):
            despacho.confirmar_entrega_digital(
                nombre_receptor='Cliente Prueba',
                rut_receptor='12.345.678-9',
                firma_base64='',
            )

        # Con firma digital Base64 válida confirma entrega y completa la ruta
        despacho.confirmar_entrega_digital(
            nombre_receptor='Cliente Prueba',
            rut_receptor='12.345.678-9',
            firma_base64='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
            usuario=self.user,
        )
        pedido.refresh_from_db()
        ruta.refresh_from_db()
        self.assertEqual(despacho.estado_entrega, 'ENTREGADO')
        self.assertEqual(pedido.estado_comercial, 'ENTREGADO')
        self.assertEqual(ruta.estado_ruta, 'COMPLETADA')

    def test_api_drf_simulador_cotizacion(self):
        """Verifica el endpoint DRF POST /api/v1/pedidos/simular_cotizacion/."""
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.post(
            '/api/v1/pedidos/simular_cotizacion/',
            {
                'producto_base_id': self.producto.id,
                'porciones_solicitadas': 30,
                'nivel_complejidad': 'PERSONALIZADO_MEDIO',
                'modalidad_entrega': 'DESPACHO_DOMICILIO',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['stock_factible'])
        self.assertEqual(response.data['porciones_solicitadas'], 30)

    def test_vistas_web_y_admin_renderizan_correctamente(self):
        """Verifica que todas las vistas HTML, el Admin personalizado y la API respondan HTTP 200."""
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)

        pedido = PedidoPersonalizado.objects.create(
            cliente=self.cliente,
            producto_base=self.producto,
            porciones_solicitadas=15,
            descripcion_diseno='Diseño integral',
            fecha_entrega_comprometida=timezone.now() + timedelta(days=1),
        )
        ruta = RutaDespacho.objects.create(
            codigo_ruta='RUTA-VIEW-01',
            nombre_ruta='Ruta Vistas',
            repartidor=self.user,
        )
        despacho = DespachoPedido.objects.create(
            ruta=ruta,
            pedido=pedido,
            orden_parada=1,
            direccion_destino='Av. Providencia 1234',
            comuna_destino='Providencia',
            telefono_contacto='+56911112222',
        )

        rutas_a_probar = [
            '/',
            '/pedidos/',
            '/pedidos/nuevo/',
            f'/pedidos/{pedido.pk}/',
            f'/pedidos/{pedido.pk}/editar/',
            '/clientes/',
            '/cocina/kanban/',
            '/bodega/bom/',
            '/logistica/rutas/',
            f'/logistica/entregas/{despacho.pk}/confirmar/',
            '/administracion/',
            '/admin/',
            '/api/v1/pedidos/',
            '/api/v1/insumos/alertas_criticas/',
            f'/api/v1/pedidos/{pedido.pk}/explosion_bom/',
        ]
        for url in rutas_a_probar:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, f"Fallo al cargar la ruta {url}")

    def test_restriccion_panel_administracion_por_rol(self):
        """
        Verifica Criterio 4 de la Rúbrica (Seguridad y Permisos por Rol):
        - El perfil BODEGA no debe visualizar la sección 'Administración' ni acceder a /administracion/.
        - El perfil COCINA (Chef) no debe acceder a Despachos ni Firmas de Entrega (/logistica/rutas/).
        - El perfil REPARTIDOR sí puede acceder a Despachos y Firmas de Entrega.
        - ADMIN tiene acceso global.
        """
        self.client.force_login(self.user)
        PerfilUsuario.objects.update_or_create(usuario=self.user, defaults={'rol': 'BODEGA'})

        resp_dashboard_bodega = self.client.get('/')
        self.assertEqual(resp_dashboard_bodega.status_code, 200)
        self.assertNotContains(resp_dashboard_bodega, '<span>Panel admin</span>')
        self.assertNotContains(resp_dashboard_bodega, '<span>Django Admin</span>')
        self.assertNotContains(resp_dashboard_bodega, 'id="selectorRol"')

        resp_admin_bodega = self.client.get('/administracion/')
        self.assertEqual(resp_admin_bodega.status_code, 302)

        # Chef (COCINA) no puede hacer entregas ni firmar despachos
        PerfilUsuario.objects.update_or_create(usuario=self.user, defaults={'rol': 'COCINA'})
        self.assertEqual(self.client.get('/logistica/rutas/').status_code, 302)

        # Repartidor (REPARTIDOR) sí puede gestionar despachos, pero no entrar a Cocina Kanban
        PerfilUsuario.objects.update_or_create(usuario=self.user, defaults={'rol': 'REPARTIDOR'})
        self.assertEqual(self.client.get('/logistica/rutas/').status_code, 200)
        self.assertEqual(self.client.get('/cocina/kanban/').status_code, 302)

        # Administrador General (ADMIN) tiene acceso completo
        PerfilUsuario.objects.update_or_create(usuario=self.user, defaults={'rol': 'ADMIN'})
        resp_dashboard_admin = self.client.get('/')
        self.assertContains(resp_dashboard_admin, '<span>Panel admin</span>')
        self.assertContains(resp_dashboard_admin, '<span>Django Admin</span>')
        self.assertEqual(self.client.get('/administracion/').status_code, 200)

    def test_flujo_completo_crear_insumos_receta_producto_y_vender(self):
        """
        Verifica el flujo End-to-End solicitado por el usuario:
        1. Agregar nuevos insumos (Queso, Pan, Jamón) sin exigir SKU ni categoría manual.
        2. Crear nueva receta y producto ('Pan con queso y jamón') vinculando Queso, Pan y Jamón.
        3. Vender ese producto (1 o más unidades) y descontar stock automáticamente en bodega.
        """
        self.client.force_login(self.user)
        PerfilUsuario.objects.update_or_create(usuario=self.user, defaults={'rol': 'ADMIN'})

        # 1. Crear insumos: Queso, Pan, Jamón
        for nombre_ins, costo in [('Queso', '500'), ('Pan', '400'), ('Jamón', '600')]:
            resp_ins = self.client.post(
                '/bodega/bom/',
                {
                    'accion': 'guardar_insumo',
                    'nombre': nombre_ins,
                    'unidad_medida': 'UNIDAD',
                    'stock_actual': '20,000',
                    'stock_minimo': '2',
                    'costo_unitario': costo,
                },
            )
            self.assertEqual(resp_ins.status_code, 302)

        ins_queso = Insumo.objects.get(nombre='Queso')
        ins_pan = Insumo.objects.get(nombre='Pan')
        ins_jamon = Insumo.objects.get(nombre='Jamón')
        self.assertEqual(ins_queso.stock_actual, Decimal('20.000'))
        self.assertTrue(ins_queso.codigo_sku.startswith('INS-QUE-'))

        # 2. Crear receta y producto 'Pan con queso y jamón' con sus 3 insumos en un solo paso
        resp_prod = self.client.post(
            '/bodega/bom/',
            {
                'accion': 'guardar_producto',
                'nombre': 'Pan con queso y jamón',
                'precio_base': '2500',
                'porciones_base': '1',
                'receta_insumo_id': [str(ins_pan.pk), str(ins_queso.pk), str(ins_jamon.pk)],
                'receta_cantidad': ['1', '2', '1'],
                'receta_etapa': ['BATIDO_MASA', 'RELLENO', 'RELLENO'],
                'receta_merma': ['0', '0', '0'],
            },
        )
        self.assertEqual(resp_prod.status_code, 302)

        prod_sandwich = ProductoPasteleria.objects.get(nombre='Pan con queso y jamón')
        self.assertEqual(prod_sandwich.items_bom.count(), 3)

        # 3. Vender 2 unidades de 'Pan con queso y jamón' mediante Venta Rápida
        resp_venta = self.client.post(
            '/bodega/bom/',
            {
                'accion': 'vender_producto_rapido',
                'producto_id': prod_sandwich.pk,
                'cantidad_venta': '2',
            },
        )
        self.assertEqual(resp_venta.status_code, 302)

        ins_pan.refresh_from_db()
        ins_queso.refresh_from_db()
        ins_jamon.refresh_from_db()

        # Se vendieron 2 unidades -> descuenta 2 de Pan, 4 de Queso, 2 de Jamón
        self.assertEqual(ins_pan.stock_actual, Decimal('18.000'))
        self.assertEqual(ins_queso.stock_actual, Decimal('16.000'))
        self.assertEqual(ins_jamon.stock_actual, Decimal('18.000'))



