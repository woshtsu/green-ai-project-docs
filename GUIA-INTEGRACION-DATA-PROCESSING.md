# Data Processing: guía de implementación e integración

Fecha: 2026-09-24. Revisión de `GDianaBarrera/Green-IA`, rama `feature/data-processing-integration`, commit `c4438b7`. Esta guía describe trabajo pendiente; no certifica ejecución ni modifica el servicio. Los nombres nuevos indicados como propuestas deben incorporarse al OpenAPI antes de conectar consumidores.

Referencias: [ensamblaje](ENSAMBLAJE-MICROSERVICIOS.md), [modelo de datos verificado](modelo-bd.md), [autenticación](AUTENTICACION-JWT.md).

## Objetivo de esta entrega

Completar la consulta y preparación de datos desde Monitoring y la lectura autorizada de históricos de Supabase. El equipo puede terminar y demostrar estas capacidades sin esperar a Prediction. No implementar modelos predictivos, recomendaciones, SLA ni generación de potencia desde CPU.

Flujos a entregar:

```text
Cliente autorizado → Gateway → Data Processing → Monitoring → Prometheus
                             → Data Processing → históricos de Supabase
```

La segunda línea representa otra fuente de Data Processing. No implica que Monitoring lea Supabase. El navegador usa Supabase Auth para sesión y Gateway para operaciones; no consulta tablas directamente.

## 1. Partir de lo ya implementado

La rama contiene:

- `MonitoringHttpAdapter`: consulta `/api/v1/metrics/history` con filtros y timeout.
- `ProcessMetricsUseCase`: transforma las series en filas, conserva labels, procedencia y calidad; usa DataFrames internamente.
- `GET /api/v1/metrics/history`: publica las filas como JSON.
- `PreparePredictionDatasetUseCase`: prepara CPU de un recurso, convierte ratio a porcentaje y excluye muestras no utilizables. Actualmente no está conectado a la API.
- Dockerfile y pruebas del adaptador y de los casos de uso.

No rehacer el ETL de Excel ni sustituir los puertos existentes. Añadir los adaptadores y contratos necesarios en cambios separados. Antes de empezar, ejecutar las pruebas existentes con las dependencias del proyecto y guardar el resultado como línea base.

## 2. Corregir y validar las fechas antes de consultar Monitoring

Archivo principal: `infrastructure/adapters/input/monitoring_http_adapter.py`. Hoy utiliza `start.isoformat()` y `end.isoformat()` directamente. FastAPI admite objetos datetime que pueden carecer de zona o tener microsegundos. Monitoring los rechaza.

Pasos:

1. Validar zona explícita en ambos parámetros. Rechazar fechas sin zona; no asumir silenciosamente que son UTC.
2. Convertir a UTC.
3. Adoptar una política explícita para fracciones. Para esta API se recomienda rechazarlas con un error claro. El Frontend ya genera segundos enteros. Si se decide truncar, documentar y devolver el periodo efectivo, y validar nuevamente el intervalo.
4. Validar `start < end`, `end <= ahora`, rango de como máximo 24 horas y `stepSeconds` entre 15 y 3600, con valor predeterminado 15.
5. Serializar sin fracciones y con `Z` o un offset conocido.

Ejemplo orientativo de serialización estricta:

```python
from datetime import timezone

def monitoring_timestamp(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("La fecha debe incluir zona horaria")
    if value.microsecond:
        raise ValueError("La fecha debe utilizar segundos enteros")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
```

Ejemplo válido: `2026-09-24T04:30:00Z`. Ejemplos inválidos: `2026-09-24T04:30:00` y `2026-09-24T04:30:00.123Z`.

Monitoring limita además a 100 series y 10 000 puntos totales. Calcular los puntos por serie como `floor((end-start)/stepSeconds)+1`, pero no asumir que ese cálculo conoce cuántas series devolverá la fuente. Conservar y explicar los rechazos de límites del upstream; aconsejar filtrar por clúster/nodo o aumentar el paso. No aumentar automáticamente la ventana ni cambiar el filtro del usuario.

**Aceptación:** zona UTC y offsets válidos funcionan; fecha sin zona, fracciones, rango invertido, futuro y paso fuera de límites tienen errores documentados. Una consulta inválida no debe presentarse como caída de Monitoring.

## 3. Conservar el contrato y la semántica de Monitoring

Archivos: `process_metrics.py`, `routes.py` y modelos de respuesta que se incorporen.

Actualmente la respuesta pública solo conserva `metric`, `dataStatus`, `recordCount` y `records`. Añadir un modelo explícito que conserve también unidad, agregación, ventana, periodo, paso y advertencias de la respuesta original. Publicar el formato en OpenAPI; no exigir al consumidor reconstruir metadatos a partir de la primera fila, porque puede no haber filas.

Requisitos:

- Mantener `value=0` cuando `quality=valid`.
- Mantener ausentes los valores `missing` y `non_finite`; JSON debe contener `null`, nunca NaN/Infinity ni cero de sustitución.
- Validar la respuesta upstream antes de convertirla. Un diccionario cualquiera no garantiza un contrato válido. Detectar campos requeridos ausentes, tipos incorrectos y valores no finitos contradictorios con la calidad.
- Preservar `resource.type`, `cluster`, `resource.id`, `labels`, `source` y `origin`. Dos interfaces o filesystems no son una sola serie aunque pertenezcan al mismo nodo.
- No hacer medias ni sumar series de clústeres diferentes por defecto.
- Mantener UTC en la API. El Frontend decide la zona de presentación.
- Evitar `errors="coerce"` sin informar la pérdida: un timestamp inválido no debe convertirse silenciosamente en NaT y salir como una muestra normal.
- Conservar `warnings` de Monitoring y añadir advertencias propias cuando se excluyan muestras. No devolver siempre una lista vacía.
- Ausencia de muestras es un resultado documentado, no un fallo de conectividad. Definir `no_data`, lista vacía y contador cero cuando corresponda; conservar `partial` cuando la fuente advierta cobertura incompleta.

Antes de preparar datasets, documentar las políticas de duplicados, orden, huecos y muestreo. Primera entrega recomendada: ordenar dentro de cada serie, conservar huecos y no imputar. Si se detectan duplicados contradictorios, rechazar o señalarlos explícitamente; no elegir uno arbitrariamente.

**Aceptación:** ejemplos con cero, null, múltiples nodos, dos interfaces, advertencias y respuesta vacía conservan sus significados después de la conversión a JSON.

## 4. Errores, configuración y trazabilidad

`MonitoringHttpAdapter` distingue algunos fallos HTTP, pero las rutas convierten cualquier `ValueError` en 400 y cualquier `RuntimeError` en 503. Un JSON roto puede terminar clasificado como error del usuario.

1. Separar errores de entrada, respuesta upstream inválida, timeout y fuente indisponible con excepciones propias o una clasificación equivalente.
2. Publicar la correspondencia HTTP: validación 400/422 (elegir y documentar), respuesta upstream inválida 502, timeout 504, indisponibilidad 503. No reenviar texto upstream sin revisar: puede contener detalles internos.
3. Propagar `X-Request-Id` hacia Monitoring y devolverlo al cliente. Si no llega, generar uno; validar longitud/formato del recibido. Nunca registrar bearer tokens, contraseñas ni cadenas de conexión.
4. Validar configuración al arrancar: URL de Monitoring, timeout positivo, límites y configuración de Supabase cuando esa fuente esté habilitada. Actualmente la conversión de timeout se realiza por petición y fuera del bloque de manejo de errores.
5. Configurar `MONITORING_BASE_URL=http://monitoring:8080` en Docker. `localhost` dentro del contenedor apunta al propio Data Processing.
6. Permitir que un fallo temporal de una fuente no impida usar la otra. No hacer fallback de Monitoring a Supabase: son históricos distintos.

**Aceptación:** cada fallo tiene un código estable, mensaje seguro y correlación; el servicio no oculta un fallo con datos vacíos ni con fixtures.

## 5. Implementar la lectura de Supabase con alcance mínimo

El esquema está documentado en `modelo-bd.md`. No pedir crear de nuevo las tablas. La evidencia es una instantánea: el responsable de Supabase debe confirmar que las columnas y permisos siguen vigentes.

### 5.1 Acordar acceso con el responsable de Supabase

Solicitar:

- Un acceso de servidor dedicado, de solo lectura a las columnas necesarias de `logs` y, si hace falta, `hardware`.
- Confirmación de permisos efectivos y políticas RLS. La instantánea documentada tenía políticas permisivas; no considerar que activar RLS basta para limitar acceso.
- Medio de conexión aprobado: PostgreSQL con consultas parametrizadas, o Data API mediante un adaptador y permisos revisados. Escoger uno para la primera entrega.
- Secretos entregados mediante variables locales/gestor de secretos, nunca commits, capturas ni documentos compartidos. Una publishable key por sí sola no demuestra permiso de lectura. No resolver un error de permisos abriendo todas las tablas al público.
- Procedencia de los históricos y correspondencia entre `hardware_id` y la identidad de los nodos. El esquema no contiene clúster ni origen.

No consultar `usuario.password`, `password_hash`, ni reutilizar esas columnas para login. La autenticación ya corresponde a Supabase Auth.

### 5.2 Añadir un puerto y un adaptador

Propuesta: un puerto `HistoricalLogsSource` con una operación de lectura por `hardware_id`, periodo y cursor. Implementar `SupabaseHistoricalLogsAdapter` o un nombre equivalente según el transporte elegido. Mantener las reglas de unidades y calidad en el caso de uso, fuera del SQL/cliente HTTP.

Leer columnas explícitas, sin `SELECT *`. Primera selección posible: `log_id`, `hardware_id`, `timestamp`, `cpu_utilization_pct`, `ram_utilization_pct`, `temperatura_celsius`, `energia_watts`. Incorporar otros campos solo cuando haya una necesidad y contrato definidos.

Aplicar filtros y paginación en la fuente. Orden estable por `(timestamp, log_id)`; el timestamp solo puede repetirse. Definir un máximo de filas/páginas y un timeout. Nunca cargar toda `logs` y filtrar después con Pandas.

Para una consulta completa paginada, fijar el intervalo al inicio y avanzar por cursor compuesto para no duplicar filas en los límites. Si se alcanza un límite propio, devolver cursor/advertencia o un error documentado; no declarar `complete` sobre un resultado truncado. Aprovechar los índices existentes por hardware y timestamp; cualquier índice nuevo requiere medir y coordinarlo con el responsable de BD.

### 5.3 Respetar unidades e identidad

| Campo | Tratamiento requerido |
| --- | --- |
| `cpu_utilization_pct` | Ya es porcentaje. No multiplicar otra vez por 100. Compararlo con CPU de Monitoring solo después de confirmar ventana y definición. |
| `ram_utilization_pct` | Porcentaje, distinto de `node.memory.used` en bytes. No intercambiarlos. |
| `energia_watts` | Potencia en W pese al nombre. No presentarlo como Wh/kWh. |
| `prediccion_watts` | Predicción histórica; no tratarla como medición ni como etiqueta de entrenamiento sin evaluar su origen y posible fuga de información. |
| `hardware_id` | Identidad SQL; usar un mapeo explícito hacia recursos de Monitoring. No adivinar a partir del hostname. |
| `timestamp` | Normalizar a UTC; conservar precisión de la fuente según el contrato de históricos. La restricción de segundos enteros de Monitoring no obliga a perder precisión de Supabase. |

No asignar `observed` solo porque el dato venga de Supabase. Si la procedencia no está confirmada, declararla desconocida y advertirlo. No asignar el clúster `sim-run-*` a registros históricos sin evidencia. No mezclar ambas fuentes hasta acordar equivalencia de identidad, tiempos y unidades.

En esta entrega el adaptador es de lectura: no inserta simulaciones, predicciones, usuarios ni recomendaciones, y no cambia el esquema.

**Aceptación:** consulta acotada y paginada, cero filas válido, credenciales ausentes, permisos denegados y timeout distinguibles; sin contraseñas en respuestas; sin escrituras.

## 6. Publicar la API para poder probar sin Prediction

Conservar el endpoint existente de Monitoring procesado. Proponer y documentar otro endpoint, por ejemplo `GET /api/v1/historical-logs`, para Supabase. No activar una selección de fuente implícita según cuál esté disponible.

Para cada operación, añadir modelos de parámetros y respuesta, ejemplo real anonimizado, unidades, calidad, límites, paginación y errores al OpenAPI de FastAPI. Exportar una copia versionada del OpenAPI al repositorio para revisión del Gateway.

No hace falta conectar `PreparePredictionDatasetUseCase` para demostrar las dos lecturas. Puede mantenerse probado internamente con fixtures. Si se publica una operación para obtener un dataset preparado, declararla como contrato provisional, documentar muestras excluidas, periodo solicitado frente al efectivo y versión; no presentarla como inferencia ni simular una respuesta de Prediction.

Quedan pendientes del equipo Prediction: aceptación del esquema final, mínimo de muestras, cadencia, horizonte, endpoint y política de datos mixtos. No bloquear las fases anteriores por estas decisiones.

## 7. Coordinar Gateway y Docker

Entregable del compañero: OpenAPI estable, Dockerfile funcional, variables de ejemplo sin secretos y evidencia de prueba HTTP. Con eso, el responsable del Gateway podrá añadir rutas explícitas:

```text
/api/processing/v1/metrics/history → /api/v1/metrics/history
/api/processing/v1/historical-logs → /api/v1/historical-logs (propuesta)
```

No basta con modificar YAML: la configuración de seguridad actual permite las rutas de Monitoring explícitamente; las nuevas requieren autorización y pruebas correspondientes. Gateway valida JWT de Supabase y roles `OPERATOR`/`ADMIN`. No crear login ni JWT propios en Data Processing. No usar la clave de Supabase del servidor como token del usuario.

En el MVP, Data Processing queda en red privada y consulta Monitoring directamente. Cualquier autorización por hardware/usuario debe acordarse e implementarse antes de ofrecer aislamiento por usuario; un filtro `hardware_id` no es una comprobación de permisos.

Añadir Data Processing al Compose de integración cuando su imagen esté comprobada. Puede escuchar en 8000 dentro de su contenedor aunque Simulator también use 8000 internamente; evitar publicar ambos en el mismo puerto del host. El navegador utiliza Gateway. Mantener CORS allí.

El Dockerfile actual usa Python 3.14. Comprobar que las versiones fijadas de dependencias se instalen y funcionen en esa imagen; no afirmar portabilidad basándose solo en el entorno local. Las variables `DATA_PROCESSING_HOST` y `DATA_PROCESSING_PORT` del ejemplo no controlan el CMD actual, que fija host/puerto: documentar los valores fijos o implementar su uso.

## 8. Secuencia de pruebas y entrega

1. Ejecutar la suite actual antes y después de cada cambio funcional.
2. Añadir casos de fechas/límites y respuestas upstream inválidas.
3. Probar transformación con múltiples series, cero, null, advertencias, duplicados y ausencia de datos.
4. Probar Supabase mediante dobles del adaptador: paginación, mismo timestamp con distintos IDs, fallo a mitad de lectura, permisos y timeout. Después hacer una lectura real acotada con credenciales autorizadas.
5. Ejecutar Data Processing en contenedor y consultar un intervalo reciente conocido de Monitoring. Comparar valores, unidad, origen e identidad con la respuesta original; no basta con recibir 200.
6. Probar las rutas publicadas por Gateway con sesión real: sin token 401, token válido y rol autorizado éxito, rol insuficiente 403. No adjuntar el token como evidencia.
7. Detener temporalmente una fuente en un entorno de prueba propio y comprobar el error esperado. No detener servicios compartidos sin coordinarlo.

Prueba manual orientativa dentro de la red Docker, usando fechas recientes en segundos enteros:

```text
GET http://data-processing:8000/api/v1/metrics/history?metric=node.cpu.utilization&resourceType=node&start=<UTC_INICIO>&end=<UTC_FIN>&stepSeconds=15
```

El nombre `data-processing` debe coincidir con el servicio definido en Compose. Los marcadores de fecha se sustituyen; no son valores literales.

Actualizar README con: arranque local y Docker, variables obligatorias/opcionales, contratos, ejemplos, política de limpieza, límites, tabla de errores y funciones pendientes. Entregar commits pequeños: fechas/errores; contrato/metadatos; Supabase; documentación/evidencias. No incluir `.env`, datasets sensibles ni tokens.

## Checklist de cierre para el compañero

- [ ] Fechas y límites compatibles con Monitoring.
- [ ] JSON estable con metadatos, identidad, procedencia, calidad y warnings.
- [ ] Ningún NaN/Infinity ni cero artificial en respuestas.
- [ ] Errores clasificados y correlación de peticiones.
- [ ] Adaptador Supabase de lectura, permisos confirmados y paginación acotada.
- [ ] Fuentes y unidades separadas; mapeos pendientes explícitos.
- [ ] OpenAPI y README actualizados.
- [ ] Imagen Docker y lectura real verificadas.
- [ ] Rutas y autorización coordinadas con Gateway.
- [ ] Prediction identificado como pendiente, sin resultados inventados.

Al cerrar estas tareas, Data Processing podrá integrarse y probarse de forma independiente; no significará que el sistema predictivo completo esté terminado.
