# Recomendaciones dentro de Prediction

Prediction es el propietario de inferencia, evaluación de recomendaciones y cálculo
de energía a partir de muestras suministradas. No existe un microservicio adicional
de recomendaciones. La API llama a `predict_from_payload` en el mismo proceso;
no realiza llamadas HTTP a sí misma ni consulta Supabase, Prometheus o Kubernetes.

## Organización

- `src/service/app.py`: ensamblaje FastAPI y manejo común de errores/correlación.
- `src/service/recommendations.py`: contratos HTTP, validación y coordinación.
- `src/recommendations/policy.py`: política de demostración sin dependencias HTTP.
- `src/inference/predict.py`: inferencia reutilizada por predicciones y recomendaciones.

## Contratos

| Ruta interna | Uso |
| --- | --- |
| `POST /v1/predictions` | Predicción de CPU a partir del dataset preparado. |
| `POST /v1/recommendations` | `{dataset, telemetry?}`; inferencia local y evaluación de restricciones. |
| `POST /v1/energy` | Integra muestras de potencia; no mide ahorro. |
| `GET /metrics` | Métricas de recomendaciones y última estimación/importación para Prometheus. |

Swagger de desarrollo: `http://127.0.0.1:8002/docs` al usar el override
`compose.swagger.yaml`. El frontend continúa usando exclusivamente Gateway:
`/api/prediction/v1/predictions`, `/api/recommendations/v1/recommendations` y
`/api/recommendations/v1/energy`. El prefijo público conservado es una agrupación
funcional, no prueba de que exista otro microservicio. Gateway usa una sola variable
de destino para estas tres operaciones: `GATEWAY_PREDICTION_BASE_URL`.

La telemetría incluye recurso, fecha con zona horaria, procedencia y, opcionalmente,
memoria en porcentaje, latencia p95 en milisegundos y tasa de errores en porcentaje.
Se exige coincidencia del recurso y vigencia de la predicción/telemetría. Ausencias
permanecen desconocidas. Los resultados son `not_evaluable`, `blocked` o
`eligible_for_review`; siempre `executionAllowed=false`. La telemetría es declarada
por el operador, no verificada independientemente. No se garantiza SLA futuro ni ahorro.

`DEMO_POLICY_JSON` se configura en el servicio Prediction. Valores por defecto:

```json
{"cpuLowPercent":30,"cpuHighPercent":80,"memoryMaxPercent":85,"latencyP95MaxMs":500,"errorRateMaxPercent":1,"freshnessSeconds":300}
```

La configuración inválida impide arrancar. Las reglas son de demostración, no SLA
aprobados. Un valor faltante no se reemplaza por cero.

La energía requiere 2–10000 muestras `{timestamp, watts}`, ordenadas y separadas
por intervalos de hasta 300 segundos. Conserva `origin` declarado. Calcula kWh con
integración trapezoidal y CO₂e solo cuando se aporta factor y fuente; sin factor,
CO₂e es `null`. No deduce potencia desde CPU ni prueba reducción de consumo.

Errores de inferencia conservan el contrato `{code,message,details}`: 400 para
entrada inválida, 422 para dataset insuficiente/inválido y 503 para modelo no
disponible. Validaciones de telemetría/energía usan 422 con `{detail}`. Un resultado
interno incompatible se rechaza con 502. No se reintenta la inferencia.

## Verificación

`python -m pytest tests/test_recommendations_api.py` comprueba restricciones,
ausencias, fechas, integridad de identidad, energía y uso de inferencia local.
La suite general se ejecuta con `python -m pytest tests`. Los datos de prueba son
simulados; pasar estas pruebas no demuestra precisión con datos observados.

Desde la raíz del workspace, las imágenes se construyen desde las ramas locales
correctas. Reiniciar un contenedor no incorpora código nuevo:

```powershell
docker compose -f docker-compose.yml -f compose.swagger.yaml up -d --build prediction gateway frontend
```

No ejecutar `down -v`: los históricos y volúmenes no forman parte de esta migración.
