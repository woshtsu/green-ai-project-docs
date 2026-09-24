# Historias de usuario y plan de evidencias

Revisión: 23 de septiembre de 2026 (Lima). Las respuestas usan UTC del 24 de septiembre. Alcance: documentos, código del frontend/Monitoring/Gateway/Simulator y consultas HTTP de lectura al entorno local. No se ejecutó una validación autenticada del navegador ni se verificó directamente Supabase.

## 1. Los documentos todavía no son equivalentes

Se utiliza como referencia provisional **la sección 2.3 de `0.Lineamientos al proyecto.md`**, que enumera HU-01 a HU-10 y contiene criterios de aceptación. No se modificaron los documentos originales.

El mismo documento presenta otra numeración en la tabla de incrementos (HU-01 a HU-17). Por ejemplo, HU-05 significa energía futura en 2.3 y comparación de modelos en la tabla de incrementos. Citar siempre sección y nombre, además del ID.

`2. Conocimiento de Ingenieria.md`, sección 2.4, contiene 15 historias sin ID. Comparte objetivos, pero agrega importación, limpieza, interpretación de predicciones, preparación de ejecución y seguridad por roles. Sus criterios no son idénticos.

| Lineamientos 2.3 | Correspondencia en Conocimiento 2.4 | Diferencia relevante |
| --- | --- | --- |
| HU-01: métricas actuales | Observabilidad: visualizar métricas | Conocimiento exige además workloads, recursos Kubernetes y tolerancia a fuente caída. |
| HU-02: históricos | Observabilidad: consulta histórica | Lineamientos explicita selección de nodo, métrica y período. |
| HU-03: demanda futura | Predicción: demanda computacional | Conocimiento incluye datos insuficientes; Lineamientos exige mostrar modelo y horizonte. |
| HU-04: CPU y memoria futuras | Relación con predicción | No hay historia separada equivalente para ambos recursos. |
| HU-05: energía futura | Sin equivalente explícito | No confundir con registrar energía de experimentos. |
| HU-06: recomendaciones | Decisión, Optimización y Recomendaciones | Desglose en varias historias con criterios adicionales. |
| HU-07: SLA/SLO | Optimización y Policy/Safety | Correspondencia parcial; revisar cada restricción. |
| HU-08: aprobación humana y auditoría | Policy/Safety y Execution/Scheduler | Validar políticas no equivale a aprobar/rechazar con usuario, fecha y justificación. |
| HU-09: comparar baseline/Green AI | Experimentación | Conocimiento agrega invalidación de condiciones incomparables y registro reproducible. |
| HU-10: reporte experimental | Experimentación y Visualización | No especifica el mismo reporte con diferencias absolutas/relativas y métricas predictivas. |

Recomendación: mantener un catálogo único con ID estable y hacer que ambos documentos lo referencien; conservar los criterios adicionales como escenarios, sin eliminarlos para declarar cumplimiento.

## 2. Qué podemos demostrar ahora

“Candidata a cierre” significa que hay implementación y evidencia técnica, pero falta ejecutar y registrar todos los criterios de aceptación desde la interfaz.

| Historia | Estado de esta revisión | Evidencia / pendiente |
| --- | --- | --- |
| HU-01 — métricas actuales | **Candidata a cierre en entorno simulado** | API devolvió las cinco métricas del catálogo con `dataStatus=complete`, identidad, fecha, unidad y `origin=simulated`. Frontend implementa visualización. Falta captura autenticada de cada tipo de métrica y correspondencia con respuesta. |
| HU-02 — históricos | **Candidata a cierre en entorno simulado** | API devolvió 61 puntos de CPU para node-01 en 15 minutos. Frontend implementa filtros de clúster, nodo, métrica y período. Falta demostrar cambios de filtros y gráfica desde UI. |
| Seguridad y acceso — Conocimiento 2.4 | **Parcial** | Gateway valida JWT y permite ADMIN/OPERATOR. Consulta sin token rechazó con 401. Falta evidencia autenticada 200, token válido sin rol permitido → 403, y registro del intento rechazado. No se verificó bitácora de seguridad. |
| Observabilidad — Conocimiento 2.4 | **Parcial** | CPU, RAM, red y filesystem de nodos disponibles. El catálogo revisado no contiene solicitudes, concurrencia, throughput, latencia ni recursos reales del clúster. Falta escenario de fuente caída. |
| Visualización — Conocimiento 2.4 | **Parcial** | Dashboard de métricas implementado. La historia completa también pide predicciones, recomendaciones y resultados experimentales. |
| HU-03 y HU-04 | **Pendientes de evidencia integrada** | Prediction no figura en el compose revisado; el resumen de integración describe un núcleo ML experimental fuera del flujo. No se auditó aquí todo su código. No basta el simulador para acreditar predicción. |
| HU-05 | **Pendiente** | Hace falta energía medida o modelo validado, Wh/kWh y distinción medición/estimación. CPU alta no demuestra consumo energético. |
| HU-06, HU-07 y HU-08 | **Pendientes de evidencia integrada** | No se acreditó flujo operativo de recomendaciones, evaluación SLA/SLO ni aprobación humana auditada. |
| HU-09 y HU-10 | **Pendientes** | Se requieren experimentos comparables baseline/tratamiento y reporte cuantitativo. Una ejecución del simulador no cumple estos criterios. |
| Importación, limpieza, comparación de modelos, preparación de ejecución y registro experimental — Conocimiento | **Fuera de lo validado** | Requieren revisión específica de los módulos y sus escenarios; no se deducen de que los cinco componentes actuales funcionen. |

Supabase cumple el papel de autenticación en el flujo frontend revisado. Los históricos consultados proceden de **Prometheus**, no de tablas Supabase. Tener Supabase operativo no demuestra importación, limpieza o persistencia de métricas allí.

## 3. Guion para recoger evidencia de aceptación

### HU-01 — visualización actual

1. Iniciar sesión y abrir el dashboard. Seleccionar el clúster activo y node-01.
2. Mostrar CPU, memoria, red recibida/transmitida y filesystem. Guardar capturas con nodo, unidad, valor, procedencia, fecha y hora legibles.
3. En Network, guardar la respuesta de la consulta `current` que alimentó la pantalla, su URL y estado 200. No incluir Authorization, cookies ni tokens en las evidencias compartidas.
4. Comprobar que el valor representado corresponde al JSON: CPU ratio × 100, memoria en escala de bytes; red por interfaz y disco por filesystem.
5. Mostrar el target del simulador en Prometheus y vincularlo al mismo clúster/nodo de la respuesta. La etiqueta simulada debe mantenerse visible.

Aceptación: las cuatro familias de métricas se almacenan en el sistema de series temporales y se muestran con identidad y tiempo. Las evidencias de histórico de HU-02 respaldan el almacenamiento temporal; no demuestran durabilidad tras recrear contenedores.

### HU-02 — consulta histórica

1. Con suficientes muestras, elegir CPU, node-01 y período de 15 minutos; capturar gráfica y filtros.
2. Cambiar a node-02; comprobar que la respuesta usa el nodo elegido.
3. Cambiar a memoria y a otro período disponible; comprobar rango, unidades y serie.
4. Guardar respuesta `history` y captura con el mismo intervalo. Para comparar exactamente, usar los tiempos de esa respuesta, pues el refresco mueve la ventana.

Aceptación: se seleccionan nodo, variable y período y se presenta la serie correspondiente. No basta una gráfica sin filtros visibles.

### Seguridad y acceso

1. Con cuenta autorizada, obtener 200 en una ruta de métricas del Gateway.
2. Sin token, comprobar 401; esto ya se observó en esta revisión.
3. En entorno de prueba, usar token válido de cuenta sin rol permitido y comprobar 403. No alterar roles de una cuenta habitual para la demostración.
4. Localizar el registro del intento rechazado y vincularlo a fecha/ruta/resultado. Si no existe, registrar la brecha y mantener la historia parcial.

ADMIN y OPERATOR tienen los mismos permisos de lectura en estas rutas. Mostrar dos insignias de rol no acredita restricciones diferentes.

## 4. Evidencia técnica ya capturada

Carpeta: [evidencias-hu/2026-09-23](evidencias-hu/2026-09-23/).

| Archivo | Resultado observado |
| --- | --- |
| `catalogo.json` | Cinco métricas de infraestructura. |
| `node.cpu.utilization-current.json` | Complete; dos nodos simulados. |
| `node.memory.used-current.json` | Complete; dos nodos simulados. |
| `node.network.receive-current.json` | Complete; tres series por interfaz. |
| `node.network.transmit-current.json` | Complete; tres series por interfaz. |
| `node.filesystem.used-current.json` | Complete; dos series. |
| `cpu-node-01-history.json` | Complete; una serie y 61 muestras; 04:43:59–04:58:59 UTC, resolución 15 s. |

Las respuestas se obtuvieron directamente de Monitoring en `http://127.0.0.1:8080/api/v1/metrics/`. Son evidencia de backend; no prueban el recorrido autenticado Frontend → Gateway → Monitoring.

También se observó HTTP 200 en login del frontend y health de Monitoring/Gateway (UP), y HTTP 401 en el catálogo del Gateway sin token. Estas comprobaciones se registran aquí como observaciones, no como capturas visuales. Docker no permitió consultar su API desde esta sesión; no se cambió ni reinició ningún servicio.

## 5. Paquete recomendado para el informe

Prioridad: **HU-01 + HU-02**, acompañadas de seguridad como avance parcial. Por cada historia adjuntar: criterio Given/When/Then, configuración y procedencia simulada, pasos, resultado esperado/obtenido, captura UI, JSON correspondiente y veredicto. Registrar versión/commit de los componentes al ejecutar la aceptación final.

Texto sugerido, sujeto a completar las capturas: “Se validó la consulta actual e histórica de métricas de infraestructura en un entorno controlado con datos simulados. La solución permite seleccionar nodo, variable y período y conserva la procedencia de los datos. La validación no constituye todavía evidencia de predicción, ahorro energético ni operación sobre infraestructura universitaria real”.
