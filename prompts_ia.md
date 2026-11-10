# Registro de Consultas y Apoyo de Inteligencia Artificial (`prompts_ia.md`)

**Asignatura:** Desarrollo Backend — Evaluación Parcial N°3  
**Docente:** Marcelo Alvarado Aravena  
**Proyecto Asignado:** Proyecto 3 — Sistema de Trazabilidad y Gestión de Pedidos para Pastelería Artesanal (**Dulce Arte**)  
**Arquitectura:** Paradigma 4+1 de Kruchten · Django + Django REST Framework (DRF) + PostgreSQL + AWS EC2  

---

## 1. Propósito del Registro

En cumplimiento del **Criterio de Evaluación 4** de la rúbrica (*"Codifica una aplicación backend con acceso a base de datos y seguridad, según los requerimientos del problema planteado y orientaciones generadas por herramientas de inteligencia artificial"*), este documento detalla de forma estructurada los prompts utilizados, las decisiones técnicas adoptadas y las validaciones realizadas durante el desarrollo del sistema **Dulce Arte**.

---

## 2. Bitácora Estructurada de Prompts y Soluciones Aplicadas

### Prompt 1: Modelado de Datos Relacional (PostgreSQL) y Paradigma 4+1 para Lista de Materiales (BOM)
> **Consulta realizada a la IA:**  
> *"Actúa como arquitecto de software senior experto en Django y PostgreSQL. Necesito modelar bajo el Paradigma 4+1 el Proyecto 3 'Pastelería Artesanal Dulce Arte'. El sistema debe conectar: 1) Cotización y registro de pedidos personalizados con escalado de porciones y nivel de complejidad, 2) Recetas base y Lista de Materiales (BOM - Bill of Materials) con porcentaje de merma técnica e ingredientes extra por pedido, 3) Tablero Kanban de cocina con 5 estados exactos (Recibido, En Preparación, Horneado/Decorado, Control de Calidad, Listo) y 4) Rutas de despacho con confirmación mediante firma digital o comprobante fotográfico. Diseña los modelos de Django garantizando integridad referencial y transacciones atómicas."*

- **Orientación generada por la IA y aplicación en el código:**
  - Se estructuraron **12 modelos relacionales** en [`gestion_pasteleria/models.py`](gestion_pasteleria/models.py):
    - `PerfilUsuario`, `Cliente`, `CategoriaInsumo`, `Insumo`, `ProductoPasteleria`, `ItemBOM`, `PedidoPersonalizado`, `InsumoExtraPedido`, `MovimientoInventario`, `HistorialKanban`, `RutaDespacho`, `DespachoPedido`.
  - Se incorporó el cálculo de factor de escala (`factor_escala_porciones = porciones_solicitadas / producto_base.porciones_base`) y porcentaje de merma técnica (`merma_tecnica_pct`) en cada línea `ItemBOM`.

---

### Prompt 2: Algoritmo de Descuento Automático de Inventario mediante BOM con Bloqueo Transaccional
> **Consulta realizada a la IA:**  
> *"En Django con PostgreSQL, ¿cómo implemento el método de negocio para que cuando un PedidoPersonalizado pase a la etapa 'EN_PREPARACION' en el Tablero Kanban se descuenten automáticamente los insumos del inventario según su Lista de Materiales (BOM) escalada por las porciones solicitadas más los insumos extra del pedido, evitando condiciones de carrera y dobles descuentos?"*

- **Orientación generada por la IA y aplicación en el código:**
  - Se implementó el método `@transaction.atomic def descontar_insumos_bom(self, usuario=None)` dentro de `PedidoPersonalizado` en [`gestion_pasteleria/models.py`](gestion_pasteleria/models.py).
  - Utiliza `Insumo.objects.select_for_update()` para bloquear las filas de los insumos en PostgreSQL durante la transacción.
  - Verifica previamente si existe stock suficiente para cada insumo requerido (`obtener_explosion_bom()`); si algún insumo presenta déficit, lanza un `ValidationError` detallando la cantidad requerida vs. disponible y revierte toda la operación.
  - Registra cada descuento en el Kardex inmutable `MovimientoInventario` con `tipo_movimiento='SALIDA_BOM_PEDIDO'`, `stock_anterior`, `cantidad`, `stock_resultante` y referencia al pedido, marcando `insumos_descontados = True`.

---

### Prompt 3: Diseño de API REST con Django REST Framework (DRF) y Simulador de Cotizaciones en Vivo
> **Consulta realizada a la IA:**  
> *"Necesito crear ViewSets en Django REST Framework para todos los modelos de Dulce Arte, además de endpoints personalizados (`@action`) para: 1) simular una cotización en tiempo real devolviendo el costo BOM y factibilidad de stock antes de guardar, 2) mover tarjetas en el Tablero Kanban vía AJAX/Fetch y 3) confirmar entregas en ruta recibiendo una firma digital en Base64."*

- **Orientación generada por la IA y aplicación en el código:**
  - Se implementaron los serializadores en [`gestion_pasteleria/serializers.py`](gestion_pasteleria/serializers.py) y los `ModelViewSet` en [`gestion_pasteleria/api_views.py`](gestion_pasteleria/api_views.py).
  - Se crearon las acciones personalizadas:
    - `POST /api/v1/pedidos/simular_cotizacion/`
    - `GET /api/v1/pedidos/{id}/explosion_bom/`
    - `POST /api/v1/pedidos/{id}/descontar_bom/`
    - `POST /api/v1/pedidos/{id}/mover_kanban/`
    - `POST /api/v1/despachos/{id}/confirmar_entrega/`
    - `GET /api/v1/insumos/alertas_criticas/` y `POST /api/v1/insumos/{id}/ajustar_stock/`

---

### Prompt 4: Personalización Avanzada de Django Admin con Templates y Acciones Masivas
> **Consulta realizada a la IA:**  
> *"Según el Criterio 2 de la rúbrica, debo personalizar el Django Admin registrando todos los modelos con filtros, búsquedas, campos visuales optimizados y templates personalizados. ¿Cómo sobrescribo `admin/base_site.html` y `admin/index.html` para mostrar KPIs en vivo de la pastelería y agregar badges visuales e inlines en `admin.py`?"*

- **Orientación generada por la IA y aplicación en el código:**
  - Se creó el procesador de contexto [`gestion_pasteleria/context_processors.py`](gestion_pasteleria/context_processors.py) que inyecta indicadores en tiempo real (`KPI_PEDIDOS_COCINA`, `KPI_INSUMOS_ALERTA`, `KPI_PEDIDOS_LISTOS`, `KPI_ENTREGAS_PENDIENTES`).
  - Se personalizaron los templates [`templates/admin/base_site.html`](templates/admin/base_site.html) y [`templates/admin/index.html`](templates/admin/index.html).
  - En [`gestion_pasteleria/admin.py`](gestion_pasteleria/admin.py) se registraron los 12 modelos con `format_html` para semáforos de stock crítico, alertas de vencimiento de insumos perecibles, etapas Kanban, inlines (`ItemBOMInline`, `InsumoExtraPedidoInline`, `HistorialKanbanInline`, `DespachoPedidoInline`) y acciones administrativas masivas.

---

### Prompt 5: Lienzo Interactivo HTML5 (`<canvas>`) para Firma Digital de Recepción en Ruta
> **Consulta realizada a la IA:**  
> *"Genera un componente en HTML5 y JavaScript puro (compatible con eventos mouse y touch móvil) que permita al cliente firmar la recepción de su torta en pantalla, convierta el trazo a Data URI PNG Base64 (`canvas.toDataURL('image/png')`) y lo envíe al backend Django junto con el RUT del receptor, temperatura de entrega y fotografía opcional."*

- **Orientación generada por la IA y aplicación en el código:**
  - Se implementó en [`templates/gestion_pasteleria/confirmar_entrega.html`](templates/gestion_pasteleria/confirmar_entrega.html) un pad de firma digital con soporte para `mousedown/mousemove/mouseup` y `touchstart/touchmove/touchend`, botón de limpieza y generador de firma rápida de prueba, conectado al método transaccional `DespachoPedido.confirmar_entrega_digital()`.

---

### Prompt 6: Automatización de Despliegue en Instancia Única AWS Academy EC2 (Ubuntu + PostgreSQL + Gunicorn + Nginx)
> **Consulta realizada a la IA:**  
> *"Elabora un script bash idempotente para desplegar esta aplicación Django + DRF + PostgreSQL en una instancia EC2 Ubuntu de AWS Academy. Debe consultar automáticamente la IP pública desde los metadatos de EC2 (`169.254.169.254`), crear la base de datos en PostgreSQL, aplicar migraciones, cargar el seed de datos y configurar Gunicorn con Systemd y Nginx en el puerto 80."*

- **Orientación generada por la IA y aplicación en el código:**
  - Se creó el script [`deploy/deploy_aws.sh`](deploy/deploy_aws.sh) que automatiza de principio a fin la configuración de PostgreSQL, entorno virtual, variables de entorno `.env`, migraciones, archivos estáticos con WhiteNoise/Nginx y demonios `systemd`.
