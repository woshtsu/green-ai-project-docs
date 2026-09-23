Informe técnico: Modelo de Predicción ML
1. Propósito
Este documento especifica la implementación del componente de Machine
Learning encargado de predecir la demanda computacional a corto plazo.
Debe desarrollarse dentro de la carpeta existente `ML/` y quedar
acompañado de pruebas automatizadas, artefactos reproducibles y registro
mediante MLflow.
2. Contexto vigente
La arquitectura global es de microservicios sobre Kubernetes. El flujo
actual comprobado es `Simulator → Prometheus → Monitoring`. Data
Processing consume las métricas normalizadas de Monitoring y prepara el
dataset para Prediction.
Prediction no debe consultar directamente Prometheus ni Supabase. Debe
recibir datasets/features preparados y versionados desde Data
Processing.
El contrato de Prediction requiere identificar, como mínimo,
`predictionId`, recurso, target, instante futuro, valor, unidad,
`modelVersion`, `inputDatasetId`, procedencia y fecha de generación. Las
predicciones deben identificarse como `estimated`.
3. Objetivo del modelo
Estimar la demanda computacional futura a corto plazo, priorizando CPU y
utilizando memoria, red y otras variables disponibles como predictores
cuando estén justificadas.
La variable objetivo inicial será `cpu_utilization`, expresada en
porcentaje, siempre que el dataset presente calidad suficiente.
No debe interpretarse CPU como consumo energético.
4. Horizontes
Evaluar inicialmente:
5 minutos
15 minutos
30 minutos
El horizonte definitivo se seleccionará experimentalmente considerando
calidad de datos, autocorrelación, error y utilidad para el ciclo de
decisión.
La ventana histórica se determinará mediante análisis temporal y pruebas
comparativas.
5. Modelos obligatorios
Evaluar:
Persistence/Naive baseline.
Promedio móvil cuando corresponda.
Random Forest Regressor.
XGBoost Regressor.
No asumir previamente que Random Forest o XGBoost será el seleccionado.
Deep Learning queda fuera de la primera versión.
6. Estructura obligatoria
``` text
ML/
├── README.md
├── requirements.txt
├── .gitignore
├── config/
│   └── config.yaml
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
├── notebooks/
│   └── 01_exploratory_analysis.ipynb
├── src/
│   ├── config/
│   ├── data/
│   │   ├── loader.py
│   │   ├── schema.py
│   │   └── validation.py
│   ├── preprocessing/
│   │   ├── cleaning.py
│   │   ├── temporal.py
│   │   └── features.py
│   ├── models/
│   │   ├── baseline.py
│   │   ├── random_forest.py
│   │   └── xgboost_model.py
│   ├── evaluation/
│   │   ├── metrics.py
│   │   ├── evaluation.py
│   │   └── comparison.py
│   ├── training/
│   │   └── train.py
│   ├── inference/
│   │   └── predict.py
│   └── mlflow/
│       └── tracking.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── models/
│   ├── candidate/
│   └── selected/
├── results/
│   ├── metrics/
│   ├── predictions/
│   ├── plots/
│   └── reports/
└── scripts/
    ├── prepare_dataset.py
    ├── train_models.py
    ├── evaluate_models.py
    └── run_pipeline.py
```
7. Dependencias
Como base:
``` text
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
Registrar las versiones efectivamente utilizadas.
8. Entrada de datos
El dataset debe respetar el contrato de Data Processing. Como mínimo
debe conservar:
`schemaVersion`
`datasetId`
período
recurso
features
`origins`
`dataStatus`
warnings
El DataFrame puede utilizarse internamente, pero no es el contrato entre
microservicios.
Si Data Processing todavía no entrega el dataset definitivo, utilizar un
fixture controlado compatible con el contrato conocido. No inventar un
contrato de producción.
9. Calidad de datos
Implementar validaciones para:
timestamps inválidos;
timestamps sin zona;
duplicados;
`null`;
`NaN`;
`Inf`;
procedencia inválida;
calidad inválida;
discontinuidades temporales;
dataset vacío.
Nunca convertir automáticamente `missing`, `no_data`, `NaN` o errores en
cero.
Conservar la procedencia:
`observed`
`simulated`
`estimated`
`unknown`
No mezclar procedencias sin una operación explícita.
10. EDA
El notebook debe producir:
número de registros;
período;
frecuencia;
nodos;
clusters;
variables;
unidades;
valores faltantes;
duplicados;
estadística descriptiva;
series temporales;
comportamiento por nodo;
comportamiento por hora;
comportamiento por día cuando corresponda;
autocorrelación.
El análisis debe justificar la ventana histórica y las variables
seleccionadas.
11. Feature Engineering
Evaluar:
Variables temporales
``` text
hour
minute
day_of_week
day_of_month
```
Lags
``` text
cpu_lag_1
cpu_lag_2
cpu_lag_3
```
y otros solamente si la frecuencia los justifica.
Rolling features
``` text
cpu_rolling_mean
cpu_rolling_std
cpu_rolling_min
cpu_rolling_max
```
Las ventanas deben justificarse experimentalmente.
Variables complementarias
Cuando estén disponibles:
``` text
memory_utilization
network_in
network_out
workload_count
pod_count
cpu_requests
memory_requests
```
No agregar variables sin justificación.
12. Target
Para cada horizonte crear el target futuro correspondiente.
Ejemplo conceptual:
``` python
target_15m = cpu_utilization.shift(-N)
```
`N` debe calcularse según la frecuencia real del dataset.
Las features solamente pueden utilizar información disponible hasta el
instante de predicción.
13. Prevención de leakage
Debe existir una prueba específica contra data leakage.
Para predecir `CPU(t+15)` se permiten:
``` text
CPU(t)
CPU(t-1)
CPU(t-2)
memory(t)
network(t)
```
No se permiten:
``` text
CPU(t+1)
CPU(t+5)
CPU(t+15)
```
El pipeline debe fallar si una feature futura entra al entrenamiento.
14. División temporal
Utilizar división cronológica:
``` text
TRAIN | VALIDATION | TEST
```
Configuración inicial:
``` text
70 % | 15 % | 15 %
```
Los datos deben permanecer ordenados temporalmente. No utilizar
`train_test_split` aleatorio para la evaluación principal.
15. Baseline
Implementar Persistence/Naive:
``` text
ŷ(t+h) = y(t)
```
Evaluar promedio móvil cuando corresponda.
El baseline es obligatorio para demostrar si Machine Learning aporta
valor.
16. Random Forest
Implementar `RandomForestRegressor`.
Registrar:
`n_estimators`
`max_depth`
`min_samples_split`
`min_samples_leaf`
`max_features`
`random_state`
`n_jobs`
La configuración debe ser reproducible.
17. XGBoost
Implementar `XGBRegressor`.
Registrar como mínimo:
`n_estimators`
`max_depth`
`learning_rate`
`subsample`
`colsample_bytree`
`objective`
`random_state`
La configuración final debe surgir de la evaluación.
18. Métricas
Calcular obligatoriamente:
MAE
``` text
mean(|y - ŷ|)
```
RMSE
``` text
sqrt(mean((y - ŷ)^2))
```
sMAPE
Implementar una versión estable ante valores próximos a cero.
Latencia
Registrar:
media;
p50;
p95 cuando exista suficiente cantidad de inferencias.
19. Evaluación por escenarios
Evaluar, cuando el dataset lo permita:
baja carga;
carga normal;
alta carga;
picos.
Reportar:
``` text
MAE general
MAE alta demanda
RMSE general
RMSE alta demanda
sMAPE general
sMAPE alta demanda
```
20. Comparación
Generar una tabla con:
Modelo            Horizonte         MAE        RMSE       sMAPE    Latencia
---
Persistence              5m   calculado   calculado   calculado   calculado
Random Forest            5m   calculado   calculado   calculado   calculado
XGBoost                  5m   calculado   calculado   calculado   calculado
Persistence             15m   calculado   calculado   calculado   calculado
Random Forest           15m   calculado   calculado   calculado   calculado
XGBoost                 15m   calculado   calculado   calculado   calculado
Persistence             30m   calculado   calculado   calculado   calculado
Random Forest           30m   calculado   calculado   calculado   calculado
XGBoost                 30m   calculado   calculado   calculado   calculado
No introducir valores ficticios.
21. Selección
El modelo seleccionado debe surgir del experimento.
Prioridad:
menor MAE;
menor RMSE;
menor sMAPE;
comportamiento en alta demanda;
latencia;
complejidad operacional.
Si los modelos son equivalentes, preferir el más simple.
No asumir que XGBoost será el ganador.
El proyecto no debe tratar una meta histórica de 90 % como resultado
garantizado.
22. MLflow
Cada entrenamiento debe registrar:
Parameters
``` text
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
Metrics
``` text
mae
rmse
smape
latency_mean_ms
latency_p95_ms
high_demand_mae
high_demand_rmse
```
Tags
``` text
dataset_id
schema_version
model_version
git_commit
environment
```
Artifacts
``` text
model
metrics.json
predictions.csv
feature_importance.csv
plots
configuration
```
Registrar el modelo seleccionado mediante MLflow Model Registry.
23. Artefactos locales
Generar:
``` text
models/selected/
├── model.joblib
└── metadata.json
```
`metadata.json` debe contener:
``` json
{
  "modelVersion": "1.0.0",
  "modelType": "XGBoost",
  "target": "cpu_utilization",
  "unit": "%",
  "horizon": "15m",
  "datasetId": "dataset-001",
  "features": [],
  "metrics": {
    "mae": 0.0,
    "rmse": 0.0,
    "smape": 0.0
  }
}
```
Los valores reales deben ser generados automáticamente.
24. Inferencia
Implementar una función interna equivalente a:
``` python
predict(features)
```
Debe:
cargar el modelo;
validar features;
mantener el orden correcto;
ejecutar inferencia;
devolver predicción;
devolver metadatos;
medir latencia.
No debe conectarse directamente a Prometheus, Supabase o Kubernetes.
25. Salida preparada para Prediction Service
La información generada debe permitir posteriormente producir:
``` json
{
  "predictionId": "pred-001",
  "resource": {
    "type": "node",
    "cluster": "cluster-01",
    "id": "node-01"
  },
  "target": "cpu_utilization",
  "predictedFor": "RFC3339",
  "value": 0.0,
  "unit": "%",
  "modelVersion": "1.0.0",
  "inputDatasetId": "dataset-001",
  "origin": "estimated",
  "generatedAt": "RFC3339"
}
```
La API FastAPI definitiva será implementada en la etapa de Prediction
Service.
26. Pruebas unitarias obligatorias
`test_validation.py`
Probar:
esquema válido;
timestamp inválido;
campos ausentes;
nulos;
NaN;
Inf;
procedencia inválida;
calidad inválida.
`test_features.py`
Probar:
lags;
rolling;
variables temporales;
target;
ausencia de columnas futuras;
orden temporal.
`test_baseline.py`
Probar:
persistencia;
promedio móvil cuando corresponda;
dimensiones;
ausencia de leakage.
`test_metrics.py`
Probar:
MAE;
RMSE;
sMAPE;
valores conocidos;
valores próximos a cero.
`test_models.py`
Probar:
entrenamiento Random Forest;
entrenamiento XGBoost;
cantidad correcta de predicciones;
valores numéricos;
ausencia de NaN.
27. Pruebas de integración
Implementar:
``` text
dataset
→ validation
→ preprocessing
→ features
→ split
→ baseline
→ Random Forest
→ XGBoost
→ evaluation
→ selection
→ artifact
```
Comprobar también:
carga del `model.joblib`;
inferencia después de recargarlo;
creación de metadata;
registro MLflow cuando esté disponible.
28. Prueba de reproducibilidad
Ejecutar dos entrenamientos con:
mismo dataset;
mismo código;
mismos parámetros;
misma semilla.
Comparar:
métricas;
predicciones;
metadata.
Las diferencias no justificadas deben considerarse error.
29. Prueba anti-leakage
Debe existir una prueba automatizada que rechace cualquier feature cuyo
timestamp sea posterior al instante utilizado para generar la
predicción.
30. Cobertura
Objetivo:
``` text
>= 80 %
```
Ejecutar:
``` bash
pytest --cov=src tests/
```
Priorizar cobertura de:
validación;
features;
baseline;
métricas;
selección;
inferencia.
31. Dataset de prueba
Crear:
``` text
tests/fixtures/sample_dataset.json
```
Debe ser pequeño, determinista y suficiente para ejecutar:
validación;
features;
baseline;
entrenamiento;
evaluación;
inferencia.
Las pruebas no deben depender de Internet, Prometheus o Supabase.
32. Pipeline único
Crear:
``` bash
python scripts/run_pipeline.py
```
Debe ejecutar:
``` text
carga
→ validación
→ limpieza
→ features
→ target
→ split
→ baseline
→ Random Forest
→ XGBoost
→ evaluación
→ comparación
→ selección
→ guardado
→ MLflow
```
33. Salidas obligatorias
``` text
results/
├── metrics/
│   ├── model_comparison.csv
│   └── selected_model_metrics.json
├── predictions/
│   ├── test_predictions.csv
│   └── selected_model_predictions.csv
├── plots/
│   ├── actual_vs_predicted.png
│   ├── error_distribution.png
│   ├── temporal_prediction.png
│   └── feature_importance.png
└── reports/
    └── model_report.md
```
34. Gráficas
Generar:
observado vs predicho;
distribución de errores;
predicción temporal;
importancia de variables cuando el modelo lo permita.
No interpretar feature importance como causalidad.
35. Drift
Dejar preparado un módulo para comparar:
``` text
distribución de entrenamiento
vs.
distribución reciente
```
y:
``` text
error histórico
vs.
error reciente
```
No implementar todavía un retraining automático.
36. Condiciones de fallo
El pipeline debe detenerse ante:
dataset vacío;
target inexistente;
timestamps inválidos;
entrenamiento vacío;
test vacío;
muestras insuficientes;
modelo no entrenable;
predicciones NaN;
métricas no calculables.
No generar un modelo aparentemente válido con datos inválidos.
37. Datos insuficientes
Si los datos no son suficientes, devolver un estado claramente
identificable:
``` text
INSUFFICIENT_DATA
```
con:
registros disponibles;
período;
frecuencia;
horizonte;
motivo.
No fabricar datos ni resultados experimentales.
38. Datos simulados
Los datos provenientes del Simulator pueden utilizarse para desarrollo y
pruebas, pero deben conservar:
``` text
origin = simulated
```
y nunca presentarse como observaciones reales.
39. Separación energética
El modelo predice demanda computacional.
No debe afirmar:
ahorro energético;
reducción de kWh;
reducción de CO2;
reducción porcentual de energía.
Esos resultados pertenecen a la etapa de optimización y experimentación.
La implementación del modelo no constituye evidencia de mejora
energética.
40. Criterios de aceptación
Datos
[ ] Dataset cargable.
[ ] Esquema validado.
[ ] Timestamps normalizados.
[ ] Calidad validada.
[ ] Procedencia conservada.
Features
[ ] Variables temporales.
[ ] Lags.
[ ] Rolling features cuando corresponda.
[ ] Target.
[ ] Anti-leakage.
Modelos
[ ] Baseline.
[ ] Random Forest.
[ ] XGBoost.
[ ] Entrenamiento reproducible.
Evaluación
[ ] MAE.
[ ] RMSE.
[ ] sMAPE.
[ ] Latencia.
[ ] Alta demanda.
[ ] Comparación.
[ ] Selección experimental.
MLOps
[ ] MLflow Tracking.
[ ] Model Registry.
[ ] Modelo serializado.
[ ] Metadata.
[ ] Dataset identificado.
Pruebas
[ ] Unitarias.
[ ] Integración.
[ ] Inferencia.
[ ] Reproducibilidad.
[ ] Anti-leakage.
[ ] Cobertura objetivo de 80 %.
41. Entregables
El desarrollador debe entregar:
``` text
ML/
├── código fuente
├── tests
├── requirements.txt
├── configuración
├── fixture
├── notebook EDA
├── modelos
├── resultados
├── gráficos
├── MLflow
└── README.md
```
El README debe explicar instalación, estructura, dataset, ejecución,
entrenamiento, evaluación, pruebas, MLflow, modelo generado e
integración futura.
42. Evidencias
Conservar como mínimo:
``` text
E1  Entorno Python
E2  Dataset
E3  EDA
E4  Dataset procesado
E5  Features
E6  Baseline
E7  Random Forest
E8  XGBoost
E9  Comparación
E10 Evaluación en alta demanda
E11 Modelo seleccionado
E12 MLflow Run
E13 Modelo registrado
E14 model.joblib
E15 Predicciones vs observaciones
E16 Pruebas
E17 Cobertura
E18 Reproducibilidad
E19 Anti-leakage
E20 Reporte
```
43. Trazabilidad
---
Necesidad          Conocimiento   Decisión       Componente     Evidencia
---
Demanda variable   Series         Predecir       Prediction     MAE, RMSE,
temporales +   demanda        Model          sMAPE
ML
Datos históricos   Ingeniería de  Dataset        ML Pipeline    Dataset ID
datos          versionado
Incertidumbre      Machine        Comparar       Model          Comparación
predictiva         Learning       modelos        Evaluation
Reproducibilidad   MLOps          Registrar      MLflow         Runs, modelos
ciclo de vida                 y artefactos
Datos              Calidad de     Validar        Data           Reporte
insuficientes      datos          dataset        Validation
Leakage            Series         División       Training       Test
temporales     temporal       Pipeline       anti-leakage
Cambio de          MLOps          Monitorear     Drift Module   Reporte
distribución                      drift
44. Correspondencia con la EDT
El desarrollo cubre:
``` text
2.6 Machine Learning e IA
├── 2.6.1 Análisis exploratorio de datos
├── 2.6.2 Feature engineering y variables temporales
├── 2.6.3 Modelo baseline
├── 2.6.4 Random Forest Regressor
├── 2.6.5 XGBoost Regressor
├── 2.6.6 Comparación
└── 2.6.7 Modelo seleccionado y MLflow
```
La API FastAPI correspondiente a `2.6.8` queda como etapa posterior de
integración.
45. Resultado final
El componente debe producir:
``` text
Dataset
   ↓
Validación
   ↓
EDA
   ↓
Feature Engineering
   ↓
Baseline
   ↓
Random Forest
   ↓
XGBoost
   ↓
Evaluación
   ↓
Comparación
   ↓
Modelo seleccionado
   ↓
MLflow
   ↓
Artifact
   ↓
Inferencia reproducible
   ↓
Prediction Service
```
El entregable no es solamente un archivo de modelo. Debe existir un
pipeline reproducible, métricas, comparación, pruebas, artefactos,
metadata y registro del ciclo de vida.
46. Regla de implementación
No inventar:
métricas;
resultados;
precisión;
ahorro energético;
datasets;
unidades;
endpoints de producción;
features no justificadas.
Las decisiones dependientes de los datos deben resolverse mediante
experimentación.
Cuando el contrato definitivo de Data Processing o Prediction todavía no
exista, utilizar fixtures compatibles con el contrato conocido y esperar
la versión oficial para la integración.
El objetivo es entregar un modelo predictivo reproducible, evaluado
experimentalmente y listo para ser integrado en Prediction Service.
47. Base documental
Esta especificación se deriva de la documentación técnica vigente del
proyecto:
Guía de ensamblaje de microservicios Green AI.
Resumen de Integración y Funcionamiento (MVP).
Conocimiento de Ingeniería.
Gestión de Proyecto.
Informe Técnico del proyecto.
La documentación del proyecto establece el uso de series temporales y
Machine Learning para predecir demanda, con baseline, Random Forest,
XGBoost, MAE, RMSE, sMAPE, validación temporal, MLflow y monitoreo de
drift. También establece que Deep Learning no forma parte de la primera
versión y que la implementación tecnológica no constituye por sí misma
evidencia de mejora energética.