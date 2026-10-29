# Arquitectura híbrida de Green AI

Diagrama general de microservicios con separación hexagonal interna, basado en la imagen original y en el código local revisado el **1 de octubre de 2026**. La imagen original `project-docs/diagrama.png` se conserva.

## Abrir los resultados

- [Diagrama general en SVG](diagrama-hibrido.svg): formato vectorial recomendado para ampliar y presentar.
- [Diagrama general en PNG](diagrama-hibrido.png): imagen de alta resolución.
- [Fuente PlantUML general](diagrama-hibrido.puml).
- [Generador Python](generar_diagrama.py).

Para estudiar los detalles sin reducir todo a una sola pantalla:

| Servicio | Imagen | Vector | Fuente editable |
| --- | --- | --- | --- |
| Monitoring | [PNG](detalle-mon.png) | [SVG](detalle-mon.svg) | [PlantUML](detalle-mon.puml) |
| Data Processing | [PNG](detalle-dp.png) | [SVG](detalle-dp.svg) | [PlantUML](detalle-dp.puml) |
| Prediction | [PNG](detalle-pred.png) | [SVG](detalle-pred.svg) | [PlantUML](detalle-pred.puml) |
| Simulator | [PNG](detalle-sim.png) | [SVG](detalle-sim.svg) | [PlantUML](detalle-sim.puml) |

## Qué significa híbrido

La vista exterior separa procesos y servicios que se comunican mediante HTTP o E/S. La vista interior distingue adaptadores de entrada, puertos de entrada, aplicación, dominio, puertos de salida y adaptadores externos. No se introduce un único dominio compartido entre todos los microservicios.

La separación hexagonal busca que la aplicación converse con el exterior a través de contratos y mantenga su lógica desacoplada de tecnologías externas. El número de lados del dibujo no exige seis interfaces. Referencia conceptual: [arquitectura hexagonal de Alistair Cockburn](https://alistair.cockburn.us/hexagonal-architecture).

Gateway se representa como infraestructura de entrada con políticas y proxy. No se le inventa un dominio analítico ni un conjunto de interfaces inexistentes para obligarlo a parecerse a Monitoring. Prometheus, Supabase y los archivos permanecen fuera de los núcleos.

## Leyenda y dirección de las flechas

- **[C]**: existe código o configuración local. No significa que se haya ejecutado una prueba de integración en esta tarea.
- **[H]**: abstracción o separación hexagonal propuesta. El nombre describe una responsabilidad, no necesariamente una clase o interfaz existente.
- **[P]**: comunicación pendiente de implementación.
- **Verde**: aplicación y dominio. **Violeta**: puertos. **Azul claro**: adaptadores. **Amarillo**: persistencia y sistemas de datos.
- **Flecha azul**: solicitud HTTP o acceso a archivos. Señala quién inicia la operación; las respuestas regresan por la misma conexión.
- **Flecha gris**: uso o dependencia interna hacia el núcleo o contrato.
- **Triángulo discontinuo**: realización de un contrato. Donde el puerto lleva [H], muestra la relación objetivo, no una declaración `implements` ya existente.
- **Flecha naranja discontinua**: integración futura.

En el flujo de ejecución, la aplicación llama al puerto de salida y el adaptador ejecuta la operación. En la dependencia de código, el adaptador implementa el contrato del núcleo. Por eso la realización apunta **del adaptador al puerto**, aunque la llamada en ejecución salga de la aplicación.

El asterisco recuerda que algunas relaciones son conceptuales. En Monitoring, `Clock` es una abstracción del JDK inyectada, no una interfaz propia implementada por Prometheus. El bloque agrupa varias alternativas: no significa que cada adaptador implemente todos los puertos listados.

Los prefijos `/*` de las flechas externas son abreviaturas de familias de rutas. No indican que Gateway acepte rutas comodín: la configuración contiene una lista explícita de paths y métodos.

## Estado real de la separación interna

### Monitoring

`MetricsController` invoca `QueryMetrics`, implementado por `MonitoringService`. La aplicación utiliza `MetricsSource`, con implementaciones Prometheus, fixture y fuente no disponible, además del decorador de límites. `MonitoringConfiguration` ensambla las dependencias. El dominio no depende de Spring, HTTP ni Prometheus.

### Data Processing

Existen casos de uso, tipos y validación de dominio, así como puertos `MetricsSource`, `HistoricalLogsSource`, `DatasetSource` y `DatasetRepository`. La lectura de históricos se inyecta en `ReadHistoricalLogsUseCase`. Sin embargo, las rutas de métricas construyen y llaman `MonitoringHttpAdapter` directamente antes de invocar el procesamiento: el recorrido uniforme mediante puertos es la separación objetivo, no un reflejo exacto de todas las llamadas actuales.

La carpeta `infrastructure/adapters/input` contiene lectores de Monitoring, Supabase y Excel. En el diagrama se clasifican por su papel **respecto al núcleo**: un lector de fuente externa es un adaptador secundario o de salida desde la perspectiva de la aplicación, aunque los datos entren al sistema. La ubicación de la carpeta no cambia esa distinción.

### Prediction

Existen API FastAPI, adaptación del payload, inferencia y carga de modelos. Los puertos de entrada/salida dibujados son responsabilidades que podrían extraerse como contratos explícitos. `inference/predict.py` importa joblib, pandas y numpy y carga archivos; no se representa como un núcleo puro ya aislado. El hexágono señala reglas y responsabilidades que se desea separar, no una refactorización realizada.

### Simulator

La CLI conduce `run_simulation`. El dominio contiene inventario, escenario, estado y motor determinista. `runner.py` construye los adaptadores concretos. Los contratos para inventario, registro y publicación de snapshots son propuestos; hoy no existen como interfaces explícitas equivalentes a `MetricsSource` de Monitoring.

`SimulatorCollector` es un adaptador de publicación del estado y atiende lecturas HTTP de Prometheus. La petición de scrape termina en ese adaptador: no inicia un nuevo run ni hace avanzar el motor por sí misma. Por eso aparece la flecha Prometheus → exporter, aunque el exporter se agrupe entre las salidas del caso de uso de simulación.

## Cambios respecto a la imagen original

1. **Data Processing y Prediction tienen código de API y rutas en Gateway.** Ya no se muestran ambos únicamente como futuros.
2. **La autenticación está separada de la BD.** Frontend utiliza Supabase Auth para sesión; Gateway valida JWT y obtiene claves JWKS. Esto no permite acceso del navegador a tablas.
3. **Data Processing tiene un lector de logs de Supabase.** Su uso depende de configuración y permisos. No se afirma una consulta exitosa en vivo.
4. **Prediction no es llamado directamente por Data Processing en el recorrido actual del frontend.** `prediction.js` obtiene el dataset mediante Gateway y después envía otra petición de inferencia, también mediante Gateway. Una llamada interna DP → Prediction requeriría un adaptador/orquestación adicional.
5. **Simulator conserva lectura de inventario desde archivos.** Su futura conexión directa a hardware de Supabase sigue discontinua.
6. **Workloads Kubernetes sigue siendo una fuente prevista.** El diagrama no afirma despliegue Kubernetes ni métricas Grupo B ya implementadas.

No se dibujan escrituras a Supabase desde Monitoring, Prediction, Simulator o Gateway. Tampoco se agrega un flujo de predicción que actúe automáticamente sobre Kubernetes.

## Cómo regenerar

Requisitos: Python 3.10 o superior y Java accesible mediante `java`. Se descargó PlantUML **1.2025.10** desde [Maven Central](https://repo.maven.apache.org/maven2/net/sourceforge/plantuml/plantuml/1.2025.10/) y se conserva en `tools`. La instalación local de PlantUML encontró Graphviz disponible al ejecutar `-testdot`. En otro equipo, si no se encuentra Graphviz, debe instalarse/configurarse para el layout usado.

Desde la raíz del workspace:

```powershell
python project-docs/arquitectura-hibrida/generar_diagrama.py
```

El script escribe los cinco archivos `.puml` y llama localmente a PlantUML para generar PNG y SVG. Pillow es opcional y solo produce una vista previa reducida. No se envía el diagrama a un servidor de renderizado.

Para editar PlantUML manualmente y renderizar sin sobrescribir esas ediciones:

```powershell
python project-docs/arquitectura-hibrida/generar_diagrama.py --render-only
```

Para cambios permanentes en los nombres o la organización, se puede editar la estructura `SERVICES` y `build_main()` del generador. Los hashes del JAR y de las fuentes se registran en `generacion.json` para identificar los archivos empleados; ese registro no es una certificación de la aplicación.

La sintaxis de cajas, hexágonos, paquetes y relaciones utiliza los [elementos de PlantUML](https://plantuml.com/deployment-diagram).

## Fuentes locales revisadas

- `docker-compose.yml` del workspace.
- `green-ai-gateway/src/main/resources/application.yaml` y `SecurityConfiguration.java`.
- Paquetes `domain`, `application`, `adapter` y `configuration` de Monitoring.
- `green-ai-data-processing/Green-IA/data-processing-service/domain/ports`, `application/use_cases` e `infrastructure/adapters/input/api/routes.py`.
- `green-ai-prediction/green-ai-project-docs/src/service/app.py` y `src/inference/predict.py`.
- `green-ai-simulator/src/green_ai_simulator/domain`, `application/runner.py` y `adapters`.
- `green-ai-front-end/Frontend-GreenAi/prediction.js` y `app.js`.
- `project-docs/AUTENTICACION-JWT.md` y la imagen original.

Los documentos previos de septiembre describen etapas anteriores; cuando difieren del código observado, esta vista identifica expresamente la actualización. No se modificó código de los servicios ni su configuración de despliegue.
