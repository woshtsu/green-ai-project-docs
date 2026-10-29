# PMV2: incremento técnico del 28 de octubre de 2026

Base: PMV2/Sprints 4–6 en `4. Gestión de Proyecto.md`. El usuario autorizó límites de demostración al no existir SLA/SLO aprobados. Esta entrega no declara cerrado el PMV2 académico.

## Implementado

- Servicio `green-ai-recommendations`: Policy Engine separado de Prediction y Gateway, contrato OpenAPI, comprobaciones de recurso/vigencia/rangos, propuestas sin ejecución.
- Recomendaciones visibles en el frontend con telemetría manual, restricciones y estado no evaluable/bloqueada/revisión humana. Sin aprobación automática ni estimación de ahorro.
- Energía mediante importación de potencia, conservación de procedencia, kWh y CO₂e opcional con factor y fuente.
- Rutas explícitas JWT/RBAC en Gateway, timeout y tamaño limitado; integración en Compose.
- Métricas Prometheus, dashboard Grafana provisionado y reglas de alerta de demostración.

## Verificación realizada

- Servicio: 12 pruebas automatizadas, incluyendo entradas no finitas, fechas, datos faltantes/vencidos, identidad, fallo de upstream sin reintento, integración energética y métricas.
- Frontend: 13 pruebas Node (incluye las existentes).
- Gateway: 11 pruebas Maven (incluye autenticación, roles, rutas y conservación del cuerpo).
- Compose base y con observabilidad: configuración válida.
- Navegador: flujo con fixtures y handlers reales, comprobados `not_evaluable`, revisión humana y bloqueo por latencia; sin errores JavaScript observados. No equivale a un E2E de la pila real.

## Pendientes para aceptar el PMV2

1. Arrancar Docker Desktop y probar la pila completa, incluyendo construcción de imágenes, scrape, reglas Prometheus y render de Grafana. Docker estaba detenido durante esta entrega.
2. Evaluar el modelo con un dataset independiente y representativo, protocolo temporal y MAE/RMSE/sMAPE con umbrales acordados. «Precisión ≥90 %» necesita definición para una regresión; no convertir automáticamente `100−sMAPE` en precisión.
3. Aprobar SLA/SLO y sustituir telemetría manual por fuentes verificadas de latencia/errores. Realizar ensayos de las propuestas con carga antes de alegar cumplimiento futuro.
4. Integrar potencia real/simulada desde el pipeline si se requiere automatizar el cálculo: esta entrega recibe archivos de un único periodo, no realiza medición ni validación de su procedencia.
5. Si la aceptación exige aprobación/rechazo persistente, añadir ese flujo y auditoría. El motor actual solo genera propuestas referenciadas.

El modelo sintético se entrena al construir la imagen de Prediction, según su Dockerfile existente; no se modificó ni se volvió a entrenar en esta entrega. No se acreditan ahorro, precisión de producción ni ausencia de violaciones de SLA.

Operación, contrato y configuración: `../green-ai-recommendations/README.md`.
