# Revisión del avance de Prediction — rama `Criss`

Fecha de revisión: 2026-09-23. Fuente revisada: rama [`Criss`](https://github.com/woshtsu/green-ai-project-docs/tree/Criss), commit `75f0b8602c0ea326c282cf2d1cf06c7955898cbf` (`ML`).

## Alcance observado

El avance implementa un núcleo experimental de Machine Learning para pronosticar utilización de CPU a 5, 15 y 30 minutos. Incluye carga y validación de un dataset JSON, limpieza sin convertir ausencias en cero, features temporales, lags y ventanas móviles, división cronológica, baselines de persistencia/promedio móvil, Random Forest, XGBoost, métricas, selección, serialización con joblib, integración local con MLflow, inferencia fuera de línea, detección básica de drift y 48 pruebas declaradas.

Mantiene correctamente los límites actuales: no consulta Prometheus, Supabase ni Kubernetes; distingue resultados simulados de observaciones; no presenta CPU como energía; y deja FastAPI fuera del núcleo ML. El `compileall` de `src`, `scripts` y `tests` terminó correctamente durante esta revisión.

Las cifras publicadas en el README proceden del fixture sintético `dataset-sim-001`. No son precisión sobre datos reales ni evidencia de ahorro energético. Los artefactos generados (`model.joblib`, métricas, gráficas y `mlruns`) están ignorados y no están presentes en la rama, por lo que las cifras y el run de MLflow no pudieron contrastarse desde el commit. La suite no se ejecutó en esta revisión porque el entorno no tenía instaladas sus dependencias (`pytest` ausente); esto no equivale a un fallo de las pruebas.

## Hallazgos que deben cerrarse antes de validar el modelo

### P0 — Separación experimental y selección

El pipeline construye `TRAIN | VALIDATION | TEST`, concatena TRAIN y VALIDATION para ajustar todos los modelos y después compara y selecciona el ganador con métricas del TEST. Esto usa el conjunto de prueba como conjunto de selección y deja sin una evaluación final independiente.

Corrección requerida:

1. ajustar candidatos e hiperparámetros con TRAIN;
2. escoger modelo e hiperparámetros con VALIDATION o validación temporal walk-forward;
3. reentrenar con TRAIN + VALIDATION solo después de seleccionar;
4. evaluar una única vez sobre TEST sin utilizarlo para cambiar el modelo;
5. guardar por separado métricas de validación y prueba.

Además, debe purgarse en cada frontera al menos el horizonte pronosticado. Hoy un registro al final de TRAIN puede tener como target un valor cuyo timestamp ya pertenece al periodo de VALIDATION, y lo mismo puede ocurrir entre VALIDATION y TEST. La prueba debe demostrar que `max(target_time de la partición anterior) < min(feature_time de la partición siguiente)`.

### P0 — Prueba anti-leakage efectiva

`tests/unit/test_anti_leakage.py` contiene dos expresiones terminadas en `or True`; esas aserciones pasan aunque la relación comprobada sea falsa. La protección productiva también se basa principalmente en nombres como `future`, `lead` o `target`, no en la procedencia temporal real de cada feature.

Debe eliminarse `or True` y probarse explícitamente, para cada fila y feature, que `feature_timestamp <= prediction_time` y que `target_timestamp = prediction_time + horizon`. La prueba también debe cubrir las fronteras de partición y una columna futura con nombre aparentemente inocente.

### P0 — Contrato Data Processing → Prediction

El código espera `features` como una lista de registros temporales con `timestamp`, `cpu_utilization`, `origin` y `quality`. El ejemplo actualmente publicado en `ENSAMBLAJE-MICROSERVICIOS.md` muestra objetos `name/value/unit`; los formatos no son compatibles. Tampoco están fijadas las unidades de `memory_utilization`, `network_in`, `network_out`, `cpu_requests` y `memory_requests`.

Data Processing y Prediction deben publicar una única versión mediante JSON Schema u OpenAPI. Debe definir:

- granularidad: un recurso por dataset o múltiples recursos;
- nombre, tipo y unidad de cada columna;
- frecuencia esperada, tolerancia de huecos y ventanas mínimas por horizonte;
- vocabularios compartidos de `origin`, `quality` y `dataStatus`;
- reglas de conversión: Monitoring entrega CPU como ratio y memoria en bytes, mientras el modelo usa CPU y memoria como porcentajes;
- tratamiento de varias procedencias. El validador actual permite registros de orígenes distintos si todos están declarados, aunque el README dice que no deben mezclarse sin una operación explícita;
- compatibilidad y rechazo de versiones de esquema desconocidas. El código declara `SCHEMA_VERSION = "1.0"`, pero no rechaza expresamente otra versión.

Hasta acordar ese contrato, el fixture es útil para pruebas técnicas, pero no demuestra integración con Data Processing.

## Faltantes del Prediction Service

El repositorio implementa el núcleo ML, no el microservicio. Para incorporarlo al flujo del sistema faltan:

- API interna versionada y OpenAPI, con operación de predicción, esquema de errores, `X-Request-Id`, límites de tamaño/tiempo y validación estricta;
- respuesta completa con `predictionId`, `resource`, `predictedFor`, `generatedAt`, `modelVersion`, `inputDatasetId`, horizonte, valor, unidad y `origin=estimated`; la función actual puede devolver `resource` y `predictedFor` como `null` y no genera `predictionId` ni `generatedAt`;
- contrato de entrada que reciba una ventana temporal y ejecute el mismo preprocesamiento del entrenamiento. Actualmente el llamador debe construir y ordenar manualmente las 23 features del modelo, lo que puede producir training-serving skew;
- endpoints de liveness/readiness. Readiness debe comprobar que el artefacto y sus metadatos son compatibles, sin afirmar que el modelo es preciso;
- Dockerfile reproducible, usuario sin privilegios, configuración externa y límites de recursos;
- integración con Gateway/Decision según las rutas que se acuerden. Prediction no debe consultar Prometheus ni Supabase ni recibir llamadas directas del Frontend;
- política de concurrencia, timeout y comportamiento cuando falten datos, el modelo no exista o la versión sea incompatible.

## Reproducibilidad, evidencia y operación

Antes de presentar resultados del avance como evidencia del proyecto se requiere:

- fijar Python y dependencias con un lockfile o hashes; `requirements.txt` contiene rangos, mientras el README enumera una instalación concreta;
- ejecutar en un entorno limpio y conservar reporte de pruebas, cobertura real y comando exacto. El objetivo de cobertura `>= 80 %` no aparece respaldado por un reporte versionado;
- publicar un manifiesto pequeño con commit, dataset ID y hash, configuración, versiones, semilla, métricas y hashes del modelo/metadata. Los binarios pueden mantenerse como artefactos de CI o release en vez de Git;
- corregir la discrepancia del README que afirma un run/model version de MLflow sin incluir evidencia consultable en la rama;
- validar con datos observados y backtesting temporal. Tres días sintéticos correlacionados sirven para comprobar ejecución, no generalización;
- rechazar horizontes que no sean múltiplos exactos de la frecuencia o registrar el horizonte efectivo. El cálculo actual usa redondeo;
- cargar únicamente artefactos joblib de procedencia confiable y comprobar hash/metadata antes de deserializarlos;
- convertir el módulo de drift en un proceso medible: dataset de referencia, ventana reciente, umbrales justificados, persistencia de alertas y relación con error real cuando el target observado ya esté disponible. No activar reentrenamiento automático en este incremento.

## Criterio de cierre recomendado

El avance puede registrarse como **núcleo ML experimental implementado sobre fixture simulado**. No debe marcarse aún como Prediction Service integrado ni como modelo validado para operación.

El siguiente cierre verificable es: contrato Data Processing v1 acordado; particiones temporales purgadas; selección sin usar TEST; pruebas anti-leakage corregidas; suite y cobertura ejecutadas en entorno limpio; artefactos reproducibles con hashes; y API interna capaz de reproducir el preprocesamiento y devolver el contrato completo. Después corresponde una prueba Data Processing → Prediction con dataset versionado y, más adelante, evaluación sobre observaciones reales.
