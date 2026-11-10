"""
Comando de gestión Django: `python manage.py seed_dulce_arte`
Puebla la base de datos relacional (PostgreSQL / SQLite) con datos realistas
para demostrar las 4 funcionalidades clave del Proyecto 3: Pastelería Artesanal "Dulce Arte".
"""

from decimal import Decimal
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone

from gestion_pasteleria.models import (
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


# Pequeña firma digital PNG en Base64 para datos de demostración iniciales
DEMO_SIGNATURE_BASE64 = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' width='320' height='90'>"
    "<rect width='100%' height='100%' fill='white'/>"
    "<path d='M 25 60 Q 65 15 110 55 T 195 45 T 285 50' stroke='%230f172a' stroke-width='3' fill='none'/>"
    "<text x='45' y='82' font-family='sans-serif' font-size='10' fill='%23475569'>Recepción Conforme Digital · Dulce Arte</text>"
    "</svg>"
)


class Command(BaseCommand):
    help = "Carga datos iniciales completos para Pastelería Artesanal Dulce Arte (Usuarios, Insumos, BOM, Pedidos Kanban y Rutas)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Iniciando carga de datos demostrativos para Dulce Arte..."))

        # 1. Crear Usuarios y Perfiles por Rol
        usuarios_config = [
            ('admin', 'Marcelo', 'Alvarado (Admin)', 'admin@dulcearte.cl', 'ADMIN', '12.345.678-9', 'Dirección General', True),
            ('ventas_camila', 'Camila', 'Valdés', 'camila.ventas@dulcearte.cl', 'VENTAS', '18.234.567-K', 'Asesoría Eventos y Novios', False),
            ('chef_matias', 'Matías', 'Riquelme', 'matias.cocina@dulcearte.cl', 'COCINA', '16.890.123-4', 'Maestro Pastelero & Escultura Fondant', False),
            ('bodega_pedro', 'Pedro', 'Soto', 'pedro.bodega@dulcearte.cl', 'BODEGA', '15.432.198-7', 'Control de Calidad e Inventario BOM', False),
            ('repartidor_lucas', 'Lucas', 'Morales', 'lucas.ruta@dulcearte.cl', 'REPARTIDOR', '19.876.543-2', 'Transporte Refrigerado Isotérmico', False),
        ]

        usuarios_creados = {}
        for username, fname, lname, email, rol, rut, esp, is_super in usuarios_config:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': fname,
                    'last_name': lname,
                    'email': email,
                    'is_staff': True,
                    'is_superuser': is_super,
                },
            )
            user.first_name = fname
            user.last_name = lname
            user.is_staff = True
            user.is_superuser = is_super
            user.set_password('dulcearte2026')
            user.save()

            PerfilUsuario.objects.update_or_create(
                usuario=user,
                defaults={
                    'rol': rol,
                    'rut': rut,
                    'telefono': '+56 9 8765 4321',
                    'turno': 'COMPLETO',
                    'especialidad_pastelera': esp,
                    'activo': True,
                },
            )
            usuarios_creados[rol] = user

        # 2. Crear Clientes
        clientes_data = [
            ('17.456.890-1', 'Valentina Errázuriz Montes', 'EVENTO_NOVIOS', 'valentina.errazuriz@gmail.com', '+56 9 9123 4567', 'Av. Nueva Costanera 4120, Depto 802', 'Vitacura', 'Sin trazas de maní'),
            ('15.982.341-K', 'Sebastián Larraín Donoso', 'PARTICULAR', 'slarrain@outlook.cl', '+56 9 8234 5678', 'Av. Ricardo Lyon 1450', 'Providencia', ''),
            ('76.543.210-8', 'Hotel Boutique Cordillera SpA', 'CORPORATIVO', 'eventos@hotelcordillera.cl', '+56 2 2456 7890', 'Av. Apoquindo 5600', 'Las Condes', 'Opciones Sin Lactosa identificadas'),
            ('19.112.334-5', 'Francisca Muñoz Tapia', 'PARTICULAR', 'fran.munoz@gmail.com', '+56 9 7654 3210', ' José Domingo Cañas 2300', 'Ñuñoa', 'Intolerancia al Gluten (Celíaca)'),
            ('14.678.901-2', 'Rodrigo Fuenzalida Silva', 'EVENTO_NOVIOS', 'rfuenzalida@empresa.cl', '+56 9 6543 2109', 'Camino El Alba 9500', 'Las Condes', ''),
        ]
        clientes_objs = []
        for rut, nombre, tipo, email, fono, direc, comuna, alergia in clientes_data:
            c, _ = Cliente.objects.update_or_create(
                rut=rut,
                defaults={
                    'nombre_completo': nombre,
                    'tipo_cliente': tipo,
                    'email': email,
                    'telefono': fono,
                    'direccion_habitual': direc,
                    'comuna': comuna,
                    'preferencias_alimentarias': alergia,
                },
            )
            clientes_objs.append(c)

        # 3. Crear Categorías de Insumos e Insumos en Bodega
        cat_secos, _ = CategoriaInsumo.objects.get_or_create(
            nombre='Harinas, Secos y Endulzantes',
            defaults={'descripcion': 'Harinas pasteleras, azúcares y polvos de horneo', 'es_perecible': False, 'requiere_cadena_frio': False},
        )
        cat_lacteos, _ = CategoriaInsumo.objects.get_or_create(
            nombre='Lácteos, Cremas y Huevos de Campo',
            defaults={'descripcion': 'Insumos refrigerados de alta rotación', 'es_perecible': True, 'requiere_cadena_frio': True},
        )
        cat_choco, _ = CategoriaInsumo.objects.get_or_create(
            nombre='Chocolatería Belga y Rellenos',
            defaults={'descripcion': 'Coberturas Callebaut, manjar artesanal y pastas de frutos secos', 'es_perecible': True, 'requiere_cadena_frio': False},
        )
        cat_frutas, _ = CategoriaInsumo.objects.get_or_create(
            nombre='Frutas Frescas y Decoración Artística',
            defaults={'descripcion': 'Berries frescos, pulpas naturales, fondant y flores comestibles', 'es_perecible': True, 'requiere_cadena_frio': True},
        )
        cat_pack, _ = CategoriaInsumo.objects.get_or_create(
            nombre='Packaging Isotérmico y Bases',
            defaults={'descripcion': 'Bases rígidas doradas y cajas térmicas para despacho', 'es_perecible': False, 'requiere_cadena_frio': False},
        )

        hoy = timezone.localdate()
        insumos_config = [
            ('INS-HAR-001', 'Harina Pastelera 0000 Sin Polvos', cat_secos, 'KG', Decimal('45.000'), Decimal('15.000'), Decimal('1450'), hoy + timedelta(days=120), 'Estante Secos A1'),
            ('INS-AZU-002', 'Azúcar Granulada Refinada', cat_secos, 'KG', Decimal('38.000'), Decimal('10.000'), Decimal('1180'), hoy + timedelta(days=180), 'Estante Secos A2'),
            ('INS-ALM-003', 'Harina de Almendras Extra Fina (Sin Gluten)', cat_secos, 'KG', Decimal('3.200'), Decimal('5.000'), Decimal('14500'), hoy + timedelta(days=60), 'Estante Especial B1'),  # En alerta de stock
            ('INS-HUE-004', 'Huevos de Campo Gallina Libre (Bandeja x30)', cat_lacteos, 'UNIDAD', Decimal('240.000'), Decimal('60.000'), Decimal('230'), hoy + timedelta(days=5), 'Cámara Frío C1'),  # Próximo a vencer
            ('INS-MAN-005', 'Mantequilla Sin Sal Extra Pasteurizada 82% MG', cat_lacteos, 'KG', Decimal('18.500'), Decimal('6.000'), Decimal('8900'), hoy + timedelta(days=25), 'Cámara Frío C1'),
            ('INS-CRE-006', 'Crema de Leche Fresca 36% MG para Batir', cat_lacteos, 'LT', Decimal('4.000'), Decimal('8.000'), Decimal('4600'), hoy + timedelta(days=4), 'Cámara Frío C2'),  # En alerta de stock y por vencer
            ('INS-CHO-007', 'Chocolate Belga Callebaut 70% Cacao (Monedas)', cat_choco, 'KG', Decimal('22.000'), Decimal('5.000'), Decimal('18900'), hoy + timedelta(days=240), 'Bodega Climatizada D1'),
            ('INS-MNJ-008', 'Manjar Artesanal de Campo Receta Tradicional', cat_choco, 'KG', Decimal('28.000'), Decimal('8.000'), Decimal('5400'), hoy + timedelta(days=45), 'Bodega Climatizada D2'),
            ('INS-FRA-009', 'Frambuesas Orgánicas Seleccionadas', cat_frutas, 'KG', Decimal('12.500'), Decimal('4.000'), Decimal('6800'), hoy + timedelta(days=3), 'Cámara Frío C3'),
            ('INS-FON-010', 'Pasta Fondant Elástica Profesional Blanca', cat_frutas, 'KG', Decimal('16.000'), Decimal('5.000'), Decimal('7500'), hoy + timedelta(days=90), 'Estante Decoración E1'),
            ('INS-CAJ-011', 'Kit Base Rígida + Caja Isotérmica Alta Pastelería', cat_pack, 'UNIDAD', Decimal('35.000'), Decimal('10.000'), Decimal('2900'), None, 'Bodega Empaque F1'),
        ]

        insumos_map = {}
        for sku, nombre, cat, unidad, stock, minimo, costo, venc, ubic in insumos_config:
            ins, _ = Insumo.objects.update_or_create(
                codigo_sku=sku,
                defaults={
                    'nombre': nombre,
                    'categoria': cat,
                    'unidad_medida': unidad,
                    'stock_actual': stock,
                    'stock_minimo': minimo,
                    'costo_unitario': costo,
                    'fecha_vencimiento': venc,
                    'ubicacion_bodega': ubic,
                    'activo': True,
                },
            )
            insumos_map[sku] = ins

        # 4. Crear Productos Base y sus Listas de Materiales (BOM)
        prod_belga, _ = ProductoPasteleria.objects.update_or_create(
            codigo='REC-BELGA-15',
            defaults={
                'nombre': 'Torta Imperial Chocolate Belga 70% & Frambuesa',
                'categoria_producto': 'TORTA_AUTOR',
                'porciones_base': 15,
                'precio_base': Decimal('46000'),
                'tiempo_elaboracion_horas': Decimal('6.5'),
                'requiere_refrigeracion': True,
                'descripcion': 'Bizcocho húmedo de cacao alcalino, triple capa de ganache belga 70% y reducción de frambuesas orgánicas.',
                'instrucciones_receta': 'Hornear a 170°C por 38 min. Reposar ganache 4h en frío antes de montar.',
            },
        )
        prod_novios, _ = ProductoPasteleria.objects.update_or_create(
            codigo='REC-NOVIOS-30',
            defaults={
                'nombre': 'Torta Nupcial Escultural Buttercream & Manjar Nuez',
                'categoria_producto': 'NOVIOS_EVENTOS',
                'porciones_base': 30,
                'precio_base': Decimal('98000'),
                'tiempo_elaboracion_horas': Decimal('12.0'),
                'requiere_refrigeracion': True,
                'descripcion': 'Estructura de dos niveles con bizcocho vainilla Bourbon, manjar de campo y acabado en buttercream suizo o fondant.',
                'instrucciones_receta': 'Estructurar con pilares internos sanitizados y base doble.',
            },
        )
        prod_keto, _ = ProductoPasteleria.objects.update_or_create(
            codigo='REC-SIN-GLU-15',
            defaults={
                'nombre': 'Torta Financier de Almendra & Berries (Sin Gluten)',
                'categoria_producto': 'SIN_ALERGENOS',
                'porciones_base': 15,
                'precio_base': Decimal('52000'),
                'tiempo_elaboracion_horas': Decimal('5.5'),
                'requiere_refrigeracion': True,
                'descripcion': 'Elaborada 100% con harina de almendras fina, crema batida fresca y frambuesas orgánicas.',
                'instrucciones_receta': 'Trabajar en mesón sanitizado libre de contaminación cruzada de trigo.',
            },
        )

        # Configurar ItemBOM para cada receta
        bom_definitions = [
            # BOM Torta Imperial Chocolate Belga (15 porciones base)
            (prod_belga, 'INS-HAR-001', 'BATIDO_MASA', Decimal('0.650'), Decimal('3.00'), 'Tamizar 2 veces'),
            (prod_belga, 'INS-AZU-002', 'BATIDO_MASA', Decimal('0.500'), Decimal('2.00'), 'Batido punto letra'),
            (prod_belga, 'INS-HUE-004', 'BATIDO_MASA', Decimal('8.000'), Decimal('5.00'), 'Huevos a temperatura ambiente'),
            (prod_belga, 'INS-CHO-007', 'RELLENO', Decimal('0.750'), Decimal('3.00'), 'Emulsión Ganache 70%'),
            (prod_belga, 'INS-CRE-006', 'RELLENO', Decimal('0.600'), Decimal('4.00'), 'Crema para ganache y bordes'),
            (prod_belga, 'INS-FRA-009', 'RELLENO', Decimal('0.450'), Decimal('5.00'), 'Frambuesas frescas seleccionadas'),
            (prod_belga, 'INS-CAJ-011', 'PACKAGING', Decimal('1.000'), Decimal('0.00'), 'Caja isotérmica 15-20 porc.'),

            # BOM Torta Nupcial Escultural (30 porciones base)
            (prod_novios, 'INS-HAR-001', 'BATIDO_MASA', Decimal('1.400'), Decimal('3.00'), 'Bizcocho firme estructural'),
            (prod_novios, 'INS-AZU-002', 'BATIDO_MASA', Decimal('1.100'), Decimal('2.00'), 'Merengue suizo y bizcocho'),
            (prod_novios, 'INS-HUE-004', 'BATIDO_MASA', Decimal('16.000'), Decimal('5.00'), 'Huevos frescos'),
            (prod_novios, 'INS-MAN-005', 'COBERTURA_DECORACION', Decimal('0.900'), Decimal('3.00'), 'Buttercream de merengue suizo'),
            (prod_novios, 'INS-MNJ-008', 'RELLENO', Decimal('1.200'), Decimal('3.00'), 'Capas dobles de manjar artesanal'),
            (prod_novios, 'INS-FON-010', 'COBERTURA_DECORACION', Decimal('0.800'), Decimal('5.00'), 'Flores y detalles modelados'),
            (prod_novios, 'INS-CAJ-011', 'PACKAGING', Decimal('1.000'), Decimal('0.00'), 'Caja alta estructurada'),

            # BOM Torta Sin Gluten Almendra & Berries (15 porciones base)
            (prod_keto, 'INS-ALM-003', 'BATIDO_MASA', Decimal('0.750'), Decimal('2.00'), 'Harina de almendras pura'),
            (prod_keto, 'INS-HUE-004', 'BATIDO_MASA', Decimal('10.000'), Decimal('5.00'), 'Batido aireado sin gluten'),
            (prod_keto, 'INS-CRE-006', 'RELLENO', Decimal('0.700'), Decimal('4.00'), 'Chantilly estabilizada'),
            (prod_keto, 'INS-FRA-009', 'COBERTURA_DECORACION', Decimal('0.550'), Decimal('5.00'), 'Corona de frambuesas orgánicas'),
            (prod_keto, 'INS-CAJ-011', 'PACKAGING', Decimal('1.000'), Decimal('0.00'), 'Caja sellada libre de alérgenos'),
        ]

        for prod, sku, etapa, cant, merma, nota in bom_definitions:
            ItemBOM.objects.update_or_create(
                producto=prod,
                insumo=insumos_map[sku],
                etapa_uso=etapa,
                defaults={
                    'cantidad_requerida': cant,
                    'merma_tecnica_pct': merma,
                    'notas_tecnicas': nota,
                },
            )

        # 5. Crear Pedidos Personalizados en las distintas etapas del Kanban
        if PedidoPersonalizado.objects.count() == 0:
            ahora = timezone.now()

            # Pedido 1: En etapa LISTO y ENTREGADO con Firma Digital
            p1 = PedidoPersonalizado.objects.create(
                cliente=clientes_objs[0],
                producto_base=prod_novios,
                vendedor=usuarios_creados['VENTAS'],
                pastelero_asignado=usuarios_creados['COCINA'],
                porciones_solicitadas=30,
                sabor_bizcocho='Vainilla Bourbon de Madagascar',
                relleno_principal='Manjar Artesanal de Campo y Ganache Blanco',
                cobertura_diseno='Buttercream Suizo Texturizado con Peonías en Fondant',
                nivel_complejidad='ALTA_ESCULTURAL',
                dedicatoria_texto='Valentina & Mateo · Nuestra Boda',
                descripcion_diseno='Torta de dos pisos tonos marfil y dorado, flores modeladas a mano.',
                alergias_considerar='Sin trazas de maní',
                fecha_entrega_comprometida=ahora - timedelta(hours=3),
                modalidad_entrega='DESPACHO_DOMICILIO',
                direccion_entrega=clientes_objs[0].direccion_habitual,
                comuna_entrega=clientes_objs[0].comuna,
                estado_comercial='CONFIRMADO',
                estado_kanban='RECIBIDO',
                prioridad='URGENTE',
                abono_pagado=Decimal('75000'),
            )
            p1.recalcular_cotizacion(guardar=True)
            p1.cambiar_estado_kanban('EN_PREPARACION', usuario=usuarios_creados['COCINA'], comentario='Pesaje BOM completado.')
            p1.cambiar_estado_kanban('HORNEADO_DECORADO', usuario=usuarios_creados['COCINA'], comentario='Horneado y montaje de 2 pisos finalizado.')
            p1.cambiar_estado_kanban('CONTROL_CALIDAD', usuario=usuarios_creados['BODEGA'], comentario='Control sanitario 4.0°C aprobado.')
            p1.cambiar_estado_kanban('LISTO', usuario=usuarios_creados['COCINA'], comentario='Empacada en caja isotérmica lista para despacho.')

            # Pedido 2: En etapa CONTROL_CALIDAD (listo para salir a ruta)
            p2 = PedidoPersonalizado.objects.create(
                cliente=clientes_objs[1],
                producto_base=prod_belga,
                vendedor=usuarios_creados['VENTAS'],
                pastelero_asignado=usuarios_creados['COCINA'],
                porciones_solicitadas=20,
                sabor_bizcocho='Cacao Belga Intenso 70%',
                relleno_principal='Ganache Callebaut 70% y Frambuesas Orgánicas',
                cobertura_diseno='Drip Cake de Chocolate Oscuro y Frutos Rojos',
                nivel_complejidad='PERSONALIZADO_MEDIO',
                dedicatoria_texto='¡Felices 40 Años Sebastián!',
                descripcion_diseno='Acabado semimate en ganache con corona de frambuesas frescas.',
                fecha_entrega_comprometida=ahora + timedelta(hours=4),
                modalidad_entrega='DESPACHO_DOMICILIO',
                direccion_entrega=clientes_objs[1].direccion_habitual,
                comuna_entrega=clientes_objs[1].comuna,
                estado_comercial='CONFIRMADO',
                estado_kanban='RECIBIDO',
                prioridad='ALTA',
                abono_pagado=Decimal('40000'),
            )
            InsumoExtraPedido.objects.create(
                pedido=p2,
                insumo=insumos_map['INS-FRA-009'],
                cantidad_extra=Decimal('0.300'),
                motivo='300g extra de frambuesas frescas en corona superior',
            )
            p2.recalcular_cotizacion(guardar=True)
            p2.cambiar_estado_kanban('EN_PREPARACION', usuario=usuarios_creados['COCINA'], comentario='Iniciando batido con descuento automático BOM.')
            p2.cambiar_estado_kanban('HORNEADO_DECORADO', usuario=usuarios_creados['COCINA'], comentario='Decoración Drip Cake terminada.')
            p2.cambiar_estado_kanban('CONTROL_CALIDAD', usuario=usuarios_creados['BODEGA'], comentario='Verificando estabilidad térmica en cámara.')

            # Pedido 3: En etapa HORNEADO_DECORADO
            p3 = PedidoPersonalizado.objects.create(
                cliente=clientes_objs[2],
                producto_base=prod_belga,
                vendedor=usuarios_creados['VENTAS'],
                pastelero_asignado=usuarios_creados['COCINA'],
                porciones_solicitadas=30,
                sabor_bizcocho='Bizcocho Vainilla & Cacao',
                relleno_principal='Manjar de Campo y Ganache',
                cobertura_diseno='Cobertura Corporativa con Logo en Chocolate',
                nivel_complejidad='PERSONALIZADO_MEDIO',
                dedicatoria_texto='Aniversario Hotel Cordillera',
                descripcion_diseno='Colores institucionales burdeos y oro.',
                fecha_entrega_comprometida=ahora + timedelta(hours=10),
                modalidad_entrega='DESPACHO_DOMICILIO',
                direccion_entrega=clientes_objs[2].direccion_habitual,
                comuna_entrega=clientes_objs[2].comuna,
                estado_comercial='CONFIRMADO',
                estado_kanban='RECIBIDO',
                prioridad='NORMAL',
                abono_pagado=Decimal('50000'),
            )
            p3.recalcular_cotizacion(guardar=True)
            p3.cambiar_estado_kanban('EN_PREPARACION', usuario=usuarios_creados['COCINA'], comentario='Descuento BOM ejecutado.')
            p3.cambiar_estado_kanban('HORNEADO_DECORADO', usuario=usuarios_creados['COCINA'], comentario='En proceso de alisado de ganache.')

            # Pedido 4: En etapa EN_PREPARACION
            p4 = PedidoPersonalizado.objects.create(
                cliente=clientes_objs[3],
                producto_base=prod_keto,
                vendedor=usuarios_creados['VENTAS'],
                pastelero_asignado=usuarios_creados['COCINA'],
                porciones_solicitadas=15,
                sabor_bizcocho='Financier 100% Harina de Almendras (Sin Gluten)',
                relleno_principal='Chantilly Fresca y Frambuesas Orgánicas',
                cobertura_diseno='Naked Cake Rústico con Berries',
                nivel_complejidad='ESTANDAR',
                dedicatoria_texto='Feliz Cumpleaños Fran',
                descripcion_diseno='Elaborar en estación libre de gluten.',
                alergias_considerar='Celíaca - Cero trazas de trigo',
                fecha_entrega_comprometida=ahora + timedelta(hours=18),
                modalidad_entrega='DESPACHO_DOMICILIO',
                direccion_entrega=clientes_objs[3].direccion_habitual,
                comuna_entrega=clientes_objs[3].comuna,
                estado_comercial='CONFIRMADO',
                estado_kanban='RECIBIDO',
                prioridad='ALTA',
                abono_pagado=Decimal('30000'),
            )
            p4.recalcular_cotizacion(guardar=True)
            p4.cambiar_estado_kanban('EN_PREPARACION', usuario=usuarios_creados['COCINA'], comentario='Mise en place sin gluten en curso.')

            # Pedido 5: En etapa RECIBIDO (Sin descuento BOM aún -> ideal para demostrar en vivo el paso a EN_PREPARACION)
            p5 = PedidoPersonalizado.objects.create(
                cliente=clientes_objs[4],
                producto_base=prod_belga,
                vendedor=usuarios_creados['VENTAS'],
                porciones_solicitadas=15,
                sabor_bizcocho='Vainilla Bourbon',
                relleno_principal='Ganache Belga 70% y Manjar de Campo',
                cobertura_diseno='Buttercream Suizo Azul Noche & Dorado',
                nivel_complejidad='PERSONALIZADO_MEDIO',
                dedicatoria_texto='Felicidades Rodrigo',
                descripcion_diseno='Estilo moderno minimalista con detalles en pan de oro.',
                fecha_entrega_comprometida=ahora + timedelta(days=1, hours=4),
                modalidad_entrega='DESPACHO_DOMICILIO',
                direccion_entrega=clientes_objs[4].direccion_habitual,
                comuna_entrega=clientes_objs[4].comuna,
                estado_comercial='CONFIRMADO',
                estado_kanban='RECIBIDO',
                prioridad='NORMAL',
                abono_pagado=Decimal('32000'),
            )
            p5.recalcular_cotizacion(guardar=True)
            HistorialKanban.objects.create(
                pedido=p5,
                estado_anterior='RECIBIDO',
                estado_nuevo='RECIBIDO',
                usuario=usuarios_creados['VENTAS'],
                comentario='Pedido confirmado en Ventas; pendiente de iniciar preparación y descuento BOM en cocina.',
            )

            # 6. Crear Ruta de Despacho y Paradas de Entrega
            ruta1, _ = RutaDespacho.objects.update_or_create(
                codigo_ruta='RUTA-2026-01',
                defaults={
                    'nombre_ruta': 'Ruta Refrigerada Sector Oriente (Vitacura - Providencia - Las Condes)',
                    'repartidor': usuarios_creados['REPARTIDOR'],
                    'vehiculo_patente': 'KRTW-88',
                    'vehiculo_refrigerado': True,
                    'temperatura_salida_c': Decimal('4.1'),
                    'fecha_ruta': hoy,
                    'hora_salida_programada': '09:30',
                    'estado_ruta': 'EN_RUTA',
                    'observaciones_logistica': 'Mantener cámara isotérmica entre 3°C y 5°C durante todo el recorrido.',
                },
            )

            # Parada 1: Ya entregada y firmada digitalmente
            desp1 = DespachoPedido.objects.create(
                ruta=ruta1,
                pedido=p1,
                orden_parada=1,
                direccion_destino=p1.direccion_entrega,
                comuna_destino=p1.comuna_entrega,
                telefono_contacto=p1.cliente.telefono,
                ventana_horaria='10:00 - 11:30',
                estado_entrega='EN_CAMINO',
            )
            desp1.confirmar_entrega_digital(
                nombre_receptor='Valentina Errázuriz Montes',
                rut_receptor='17.456.890-1',
                firma_base64=DEMO_SIGNATURE_BASE64,
                parentesco='Cliente Titular (Novia)',
                temperatura_c=Decimal('4.2'),
                observaciones='Torta nupcial entregada en salón de eventos refrigerado en perfecto estado.',
                coordenadas='-33.3984, -70.5941',
                usuario=usuarios_creados['REPARTIDOR'],
            )

            # Parada 2: En camino (Lista para demostrar la firma digital en vivo durante la defensa)
            DespachoPedido.objects.create(
                ruta=ruta1,
                pedido=p2,
                orden_parada=2,
                direccion_destino=p2.direccion_entrega,
                comuna_destino=p2.comuna_entrega,
                telefono_contacto=p2.cliente.telefono,
                ventana_horaria='12:00 - 14:00',
                estado_entrega='EN_CAMINO',
            )

            # Parada 3: Pendiente
            DespachoPedido.objects.create(
                ruta=ruta1,
                pedido=p3,
                orden_parada=3,
                direccion_destino=p3.direccion_entrega,
                comuna_destino=p3.comuna_entrega,
                telefono_contacto=p3.cliente.telefono,
                ventana_horaria='15:00 - 17:00',
                estado_entrega='PENDIENTE',
            )

        self.stdout.write(self.style.SUCCESS("[OK] Datos de Dulce Arte cargados exitosamente en PostgreSQL."))
        self.stdout.write(self.style.WARNING("Credenciales disponibles (Contraseña para todos: dulcearte2026):"))
        self.stdout.write("  - Admin General : admin")
        self.stdout.write("  - Ventas        : ventas_camila")
        self.stdout.write("  - Cocina Kanban : chef_matias")
        self.stdout.write("  - Bodega BOM    : bodega_pedro")
        self.stdout.write("  - Repartidor    : repartidor_lucas")
