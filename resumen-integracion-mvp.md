# Resumen de Integración y Funcionamiento (MVP)

**Fecha de validación:** 21 de Septiembre de 2026  
**Estado:** Integración exitosa de 3 componentes principales mediante contenedores Docker.

## 1. Arquitectura Desplegada

Se logró orquestar un entorno local funcional que simula la recolección, almacenamiento y exposición de métricas de infraestructura. El sistema consta de tres contenedores comunicados por una red interna de Docker:

1. **Simulator Service (Puerto 8000):** Generador de métricas.
2. **Prometheus (Puerto 9090):** Base de datos de series temporales.
3. **Monitoring Service (Puerto 8080):** API REST de consulta y normalización.

---

## 2. Flujo de Datos Comprobado

El flujo de información verificado paso a paso durante la ejecución fue el siguiente:

1. **Generación Sintética:** El Simulator Service (escrito en Python) calcula métricas de CPU, memoria, red y disco para dos nodos virtuales (`node-01` y `node-02`). 
2. **Exposición Cruda:** El Simulator expone estos datos en texto plano en la ruta `/metrics` (formato compatible con Node Exporter), adjuntando la etiqueta `origin="simulated"` y un `cluster` único por ejecución.
3. **Scrapeo (Recolección):** El contenedor de Prometheus lee (scrapea) el puerto 8000 del simulador cada 5 segundos, guardando el historial de datos.
4. **Consulta REST:** Al recibir una petición HTTP en el puerto 8080, el Monitoring Service (Java/Spring Boot) traduce la solicitud a una consulta PromQL exacta.
5. **Normalización:** Monitoring extrae el JSON crudo de Prometheus, aplica la lógica de negocio (por ejemplo, restar disco libre al disco total para obtener disco usado), estandariza los timestamps y responde con un JSON final estructurado y validado.

---

## 3. Evidencia de Funcionamiento

Durante la prueba de integración `docker-compose up --build`, se validaron con éxito los siguientes hitos:

### A. Ejecución del Simulador
- **Prueba:** Acceso a `http://localhost:8000/metrics`
- **Resultado:** Se observó la salida cruda de métricas como `node_memory_MemTotal_bytes` y `node_cpu_seconds_total`, confirmando que el motor de simulación funciona en modo `realtime` y respeta el esquema de etiquetas del contrato.

### B. Almacenamiento en Prometheus
- **Prueba:** Acceso a la interfaz web en `http://localhost:9090`
- **Resultado:** Se verificó la ingesta de datos en tiempo real mediante la pestaña "Graph". Prometheus reconoció al simulador como un "target" válido gracias al archivo `prometheus-demo.yml`.

### C. Consumo desde Monitoring Service
- **Prueba:** Petición GET a `http://localhost:8080/api/v1/metrics/current?metric=node.filesystem.used`
- **Resultado:** Respuesta HTTP 200 OK con un JSON estructurado. 
  - **Validación destacada:** El servicio entregó el estado `dataStatus: "complete"`.
  - **Lógica de negocio aplicada:** El servicio identificó correctamente los tipos de sistema de archivos (`ext4` y `xfs`), los discos (`/dev/sda1` y `/dev/nvme0n1`) e hizo la operación matemática para entregar únicamente el valor final en bytes.

### D. Empaquetado
- Se validó la creación de un `Dockerfile` funcional para el Monitoring Service basado en la imagen `eclipse-temurin:21-jre-jammy`, aislando la ejecución de Java del sistema operativo host.

---

## 4. Punto de Conexión para Siguientes Fases

El sistema actual expone un contrato estable para que cualquier consumidor (como el futuro **Data Processing Service**) pueda extraer historial de datos. 

La integración demostró que un servicio externo no necesita saber hablar PromQL ni lidiar con huecos de red o datos corruptos (`NaN`/`Inf`); simplemente debe hacer peticiones REST a `http://monitoring:8080/api/v1/metrics/history` pasando los parámetros `metric`, `start`, `end` y `stepSeconds` para recibir JSON normalizado listo para ser transformado. Si Data Processing utiliza pandas, la conversión a DataFrame ocurre dentro de ese servicio y no forma parte del contrato HTTP.

## 5. Límite entre Monitoring, Data Processing y Gateway

- Monitoring define y entrega métricas normalizadas, con unidad, timestamp, identidad, procedencia y calidad.
- Data Processing consume directamente esa API interna y define las reglas analíticas: tratamiento de ausencias, alineación, agregaciones y features.
- Gateway es la entrada del Frontend. Publica las rutas confirmadas de Monitoring con el prefijo `/api/monitoring/v1/metrics/*` y posteriormente publicará operaciones de Data Processing cuando exista su OpenAPI.
- Frontend convierte los valores en gráficas, porcentajes, unidades legibles y explicaciones. No consulta microservicios ni Supabase directamente.

El Gateway no consulta Prometheus o Supabase y Data Processing no utiliza Gateway para sus pipelines internos.

## 6. Avance de Prediction revisado

La rama [`Criss`](https://github.com/woshtsu/green-ai-project-docs/tree/Criss) aporta un núcleo ML experimental para pronóstico de CPU con baselines, Random Forest y XGBoost. Se mantiene fuera del flujo desplegado y sus cifras corresponden a datos simulados. Antes de conectarlo deben corregirse la selección del modelo sobre TEST, las fronteras temporales y las pruebas anti-leakage; además, Data Processing y Prediction deben acordar un único contrato versionado y el equipo debe implementar la API del Prediction Service. Ver [revisión detallada](revision-prediction-criss.md).

## Referencia de BD actualizada — 2026-09-22

Consultar el [modelo de BD](modelo-bd.md): diagrama y campos completos de `usuario`, `hardware` y `logs`, con mapeos y limitaciones de integración. El diagrama aporta tipos y relaciones; la extracción SQL del usuario confirma tipos y nulabilidad. La extracción completa confirma defaults, longitudes/precisión, restricciones, índices y RLS; verificación documental del esquema cerrada. Monitoring conserva Prometheus como fuente y Simulator conserva JSON/JSONL como persistencia; el acceso a inventario SQL es futuro. Esta referencia actualiza las suposiciones del esquema, sin ampliar el catálogo de métricas ni implementar acceso a BD.
