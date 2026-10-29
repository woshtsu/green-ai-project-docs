# Documentación de endpoints de Green AI

Fecha de revisión: 22 de octubre de 2026.

## 1. Alcance y lectura del documento

Inventario obtenido mediante revisión estática de controladores, routers, seguridad, contratos y configuración del workspace. Describe lo implementado en los archivos revisados; no constituye una prueba de ejecución de cada endpoint ni certifica que todos estén desplegados. Los ejemplos son ilustrativos y no contienen credenciales reales.

Se distinguen:

- **API pública de aplicación:** siete operaciones permitidas por el Gateway.
- **API interna:** rutas de Monitoring, Data Processing y Prediction. El cliente debe usar el Gateway.
- **Operación y observabilidad:** salud, exportación de métricas y documentación automática.
- **Código anterior/no integrado:** backend y exporter de `GreenAi_TPI`, ausentes del Compose actual.

Un endpoint se identifica por **método HTTP + ruta**. GET consulta datos; POST envía un cuerpo para una operación, como inferencia. Query parameters van después de `?`; los encabezados transportan autenticación y correlación.

## 2. Direcciones base y acceso

| Componente | Dirección habitual | Alcance |
|---|---|---|
| Gateway | `http://127.0.0.1:8081` | Entrada del frontend |
| Monitoring | `http://monitoring:8080` | DNS interno Docker; el Compose raíz también publica `127.0.0.1:8080` |
| Data Processing | `http://data-processing:8000` | Interno |
| Prediction | `http://prediction:8000` | Interno |
| Simulator | `http://simulator:8000` | Exporter interno según Compose; raíz también publica puerto 8000 |
| Prometheus | `http://127.0.0.1:9090` | Consola y API de observabilidad |
| Grafana | `http://127.0.0.1:3000` | Incluido en el paquete portable |
| Frontend | `http://127.0.0.1:3001` | Archivos estáticos; no es un backend REST |

En la prueba portable con `test.env`: Gateway 18081, frontend 13001 y Prometheus 19090. Los puertos internos no cambian. Los nombres DNS de Docker no se resuelven directamente desde el navegador del equipo anfitrión. `127.0.0.1` siempre representa el equipo desde el que se hace la petición.

## 3. Autenticación, roles y encabezados

Las siete operaciones públicas requieren:

```http
Authorization: Bearer <ACCESS_TOKEN_DE_SUPABASE>
Accept: application/json
X-Request-Id: exposicion-001
```

Para POST agregar `Content-Type: application/json`. `X-Request-Id` permite correlacionar solicitudes y respuestas; los servicios pueden generarlo o normalizarlo.

El Gateway valida firma RS256/ES256 usando JWKS, emisor configurado, audiencia `authenticated`, expiración, sujeto no vacío, claim `role=authenticated` y que el usuario no sea anónimo. Además exige `user_role=ADMIN` o `user_role=OPERATOR`. Un JWT válido sin esos roles no basta. El inicio de sesión usa Supabase Auth desde el frontend; **el Gateway actual no implementa `/login` ni `/registro`**.

| Estado | Significado en el acceso al Gateway |
|---|---|
| 401 | Token ausente o inválido; incluye `WWW-Authenticate: Bearer` |
| 403 | Cuenta sin permiso o acceso denegado |

CORS permite el origen exacto de `GATEWAY_CORS_ALLOWED_ORIGIN`, métodos GET/POST/OPTIONS y encabezados Accept, Content-Type, Authorization y X-Request-Id. OPTIONS corresponde a preflight del navegador, no a una operación de negocio. CORS no reemplaza la autenticación.

Los servicios internos revisados no implementan esta misma validación JWT: deben mantenerse en la red interna. La ausencia de una ruta en el Gateway significa que no está publicada, aunque exista en el servicio.

## 4. Inventario de API pública del Gateway

Todas las respuestas exitosas de estas operaciones son JSON con HTTP 200.

| Método | Ruta pública | Destino interno | Función |
|---|---|---|---|
| GET | `/api/monitoring/v1/metrics/catalog` | Monitoring `/api/v1/metrics/catalog` | Catálogo de métricas permitidas |
| GET | `/api/monitoring/v1/metrics/current` | Monitoring `/api/v1/metrics/current` | Valores actuales |
| GET | `/api/monitoring/v1/metrics/history` | Monitoring `/api/v1/metrics/history` | Series temporales |
| GET | `/api/processing/v1/metrics/history` | Data Processing `/api/v1/metrics/history` | Histórico normalizado |
| GET | `/api/processing/v1/historical-logs` | Data Processing `/api/v1/historical-logs` | Logs históricos de Supabase |
| GET | `/api/processing/v1/prediction/dataset` | Data Processing `/api/v1/prediction/dataset` | Ventana CPU para inferencia |
| POST | `/api/prediction/v1/predictions` | Prediction `/v1/predictions` | Predicción CPU |

El Gateway enruta; no ejecuta PromQL, SQL, ETL ni inferencia. Timeout de conexión: 1 s; respuesta general: 6 s, Data Processing: 15 s, Prediction: 30 s. La ruta de predicción configura límite de cuerpo de 2 MB; exceso puede producir 413. No hay rutas comodín hacia microservicios.

## 5. Monitoring: catálogo, presente e histórico

### 5.1 GET `/api/v1/metrics/catalog`

Ruta pública: `/api/monitoring/v1/metrics/catalog`. No recibe parámetros. Devuelve una lista de definiciones con `id`, `group`, `resourceType`, `unit`, `aggregation`, `windowSeconds`, `description`, `denominator` y `seriesLabels`.

| Identificador de métrica | Unidad | Interpretación |
|---|---|---|
| `node.cpu.utilization` | ratio | Uso no-idle de CPU; multiplicar por 100 para porcentaje |
| `node.memory.used` | bytes | MemTotal menos MemAvailable |
| `node.network.receive` | bytes/s | Recepción por interfaz |
| `node.network.transmit` | bytes/s | Transmisión por interfaz |
| `node.filesystem.used` | bytes | Tamaño menos espacio libre por filesystem |

### 5.2 GET `/api/v1/metrics/current`

Ruta pública: `/api/monitoring/v1/metrics/current`.

| Parámetro | Obligatorio | Descripción |
|---|---|---|
| `metric` | Sí | Un identificador del catálogo |
| `resourceType` | No | `node` por defecto; es el tipo soportado |
| `cluster` | No | Identificador del clúster a filtrar |
| `resourceId` | No | Identificador de nodo, por ejemplo `HW001` |

Devuelve `metric`, `unit`, `aggregation`, `windowSeconds`, `start`, `end`, `stepSeconds`, `dataStatus` y `series`. Cada serie contiene `resource`, `labels`, `source`, `origin` y `samples`; cada muestra incluye `timestamp`, `value` y `quality`. El valor puede faltar: no debe interpretarse automáticamente como cero.

### 5.3 GET `/api/v1/metrics/history`

Ruta pública: `/api/monitoring/v1/metrics/history`. Usa los filtros anteriores y:

| Parámetro | Obligatorio | Regla |
|---|---|---|
| `start` | Sí | RFC3339 con zona y segundos enteros, por ejemplo `2026-10-22T12:00:00Z` |
| `end` | Sí | Posterior a start; rango máximo 24 horas |
| `stepSeconds` | No | Entero 15–3600; predeterminado 15 |

No acepta fracciones de segundo ni zona desconocida `-00:00` en estas consultas. Rechaza parámetros desconocidos, repetidos o vacíos. Límites adicionales: 100 series, 10 000 puntos totales y cuerpo acotado a 5 MiB. Consultar un catálogo permitido evita exponer PromQL libre al cliente.

Conserva procedencia `observed`, `simulated`, `estimated` o `unknown`. `source=prometheus` indica la fuente de consulta, no implica que el dato sea una medición física. El simulador produce `origin=simulated` y clústeres `sim-run-<uuid>`; no asumir que el filtro debe ser `sim-lab`.

### 5.4 Errores de Monitoring

Los errores contractuales usan `application/problem+json`. Consulta inválida: 400; límites excedidos: 422; respuesta inválida de fuente: 502; fuente no disponible: 503; timeout: 504. Consultar también 401/403 del Gateway. Una respuesta exitosa sin datos no equivale a fallo del servicio: revisar `dataStatus`.

## 6. Data Processing

### 6.1 GET `/api/v1/metrics/history`

Ruta pública: `/api/processing/v1/metrics/history`. Parámetros: `metric`, `start`, `end` obligatorios; `resourceType=node`, `cluster`, `resourceId` y `stepSeconds=15` opcionales. Paso de 15–3600 segundos; máximo 24 horas y fechas con zona explícita y segundos enteros.

Consulta Monitoring directamente y normaliza las series a registros. No lee Supabase para esta operación y no imputa huecos. Respuesta:

- `schemaVersion`, `metric`, `unit`, `aggregation`, `windowSeconds`.
- `period: {start, end}`, `stepSeconds`, `dataStatus`, `recordCount`, `warnings`.
- `records[]`: `metric`, `unit`, `aggregation`, `window_seconds`, `resource_type`, `cluster`, `resource_id`, `labels`, `timestamp`, `value`, `quality`, `origin`, `source`, `data_status`.

### 6.2 GET `/api/v1/historical-logs`

Ruta pública: `/api/processing/v1/historical-logs`.

| Parámetro | Obligatorio | Regla |
|---|---|---|
| `hardwareId` | Sí | Identificador de hardware de 1–20 caracteres |
| `start`, `end` | Sí | Fechas con zona; máximo 31 días; conserva fracciones en UTC |
| `limit` | No | Predeterminado 100; 1–500, sujeto al máximo configurado |
| `cursor` | No | Cursor de paginación; máximo 2048 caracteres |

Lee la tabla `logs` mediante la Data API de Supabase. Requiere `SUPABASE_ENABLED=true`, URL, API key y token de servidor configurados. El token del usuario no sustituye esas credenciales internas. `hardwareId` es un filtro, no una autorización por propietario.

Respuesta: `schemaVersion`, `hardwareId`, `period`, `units`, `dataStatus`, `recordCount`, `records`, `nextCursor`, `warnings`. Los registros incluyen `log_id`, `hardware_id`, `timestamp`, `cpu_utilization_pct`, `ram_utilization_pct`, `temperatura_celsius`, `energia_watts`, `origin=unknown`, `source=supabase` y `quality` por campo. Seguir `nextCursor` hasta finalizar la paginación; no fabricar cursores.

El nombre `energia_watts` se conserva por compatibilidad, pero W es una unidad de **potencia**, no de energía acumulada. La procedencia no se declara observed solo por estar almacenada en Supabase.

### 6.3 GET `/api/v1/prediction/dataset`

Ruta pública: `/api/processing/v1/prediction/dataset`.

Obligatorios: `start`, `end`, `cluster`, `resourceId`. Opcional: `stepSeconds` (15–3600, predeterminado 15). Usa las restricciones temporales del histórico de Monitoring. Identificadores cluster/resourceId: patrón `^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$`.

Prepara CPU de **un recurso**, convirtiendo ratio a porcentaje. Excluye muestras missing/non_finite, no mezcla orígenes ni rellena huecos. Devuelve `schemaVersion=1.0`, `contractStatus=provisional`, `datasetId`, `requestedPeriod`, `period`, `resource`, `features`, `units`, `origins`, `dataStatus`, `excludedSampleCount` y `warnings`.

Cada feature contiene `timestamp`, `cpu_utilization` (0–100), `origin` y `quality=ok`. **Preparar el dataset no ejecuta inferencia:** hay que enviar posteriormente el JSON a Prediction y respetar su frecuencia/ventana requeridas.

### 6.4 Errores de Data Processing

422 consulta inválida/límites; 502 respuesta upstream inválida; 503 fuente ausente, sin permisos o no disponible; 504 timeout; 500 error interno. Formato `application/problem+json` con `type`, `title`, `status`, `detail`, `instance`, `code`, `requestId`; encabezado `X-Request-Id`.

## 7. Prediction

### 7.1 POST `/v1/predictions`

Ruta pública: `/api/prediction/v1/predictions`. También existe el alias interno POST `/predict`, que **no está publicado** en el Gateway.

Recibe un objeto JSON con una ventana temporal, no un simple valor CPU. El contrato recomendado incluye:

| Campo | Contenido |
|---|---|
| `schemaVersion` | `1.0` |
| `datasetId` | Identificador del dataset |
| `period` | Objeto start/end |
| `resource` | Objeto type/cluster/id |
| `features` | Lista temporal con timestamp, cpu_utilization, origin y quality |
| `origins` | Procedencias presentes |
| `dataStatus` | Estado del dataset |
| `units`, `warnings` | Metadatos complementarios |

El JSON Schema describe el contrato recomendado, pero la ruta está tipada como diccionario y el adaptador ejecuta validaciones propias; no asumir que FastAPI valida automáticamente ese archivo JSON Schema. La serie debe tener suficientes datos y frecuencia compatible con el modelo; una ventana mínima inventada no garantiza una inferencia válida.

Usa el modelo seleccionado y su preprocesamiento. No consulta Prometheus, Supabase ni Kubernetes. El horizonte se obtiene del artefacto/configuración; no existe un query parameter público para elegirlo libremente. La configuración contempla 5m, 15m y 30m; el valor predeterminado del proyecto es 15m.

Respuesta contractual: `predictionId`, `resource`, `target=cpu_utilization`, `predictedFor`, `generatedAt`, `value`, `unit=%`, `horizon`, `modelVersion`, `inputDatasetId`, `origin=estimated`. Puede incluir metadatos adicionales. Es una estimación, no una orden de escalamiento.

### 7.2 Errores de Prediction

| HTTP | Código/comportamiento |
|---|---|
| 400 | `INVALID_INPUT` u otro error de dominio ML |
| 422 | `INVALID_DATASET`; FastAPI también puede rechazar un cuerpo inválido |
| 503 | `MODEL_UNAVAILABLE`: modelo ausente o integridad inválida |
| 500 | `INFERENCE_ERROR` |

Los errores ML tienen forma `{ "code": "...", "message": "...", "details": {} }`. **No comparten exactamente el formato problem+json** de Monitoring/Data Processing. Los errores automáticos de validación FastAPI pueden tener `detail`.

## 8. Salud, documentación y métricas internas

| Servicio | Método y ruta | Descripción / acceso |
|---|---|---|
| Gateway | GET `/actuator/health` | Salud; permitido sin JWT |
| Gateway | GET `/actuator/health/liveness` | Liveness, permitido sin JWT |
| Gateway | GET `/actuator/health/readiness` | Readiness, permitido sin JWT |
| Gateway | GET `/openapi/gateway-v0.1.yaml` | Contrato estático, permitido sin JWT; contrastar con código actual |
| Gateway | GET `/actuator/info` | Expuesto por Actuator, pero denegado por la seguridad actual |
| Gateway | GET `/actuator/prometheus` | Expuesto por Actuator, pero denegado por la seguridad actual |
| Monitoring | GET `/actuator/health` | Salud interna |
| Monitoring | GET `/actuator/health/liveness` | Proceso vivo |
| Monitoring | GET `/actuator/health/readiness` | Disponibilidad de la aplicación según indicadores configurados |
| Monitoring | GET `/actuator/prometheus` | Métricas JVM/HTTP/proceso; scrape de Prometheus |
| Monitoring | GET `/openapi/monitoring-v0.1.json` | Contrato estático |
| Data Processing | GET `/` | Nombre, versión y enlace `/docs` |
| Data Processing | GET `/api/v1/health` | Estado healthy; no prueba por sí solo acceso a Supabase |
| Data Processing | GET `/docs` | Swagger UI automática |
| Data Processing | GET `/redoc` | ReDoc automática |
| Data Processing | GET `/openapi.json` | Esquema OpenAPI generado |
| Data Processing | GET `/docs/oauth2-redirect` | Ruta auxiliar de Swagger UI; no es login del proyecto |
| Prediction | GET `/health` | Modelo cargado o degraded; degraded puede responder HTTP 200 |
| Prediction | GET `/health/live` | Estado live |
| Prediction | GET `/health/ready` | Verifica presencia/integridad del modelo; puede devolver 503 |
| Prediction | GET `/docs` | Swagger UI automática |
| Prediction | GET `/redoc` | ReDoc automática |
| Prediction | GET `/openapi.json` | OpenAPI generado; cuerpo de predicción genérico |
| Prediction | GET `/docs/oauth2-redirect` | Auxiliar Swagger UI |
| Simulator | GET `/metrics` | Exposición Prometheus; no es una API JSON de simulación |

Las rutas automáticas de documentación FastAPI derivan de su configuración por defecto. Los prefijos `/actuator` también pueden ofrecer enlaces de descubrimiento según configuración/seguridad; no se consideran operaciones de negocio. Salud UP no demuestra precisión predictiva ni que todas las dependencias externas estén operativas.

Simulator se controla con CLI `run`, no mediante endpoints REST de iniciar/parar. El puerto lo fija `--port`; el Dockerfile aislado usa 9090, mientras que Compose lo cambia a 8000. Exporta CPU, memoria, red y filesystem con etiquetas de procedencia simulada.

## 9. Servicios externos y herramientas de observabilidad

Estas rutas pertenecen a productos externos, no a controladores propios. Se listan las utilizadas/identificadas en la integración, no toda la API de esos productos.

| Servicio | Ruta / operación | Uso |
|---|---|---|
| Prometheus | GET `/metrics` | Métricas del propio proceso |
| Prometheus | GET `/api/v1/query` | Consulta instantánea; query PromQL |
| Prometheus | GET `/api/v1/query_range` | Consulta temporal; query, start, end, step |
| Prometheus | GET `/api/v1/targets` | Targets de scrape y su salud |
| Prometheus | GET `/targets` | Interfaz web de targets, no endpoint de negocio |
| Grafana | GET `/d/green-ai-live` | Página del dashboard provisionado; no endpoint JSON de Green AI |
| Supabase | GET `/auth/v1/.well-known/jwks.json` | Claves públicas para validar JWT en Gateway |
| Supabase | GET `/rest/v1/logs` | Lectura por Data Processing con credenciales de servidor |
| Supabase SDK | `auth.signInWithPassword`, `auth.signUp`, `auth.signOut` | Inicio de sesión, registro y cierre de sesión externos |

El frontend actual usa el SDK de Supabase Auth. No se inventa una API propia de autenticación a partir de esas llamadas. Las credenciales de servidor de históricos nunca deben enviarse al navegador. Grafana consulta Prometheus directamente; no pasa por el Gateway.

## 10. Ejemplos de consumo

Ejemplos para Bash o una herramienta HTTP equivalente. En Windows usar `curl.exe` y adaptar saltos de línea, o importar los ejemplos a Postman. Sustituir token, fechas y clúster por valores válidos con muestras disponibles. Las fechas siguientes solo ilustran el formato.

```bash
BASE="http://127.0.0.1:8081"
TOKEN="<access-token>"

curl "$BASE/api/monitoring/v1/metrics/catalog" \
  -H "Authorization: Bearer $TOKEN"

curl --get "$BASE/api/monitoring/v1/metrics/current" \
  -H "Authorization: Bearer $TOKEN" \
  --data-urlencode "metric=node.cpu.utilization" \
  --data-urlencode "resourceId=HW001"

curl --get "$BASE/api/monitoring/v1/metrics/history" \
  -H "Authorization: Bearer $TOKEN" \
  --data-urlencode "metric=node.cpu.utilization" \
  --data-urlencode "resourceId=HW001" \
  --data-urlencode "start=2026-10-22T12:00:00Z" \
  --data-urlencode "end=2026-10-22T12:30:00Z" \
  --data-urlencode "stepSeconds=60"

# Histórico normalizado: mismos parámetros temporales y de métrica.
curl --get "$BASE/api/processing/v1/metrics/history" \
  -H "Authorization: Bearer $TOKEN" \
  --data-urlencode "metric=node.cpu.utilization" \
  --data-urlencode "resourceId=HW001" \
  --data-urlencode "start=2026-10-22T12:00:00Z" \
  --data-urlencode "end=2026-10-22T12:30:00Z"

curl --get "$BASE/api/processing/v1/historical-logs" \
  -H "Authorization: Bearer $TOKEN" \
  --data-urlencode "hardwareId=HW001" \
  --data-urlencode "start=2026-10-22T00:00:00Z" \
  --data-urlencode "end=2026-10-22T01:00:00Z" \
  --data-urlencode "limit=100"

# Usar el cluster real obtenido de Monitoring. Revisar respuesta antes de inferir.
curl --fail-with-body --get "$BASE/api/processing/v1/prediction/dataset" \
  -H "Authorization: Bearer $TOKEN" \
  --data-urlencode "cluster=sim-run-<uuid>" \
  --data-urlencode "resourceId=HW001" \
  --data-urlencode "start=2026-10-22T12:00:00Z" \
  --data-urlencode "end=2026-10-22T13:00:00Z" \
  --data-urlencode "stepSeconds=60" -o dataset.json

# Ejecutar solo si dataset.json contiene una ventana válida y compatible.
curl "$BASE/api/prediction/v1/predictions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: exposicion-001" \
  --data-binary @dataset.json
```

El intervalo/paso del ejemplo no garantiza compatibilidad con cualquier artefacto del predictor; comprobar frecuencia y cantidad de muestras del modelo seleccionado.

## 11. Endpoints del backend anterior GreenAi_TPI

Encontrados en `GreenAi_TPI/Backend/server.js` (Express). **No están publicados por el Gateway ni incluidos en el Compose raíz/portable actual.** Puerto predeterminado 3001: entraría en conflicto con el frontend actual si se arrancan ambos en el mismo puerto.

| Método | Ruta | Entrada | Respuesta / comportamiento |
|---|---|---|---|
| GET | `/api/health` | Ninguna | `{status, port, db}`; db indica cliente configurado, no una consulta exitosa |
| POST | `/api/registro` | JSON nombre_completo, email, password; rol opcional | 201 `{status, data}`; inserta usuario |
| POST | `/api/login` | JSON email, password | 200 `{status, usuario}`; no emite JWT |
| GET | `/api/kpis` | Ninguna | nodosActivos, totalWatts, cpuAvg, ramAvg; promedios de los últimos 10 logs |
| GET | `/api/usuarios` | Ninguna | Array de filas de usuario, selección de todas las columnas |
| GET | `/api/hardware` | Ninguna | Array de hardware con nombre del usuario relacionado |
| GET | `/api/logs` | Ninguna | Últimos 20 logs con hostname relacionado |

Errores: 503 si Supabase no está configurado; 500 ante fallos de consultas. Registro/login agregan 400 por campos faltantes; login devuelve 401 si el usuario no existe o la contraseña no coincide. Los mensajes pueden usar `detail` o `error` según ruta.

**Limitaciones concretas de este código:** no se observa middleware de autorización en estas rutas; compara/almacena contraseñas en texto y construye un pseudo-hash; usuarios selecciona todas las columnas. No debe presentarse como el mecanismo seguro actual ni publicarse sin corregir esas funciones. `totalWatts` calcula un promedio, a pesar de su nombre.

También existe `GreenAi_TPI/Backend/main.py` con POST `/api/registro`, campos nombre_completo, email, password y rol por defecto OPERADOR. El archivo referencia `app` y `supabase` sin definirlos, por lo que **no es una aplicación ejecutable por sí sola**. Se registra como fragmento encontrado, no como servicio disponible.

`GreenAi_TPI/exporter/exporter.py` expone GET `/metrics` en puerto 8000 cuando se ejecuta. Consulta PostgreSQL cada 15 s y publica `greenai_cpu_utilization_pct`, `greenai_ram_utilization_pct`, `greenai_temperatura_celsius` y `greenai_energia_watts`. Es un exporter distinto al simulador y no forma parte del paquete portable actual. Su conversión de nulos a cero limita la interpretación de ausencia de datos.

## 12. Qué no se encontró como API propia activa

No se encontraron rutas activas de CRUD de hardware/usuarios en el Gateway actual, ni rutas de entrenamiento, inicio/parada del simulador, ejecución de escalamiento Kubernetes, exportación de reportes PDF o control energético. La existencia de esos conceptos en documentos de planificación no implica un endpoint implementado.

Las páginas HTML del frontend y recursos CSS/JS son archivos servidos por Nginx, no operaciones REST. No se inventarían rutas de microservicios a partir de botones o títulos de la interfaz.

## 13. Fuentes y mantenimiento

Fuentes locales revisadas (rutas relativas al workspace para poder trasladar este documento):

- `docker-compose.yml` y `output/green-ai-portable/compose.yaml`.
- `green-ai-gateway/src/main/resources/application.yaml`.
- `green-ai-gateway/src/main/java/pe/edu/continental/greenai/gateway/SecurityConfiguration.java`.
- `green-ai-gateway/src/main/resources/static/openapi/gateway-v0.1.yaml` (contrato estático disponible).
- `green-ai-monitoring/src/main/java/pe/edu/continental/greenai/monitoring/adapter/in/web/MetricsController.java`, `QueryParameters.java` y dominio `MetricQuery.java`.
- `green-ai-monitoring/src/main/resources/static/openapi/monitoring-v0.1.json`.
- `green-ai-data-processing/Green-IA/data-processing-service/main.py`, `infrastructure/adapters/input/api/routes.py` y `models.py`.
- `green-ai-data-processing/Green-IA/data-processing-service/contracts/data-processing-v1.openapi.json`.
- `green-ai-prediction/green-ai-project-docs/src/service/app.py`, `src/inference/predict.py` y `contracts/*.schema.json`.
- `green-ai-simulator/src/green_ai_simulator/application/runner.py` y adaptador Prometheus.
- `green-ai-front-end/Frontend-GreenAi/app.js`.
- `GreenAi_TPI/Backend/server.js`, `main.py` y `GreenAi_TPI/exporter/exporter.py`.

Ante diferencias entre contratos estáticos y rutas/seguridad actuales, contrastar con el código y la configuración ejecutada. Actualizar esta documentación cuando cambien parámetros, roles, prefijos o modelos de respuesta. No incluir tokens, contraseñas ni secretos en ejemplos de la memoria académica.

