# PROMPT MAESTRO — DESARROLLO DEL MODELO DE PREDICCIÓN ML

Actúa como un **Machine Learning Engineer / ML Engineer senior**, especializado en:

* Machine Learning aplicado a series temporales.
* Python.
* scikit-learn.
* XGBoost.
* ingeniería de datos.
* MLOps.
* MLflow.
* testing automatizado.
* sistemas distribuidos.
* microservicios.
* observabilidad.
* workloads Kubernetes.
* predicción de demanda computacional.

Tu responsabilidad es **desarrollar completamente el componente de Machine Learning del proyecto**, siguiendo estrictamente la especificación técnica proporcionada.

---

# 1. DOCUMENTO DE REFERENCIA OBLIGATORIO

Antes de escribir código debes leer completamente el siguiente documento:

```text
informe.md
```

Este documento es la **fuente principal de verdad para el desarrollo del componente ML**.

No debes modificar arbitrariamente sus decisiones técnicas.

No debes sustituir:

* Random Forest por otro algoritmo;
* XGBoost por otro algoritmo;
* MLflow por otra herramienta;
* validación temporal por validación aleatoria;
* CPU por energía;
* Recommendation-Only por ejecución automática.

Si encuentras una situación que no esté definida en el documento, primero inspecciona el repositorio y la documentación existente.

Solo debes tomar una decisión propia cuando sea técnicamente necesaria y no contradiga la documentación.

Cuando hagas una decisión propia, documenta:

```text
DECISIÓN TÉCNICA
Motivo:
Alternativas consideradas:
Decisión:
Impacto:
```

---

# 2. OBJETIVO

Debes convertir la carpeta actualmente existente:

```text
ML/
```

en un componente de Machine Learning funcional, reproducible, probado y preparado para integrarse posteriormente con el Prediction Service.

El objetivo del componente es:

> Predecir la demanda computacional futura a corto plazo, priorizando la utilización de CPU, utilizando información histórica de workloads e infraestructura.

Los horizontes iniciales son:

```text
5 minutos
15 minutos
30 minutos
```

La selección del horizonte definitivo debe realizarse experimentalmente.

---

# 3. REGLA FUNDAMENTAL

## NO empieces programando inmediatamente.

Primero debes inspeccionar el proyecto.

Realiza las siguientes acciones:

1. listar la estructura completa del repositorio;
2. localizar la carpeta `ML/`;
3. localizar la documentación del proyecto;
4. localizar servicios existentes;
5. localizar contratos JSON;
6. localizar endpoints existentes;
7. localizar configuración;
8. localizar Dockerfiles;
9. localizar `docker-compose`;
10. localizar archivos Kubernetes;
11. localizar datos existentes;
12. localizar cualquier implementación relacionada con Monitoring;
13. localizar cualquier implementación relacionada con Data Processing;
14. localizar cualquier referencia a Prediction;
15. localizar Prometheus;
16. localizar Supabase/PostgreSQL;
17. localizar MLflow si ya existe;
18. identificar versiones de Python y dependencias.

NO debes asumir que la carpeta `ML/` está completamente aislada.

Primero comprende el repositorio.

---

# 4. NO ROMPER EL SISTEMA EXISTENTE

Regla obligatoria:

> No modificar componentes existentes que no sean necesarios para implementar ML.

No debes:

* cambiar contratos existentes;
* cambiar endpoints existentes;
* cambiar nombres de servicios;
* cambiar variables de entorno existentes;
* cambiar arquitectura;
* eliminar código;
* modificar Monitoring;
* modificar Prometheus;
* modificar Kubernetes;
* modificar Data Processing;

salvo que sea estrictamente necesario para integrar el componente ML.

Si detectas una incompatibilidad:

1. documentarla;
2. explicar el problema;
3. aplicar la modificación mínima necesaria.

---

# 5. ARQUITECTURA VIGENTE

La arquitectura del proyecto utiliza microservicios.

La cadena conceptual es:

```text
Monitoring
    |
    v
Data Processing
    |
    v
Prediction
    |
    v
Decision
    |
    v
Optimization
    |
    v
Policy/Safety
    |
    v
Recommendation
```

El componente ML corresponde principalmente al núcleo de Prediction.

La arquitectura actual utiliza:

```text
Kubernetes
Prometheus
Grafana
RabbitMQ
PostgreSQL/Supabase
MLflow
Python
FastAPI
scikit-learn
XGBoost
```

No todos estos componentes deben ser utilizados directamente por el modelo.

---

# 6. REGLA DE RESPONSABILIDADES

El modelo ML:

### SÍ debe hacer

* cargar datos;
* validar datos;
* limpiar datos;
* generar features;
* construir targets;
* entrenar;
* evaluar;
* comparar modelos;
* seleccionar modelo;
* registrar modelos;
* generar predicciones;
* generar artefactos;
* ejecutar pruebas.

### NO debe hacer

* consultar directamente Prometheus;
* consultar directamente Supabase;
* modificar Kubernetes;
* escalar workloads;
* modificar réplicas;
* cambiar CPU;
* cambiar memoria;
* ejecutar recomendaciones;
* modificar infraestructura.

La interacción con infraestructura pertenece a otros componentes.

---

# 7. ESTRUCTURA OBJETIVO

Debes implementar una estructura equivalente a:

```text
ML/
├── README.md
├── requirements.txt
├── .gitignore
│
├── config/
│   └── config.yaml
│
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
│
├── notebooks/
│   └── 01_exploratory_analysis.ipynb
│
├── src/
│   ├── __init__.py
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   ├── schema.py
│   │   └── validation.py
│   │
│   ├── preprocessing/
│   │   ├── __init__.py
│   │   ├── cleaning.py
│   │   ├── temporal.py
│   │   └── features.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── baseline.py
│   │   ├── random_forest.py
│   │   └── xgboost_model.py
│   │
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── metrics.py
│   │   ├── evaluation.py
│   │   └── comparison.py
│   │
│   ├── training/
│   │   ├── __init__.py
│   │   └── train.py
│   │
│   ├── inference/
│   │   ├── __init__.py
│   │   └── predict.py
│   │
│   └── mlflow/
│       ├── __init__.py
│       └── tracking.py
│
├── tests/
│   ├── unit/
│   │   ├── test_validation.py
│   │   ├── test_features.py
│   │   ├── test_baseline.py
│   │   ├── test_metrics.py
│   │   └── test_models.py
│   │
│   ├── integration/
│   │   ├── test_training_pipeline.py
│   │   └── test_model_artifact.py
│   │
│   └── fixtures/
│       └── sample_dataset.json
│
├── models/
│   ├── candidate/
│   └── selected/
│
├── results/
│   ├── metrics/
│   ├── predictions/
│   ├── plots/
│   └── reports/
│
└── scripts/
    ├── prepare_dataset.py
    ├── train_models.py
    ├── evaluate_models.py
    └── run_pipeline.py
```

Puedes adaptar la estructura si el repositorio ya posee una convención equivalente.

No dupliques estructuras innecesariamente.

---

# 8. DEPENDENCIAS

Utiliza como base:

```text
pandas
numpy
scikit-learn
xgboost
matplotlib
seaborn
pyyaml
joblib
mlflow
pytest
pytest-cov
```

Antes de instalar dependencias:

1. comprobar si ya existe `requirements.txt`;
2. comprobar `pyproject.toml`;
3. comprobar Poetry;
4. comprobar uv;
5. comprobar Conda;
6. comprobar Docker.

Respeta el gestor de dependencias existente.

No instales paquetes innecesarios.

---

# 9. DATASET

El modelo debe aceptar datos provenientes del pipeline de Data Processing.

Debe soportar conceptualmente información equivalente a:

```json
{
  "schemaVersion": "1.0",
  "datasetId": "dataset-001",
  "period": {
    "start": "2026-09-01T00:00:00Z",
    "end": "2026-09-01T23:59:59Z"
  },
  "resource": {
    "type": "node",
    "cluster": "cluster-01",
    "id": "node-01"
  },
  "features": [],
  "origins": [
    "observed"
  ],
  "dataStatus": "complete",
  "warnings": []
}
```

Si el repositorio ya tiene un contrato diferente y oficial, debes utilizar ese contrato.

NO inventes un nuevo contrato si ya existe uno.

---

# 10. CALIDAD DE DATOS

Implementa validaciones para:

* timestamps;
* zona horaria;
* orden temporal;
* duplicados;
* valores faltantes;
* NaN;
* Inf;
* procedencia;
* calidad;
* continuidad temporal;
* columnas obligatorias.

Nunca conviertas automáticamente:

```text
null
NaN
missing
no_data
```

en:

```text
0
```

Distingue entre:

```text
ausencia de dato
valor cero
error de fuente
```

---

# 11. PROCEDENCIA

Conservar:

```text
observed
simulated
estimated
unknown
```

Los datos generados por Simulator deben conservar:

```text
origin = simulated
```

No presentarlos como datos reales.

---

# 12. VARIABLE OBJETIVO

La variable objetivo inicial será:

```text
cpu_utilization
```

Unidad:

```text
%
```

La predicción representa:

```text
demanda computacional
```

NO:

```text
energía
kWh
CO2
ahorro energético
```

No convertir CPU directamente en energía.

---

# 13. HORIZONTES

Implementar soporte para:

```text
5m
15m
30m
```

El código debe ser configurable.

No hardcodear únicamente 15 minutos.

---

# 14. FEATURE ENGINEERING

Implementar y evaluar:

### Variables temporales

```text
hour
minute
day_of_week
day_of_month
```

### Lags

Como mínimo evaluar:

```text
cpu_lag_1
cpu_lag_2
cpu_lag_3
```

Y otros lags solamente cuando la frecuencia del dataset los justifique.

### Rolling

Evaluar:

```text
rolling_mean
rolling_std
rolling_min
rolling_max
```

### Variables adicionales

Cuando existan:

```text
memory_utilization
network_in
network_out
workload_count
pod_count
cpu_requests
memory_requests
```

No agregar features sin justificación.

---

# 15. DATA LEAKAGE

Este punto es crítico.

Debes garantizar que ninguna feature utilice información futura.

Para:

```text
CPU(t+15)
```

permitido:

```text
CPU(t)
CPU(t-1)
CPU(t-2)
memory(t)
network(t)
```

prohibido:

```text
CPU(t+1)
CPU(t+5)
CPU(t+15)
```

Implementa una prueba automatizada específica contra leakage.

---

# 16. TARGET

Generar targets futuros utilizando la frecuencia real.

Conceptualmente:

```python
target = df["cpu_utilization"].shift(-N)
```

pero:

```text
N
```

debe calcularse dinámicamente según la frecuencia temporal.

No asumir que:

```text
15 minutos = 3 registros
```

sin verificar la frecuencia.

---

# 17. SPLIT

Usar división temporal:

```text
TRAIN
VALIDATION
TEST
```

Configuración inicial:

```text
70 %
15 %
15 %
```

Nunca utilizar una división aleatoria como evaluación principal.

No utilizar:

```python
train_test_split(..., shuffle=True)
```

para la evaluación temporal principal.

---

# 18. BASELINE

Implementar:

```text
Persistence / Naive
```

Regla:

```text
ŷ(t+h) = y(t)
```

Evaluar promedio móvil cuando corresponda.

El baseline es obligatorio.

La finalidad es determinar si Machine Learning realmente aporta valor.

---

# 19. RANDOM FOREST

Implementar:

```python
RandomForestRegressor
```

Registrar:

```text
n_estimators
max_depth
min_samples_split
min_samples_leaf
max_features
random_state
n_jobs
```

Utilizar semilla reproducible.

---

# 20. XGBOOST

Implementar:

```python
XGBRegressor
```

Registrar:

```text
n_estimators
max_depth
learning_rate
subsample
colsample_bytree
objective
random_state
```

No asumir que XGBoost será el seleccionado.

---

# 21. MÉTRICAS

Implementar:

```text
MAE
RMSE
sMAPE
```

y:

```text
mean latency
p50 latency
p95 latency
```

cuando exista suficiente cantidad de inferencias.

---

# 22. ALTA DEMANDA

Evaluar específicamente:

```text
baja carga
normal
alta carga
picos
```

cuando el dataset permita clasificarlos.

Reportar:

```text
MAE general
MAE alta demanda

RMSE general
RMSE alta demanda

sMAPE general
sMAPE alta demanda
```

---

# 23. SELECCIÓN DEL MODELO

No escribas:

```python
selected_model = XGBRegressor(...)
```

simplemente porque XGBoost es más avanzado.

La selección debe depender de resultados.

Priorizar:

1. MAE;
2. RMSE;
3. sMAPE;
4. alta demanda;
5. latencia;
6. complejidad.

Si los resultados son equivalentes, preferir el modelo más simple.

---

# 24. MLflow

Cada entrenamiento debe generar un Run.

Registrar:

### Parameters

```text
model_type
target
horizon
window_size
features
train_ratio
validation_ratio
test_ratio
random_state
hyperparameters
```

### Metrics

```text
mae
rmse
smape
latency_mean_ms
latency_p95_ms
high_demand_mae
high_demand_rmse
```

### Tags

```text
dataset_id
schema_version
model_version
git_commit
environment
```

### Artifacts

```text
model
metrics.json
predictions.csv
feature_importance.csv
plots
configuration
```

Registrar el modelo seleccionado en Model Registry.

---

# 25. MODELO SERIALIZADO

Generar:

```text
models/selected/model.joblib
```

y:

```text
models/selected/metadata.json
```

El metadata debe incluir:

```text
modelVersion
modelType
target
unit
horizon
datasetId
features
metrics
```

---

# 26. INFERENCIA

Implementar una función equivalente a:

```python
predict(features)
```

Debe:

1. cargar modelo;
2. validar features;
3. respetar orden;
4. inferir;
5. devolver predicción;
6. devolver metadata;
7. medir latencia.

No consultar infraestructura.

---

# 27. PRUEBAS

Debes desarrollar las pruebas como parte de la implementación.

NO dejar las pruebas para el final.

Implementar como mínimo:

```text
tests/unit/test_validation.py
tests/unit/test_features.py
tests/unit/test_baseline.py
tests/unit/test_metrics.py
tests/unit/test_models.py

tests/integration/test_training_pipeline.py
tests/integration/test_model_artifact.py
```

Y:

```text
tests/fixtures/sample_dataset.json
```

---

# 28. TESTS DE VALIDACIÓN

Probar:

* dataset válido;
* dataset vacío;
* timestamp inválido;
* columnas faltantes;
* NaN;
* Inf;
* duplicados;
* procedencia inválida;
* calidad inválida.

---

# 29. TESTS DE FEATURES

Probar:

* generación de lags;
* rolling;
* variables temporales;
* target;
* orden temporal;
* eliminación correcta de filas sin target;
* ausencia de leakage.

---

# 30. TESTS DE MODELOS

Probar:

```text
Random Forest training
XGBoost training
predict()
output shape
numeric predictions
no NaN
```

---

# 31. TESTS DE MÉTRICAS

Usar datos conocidos para verificar:

```text
MAE
RMSE
sMAPE
```

No limitar las pruebas a comprobar que una función "no da error".

Comprobar resultados matemáticamente conocidos.

---

# 32. TEST DE REPRODUCIBILIDAD

Ejecutar dos veces:

```text
mismo dataset
mismos parámetros
misma semilla
mismo código
```

Comparar:

```text
métricas
predicciones
metadata
```

Documentar cualquier fuente legítima de no determinismo.

---

# 33. TEST ANTI-LEAKAGE

Debe existir un test que falle cuando se introduce una feature futura.

Ejemplo:

```text
cpu_future_15m
```

debe ser rechazada.

---

# 34. TEST DEL PIPELINE COMPLETO

Debe ejecutarse:

```text
load
→ validate
→ clean
→ feature engineering
→ target
→ temporal split
→ baseline
→ random forest
→ xgboost
→ evaluation
→ comparison
→ selection
→ artifact
```

La prueba debe confirmar que todo el flujo funciona.

---

# 35. COBERTURA

Ejecutar:

```bash
pytest --cov=src tests/
```

Objetivo:

```text
>= 80 %
```

No generar tests artificiales únicamente para incrementar cobertura.

---

# 36. PIPELINE PRINCIPAL

Debe existir:

```bash
python scripts/run_pipeline.py
```

Debe ejecutar el flujo completo.

También pueden existir:

```bash
python scripts/prepare_dataset.py

python scripts/train_models.py

python scripts/evaluate_models.py
```

---

# 37. RESULTADOS

Generar:

```text
results/
├── metrics/
│   ├── model_comparison.csv
│   └── selected_model_metrics.json
│
├── predictions/
│   ├── test_predictions.csv
│   └── selected_model_predictions.csv
│
├── plots/
│   ├── actual_vs_predicted.png
│   ├── error_distribution.png
│   ├── temporal_prediction.png
│   └── feature_importance.png
│
└── reports/
    └── model_report.md
```

---

# 38. NOTEBOOK

Crear:

```text
notebooks/01_exploratory_analysis.ipynb
```

Debe ser reproducible y documentar:

1. carga;
2. calidad;
3. estadísticas;
4. comportamiento temporal;
5. autocorrelación;
6. distribución;
7. features;
8. conclusiones.

El notebook no debe contener lógica crítica que no exista también en `src/`.

La lógica productiva debe estar en módulos Python.

---

# 39. DRIFT

Preparar soporte para comparar:

```text
training distribution
vs.
recent distribution
```

y:

```text
historical error
vs.
recent error
```

No implementar retraining automático.

---

# 40. DATOS INSUFICIENTES

Si no existe suficiente información:

NO inventes resultados.

El pipeline debe producir un error controlado:

```text
INSUFFICIENT_DATA
```

e indicar:

```text
registros disponibles
período
frecuencia
horizonte
motivo
```

---

# 41. ENERGÍA

Regla estricta:

El modelo predice:

```text
demanda computacional
```

NO predice:

```text
ahorro energético
```

NO afirmar:

```text
"el modelo reduce 15 % la energía"
```

El 15 % es una meta experimental del proyecto, no un resultado que deba aparecer automáticamente.

---

# 42. DEEP LEARNING

NO implementar:

```text
LSTM
GRU
Transformer
```

en esta etapa.

Únicamente considerar Deep Learning posteriormente si existe evidencia de que:

* los datos son suficientes;
* existe estructura temporal que lo justifique;
* Random Forest/XGBoost son insuficientes;
* la complejidad adicional aporta valor.

---

# 43. DOCUMENTACIÓN

Al finalizar, actualizar:

```text
ML/README.md
```

Debe explicar:

```text
Objetivo
Arquitectura
Instalación
Dependencias
Dataset
Estructura
Configuración
Entrenamiento
Evaluación
Pruebas
MLflow
Modelo seleccionado
Inferencia
Artefactos
Limitaciones
Integración futura
```

No declarar que el modelo es "preciso" sin métricas.

No declarar que "funciona en producción" si únicamente fue probado experimentalmente.

---

# 44. VALIDACIÓN FINAL

Antes de terminar debes ejecutar:

```bash
pytest
```

y:

```bash
pytest --cov=src tests/
```

Después:

```bash
python scripts/run_pipeline.py
```

Verificar que existan:

```text
models/selected/model.joblib
models/selected/metadata.json

results/metrics/model_comparison.csv
results/metrics/selected_model_metrics.json
results/predictions/
results/plots/
results/reports/model_report.md
```

Si MLflow está disponible, verificar:

```text
Run
Parameters
Metrics
Artifacts
Model Registry
```

---

# 45. CRITERIOS DE TERMINADO

No declares el trabajo terminado hasta cumplir:

```text
[ ] Repositorio inspeccionado
[ ] Carpeta ML implementada
[ ] Dependencias configuradas
[ ] Dataset fixture disponible
[ ] Validación implementada
[ ] EDA implementado
[ ] Feature engineering implementado
[ ] Target implementado
[ ] Anti-leakage implementado
[ ] Split temporal implementado
[ ] Baseline implementado
[ ] Random Forest implementado
[ ] XGBoost implementado
[ ] MAE implementado
[ ] RMSE implementado
[ ] sMAPE implementado
[ ] Latencia implementada
[ ] Evaluación de alta demanda
[ ] Comparación
[ ] Selección automática basada en métricas
[ ] MLflow Tracking
[ ] MLflow Registry
[ ] model.joblib
[ ] metadata.json
[ ] Función de inferencia
[ ] Tests unitarios
[ ] Tests de integración
[ ] Test anti-leakage
[ ] Test reproducibilidad
[ ] Cobertura
[ ] Pipeline completo
[ ] Resultados
[ ] Gráficas
[ ] Reporte
[ ] README
```

---

# 46. REGLAS DE CALIDAD DE CÓDIGO

El código debe:

* utilizar type hints cuando sean útiles;
* tener funciones pequeñas;
* evitar duplicación;
* separar responsabilidades;
* manejar errores explícitamente;
* utilizar logging;
* evitar `print()` como mecanismo principal de diagnóstico;
* utilizar configuración externa;
* evitar valores mágicos;
* utilizar constantes;
* documentar funciones críticas;
* ser testeable;
* ser reproducible.

No introducir abstracciones innecesarias.

No crear una arquitectura excesivamente compleja para un componente ML experimental.

---

# 47. REGLAS DE SEGURIDAD

No almacenar:

```text
passwords
tokens
API keys
secrets
```

en código.

No subir:

```text
.env
credenciales
tokens
secretos
```

al repositorio.

Si MLflow requiere credenciales, utilizar variables de entorno.

---

# 48. RESULTADO QUE DEBES ENTREGAR

Cuando hayas terminado debes mostrar:

## A. Estructura implementada

Mostrar:

```text
ML/
...
```

## B. Archivos creados/modificados

Enumerar todos.

## C. Dependencias

Mostrar las dependencias agregadas.

## D. Pipeline

Explicar brevemente cómo funciona:

```text
dataset
→ preprocessing
→ features
→ baseline
→ models
→ evaluation
→ selection
→ MLflow
→ artifact
```

## E. Pruebas

Mostrar:

```text
cantidad de tests
tests exitosos
tests fallidos
coverage
```

## F. Modelo

Indicar:

```text
modelo seleccionado
horizonte
features
MAE
RMSE
sMAPE
latencia
```

IMPORTANTE:

Estos valores deben ser **reales obtenidos de la ejecución**.

Nunca inventarlos.

## G. MLflow

Indicar:

```text
run_id
experiment
model version
```

si MLflow está disponible.

## H. Evidencias

Indicar qué archivos contienen:

```text
métricas
predicciones
gráficas
modelo
metadata
reporte
```

---

# 49. COMPORTAMIENTO ANTE PROBLEMAS

Si encuentras un problema:

NO ocultarlo.

NO saltarlo.

NO generar un resultado falso.

Clasifica el problema como:

```text
BLOCKER
WARNING
DECISION_REQUIRED
```

y explica:

```text
Problema:
Causa:
Impacto:
Alternativas:
Recomendación técnica:
```

Si puedes resolverlo sin alterar la arquitectura ni los contratos, resuélvelo.

Si requiere una decisión externa, detén únicamente esa parte y continúa con todo lo que sí pueda implementarse.

---

# 50. INSTRUCCIÓN FINAL

Comienza ahora.

Primero:

```text
1. Inspecciona el repositorio.
2. Lee la documentación.
3. Identifica la arquitectura existente.
4. Identifica los contratos disponibles.
5. Identifica el estado actual de ML.
6. Compara el estado actual con esta especificación.
7. Presenta brevemente el plan de implementación.
```

Después de esa inspección, procede a implementar.

No te limites a crear archivos vacíos.

No entregues pseudocódigo.

No entregues ejemplos incompletos.

Debes desarrollar código funcional.

Implementa también las pruebas.

Ejecuta las pruebas.

Ejecuta el pipeline.

Genera los artefactos.

Registra el experimento.

Verifica el modelo.

Actualiza el README.

Al finalizar, entrega un reporte técnico de lo implementado.

## CONDICIÓN ABSOLUTA

**No inventes resultados experimentales.**

Si todavía no existen datos suficientes para entrenar un modelo real, implementa correctamente todo el pipeline y utiliza únicamente un fixture claramente identificado como `simulated` para validar técnicamente el código.

Distingue siempre entre:

```text
resultado de prueba técnica
```

y:

```text
resultado experimental del proyecto
```

El objetivo es dejar un componente ML **realmente ejecutable, probado, reproducible y listo para integrarse con Prediction Service**, no simplemente generar código que parezca correcto.
