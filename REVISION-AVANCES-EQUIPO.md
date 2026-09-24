# Revisión de avances de los equipos

Fecha: 2026-09-23. Alcance revisado: copias locales de `green-ai-data-processing`, `green-ai-front-end` y `green-ai-prediction`. Esta revisión compara el código disponible con los contratos generales; no declara integración ejecutada.

## Estado resumido

| Componente | Estado comprobado | Falta para integrarlo |
| --- | --- | --- |
| Data Processing | ETL por lotes desde Excel a CSV y endpoint de salud | Adaptadores de Monitoring y Supabase, contrato JSON con Prediction, API/OpenAPI y contenedor |
| Frontend | Prototipo estático con navegación, gráficos y sesión local demostrativa | Consumir Gateway, retirar datos inventados, implementar Supabase Auth/JWT y estados contractuales |
| Prediction | Núcleo ML e inferencia fuera de línea sobre fixture | Corregir validación experimental, acordar entrada con Data Processing y exponer un servicio reproducible |

## Falencias prioritarias
### P0 — Bloquean el ensamblaje

1. **Data Processing y Prediction no comparten el mismo contrato.** Data Processing genera un CSV tabular de 14 columnas; Prediction espera un JSON versionado con metadatos y registros temporales. Deben acordar un JSON Schema/OpenAPI único, unidades, frecuencia, horizontes, procedencia, calidad y comportamiento ante huecos.
2. **Data Processing todavía no consume las fuentes reales del diseño.** Solo existe un adaptador Excel y salida CSV. Faltan el cliente HTTP de Monitoring, el lector autorizado de históricos de Supabase y la trazabilidad que preserve recurso, timestamp, unidad, `origin`, `quality` y `dataStatus`.
3. **Prediction aún no es un microservicio.** No tiene FastAPI, OpenAPI, health/readiness ni Dockerfile. La inferencia actual requiere que el llamador construya las features del modelo y puede devolver `resource` y `predictedFor` nulos; faltan `predictionId` y `generatedAt`.
4. **La validación del modelo no permite afirmar que esté listo.** La selección utiliza TEST y dos aserciones anti-leakage terminan en `or True`. Deben corregirse la separación TRAIN/VALIDATION/TEST, la purga temporal entre fronteras y las pruebas anti-leakage antes de publicar métricas de desempeño.
5. **Frontend sigue conectado al backend experimental.** Consume `/api/login`, `/api/registro`, `/api/kpis`, `/api/hardware`, `/api/logs` y `/api/usuarios`, mientras Gateway solo publica las rutas confirmadas de Monitoring. La sesión basada en un objeto `usuarioLogueado` de `localStorage` no autentica ninguna petición.
6. **Hay datos visuales que parecen reales sin serlo.** El gráfico mensual contiene valores fijos en kWh, las vistas de red generan 50 servidores de respaldo y varios campos ausentes se convierten a cero. Todo fallback debe mostrar la etiqueta `DEMO` o retirarse del modo integrado; `null`, cero y error son estados distintos.
7. **El esquema de usuarios actual no es apto para autenticación.** `public.usuario` obliga a almacenar `password` y `password_hash`, y las políticas RLS permiten todo al rol `public`. Las credenciales deben migrarse a Supabase Auth y las políticas deben cerrarse antes de usar datos reales.

### P1 — Necesarios para una integración verificable

- Data Processing: README vacío, configuración externa, manejo de errores, request ID, límites de consulta, OpenAPI, Dockerfile, liveness/readiness y salida que no dependa de rutas locales.
- Data Processing: no descartar filas con `dropna()` sin producir un reporte de calidad; no mezclar el origen sintético del Excel con datos observados.
- Prediction: fijar Python y dependencias de forma reproducible, verificar hashes de artefactos, ejecutar suite/cobertura y cargar el mismo preprocesamiento durante entrenamiento e inferencia.
- Frontend: un adaptador HTTP único para Gateway, configuración de URL por ambiente, `Authorization: Bearer`, renovación de sesión y manejo de 401/403, `application/problem+json`, `X-Request-Id`, carga, parcial y `no_data`.
- Frontend: poblar selectores desde el catálogo de Monitoring; mostrar recurso, periodo, unidad, `origin` y `quality`; distinguir mediciones de predicciones.
- Repositorios: eliminar directorios envolventes y copias de documentación general dentro de los servicios. Cada repositorio debe abrir en su raíz real y contener solo su servicio, README y contrato propietario.

### P2 — Mejoras posteriores

- Jobs asíncronos y persistencia de datasets de Data Processing.
- Operación de inferencia y consulta de predicciones a través del Gateway después de aprobar su OpenAPI.
- Autenticación de servicio a servicio, revocación inmediata para operaciones sensibles, auditoría y MFA.
- Inventario real y vistas de topología cuando exista un contrato propietario; no deducirlos de las series de Monitoring.

## Orden recomendado

1. Aplicar la decisión de autenticación descrita en [AUTENTICACION-JWT.md](AUTENTICACION-JWT.md).
2. Conectar Frontend con las tres rutas actuales de Monitoring a través de Gateway y retirar fallbacks engañosos.
3. Cerrar el contrato Data Processing → Prediction con un fixture compartido y pruebas de contrato en ambos repositorios.
4. Implementar los adaptadores de entrada de Data Processing y su API externa.
5. Corregir la evaluación de Prediction y envolver el núcleo validado en un servicio HTTP.
6. Registrar en Gateway únicamente rutas cuyos OpenAPI ya estén aprobados.
