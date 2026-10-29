"""Generate editable PlantUML and render PNG/SVG locally, without uploading sources.

Python 3.10+, Java 21 and the PlantUML JAR in tools/ are sufficient.
Pillow is optional and only creates a small preview for visual inspection.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parent
STYLE = '''
skinparam backgroundColor #FFFFFF
skinparam defaultFontName SansSerif
skinparam defaultFontSize 14
skinparam shadowing false
skinparam roundCorner 12
skinparam packageStyle rectangle
skinparam ArrowColor #475569
skinparam ArrowFontSize 12
skinparam nodesep 35
skinparam ranksep 50
skinparam componentStyle rectangle
skinparam packageBorderColor #94A3B8
skinparam packageFontStyle bold
skinparam rectangleBorderColor #64748B
skinparam hexagonBorderColor #15803D
skinparam interfaceBorderColor #7C3AED
skinparam titleFontSize 25
skinparam titleFontColor #0F172A
skinparam noteBackgroundColor #FFF7ED
skinparam noteBorderColor #FDBA74
hide stereotype
'''

SERVICES = [
    dict(id='mon', title='01  MONITORING | Java / Spring MVC',
         incoming='ADAPTADOR DE ENTRADA [C]\\nMetricsController + validación HTTP\\n/api/v1/metrics/{catalog,current,history}',
         pin='PUERTO DE ENTRADA [C]\\nQueryMetrics',
         app='APLICACIÓN [C]\\nMonitoringService\\nconsultar · normalizar · acotar',
         domain='DOMINIO [C]\\nMetricCatalog / MetricQuery / MetricData\\nunidades · identidad · origen · calidad',
         pout='PUERTOS DE SALIDA [C]\\nMetricsSource + Clock (JDK)',
         adapter='ADAPTADORES DE SALIDA [C]\\nPrometheusMetricsSource / HttpClient\\nFixture / Unavailable / BoundedMetricsSource',
         extra='ENSAMBLAJE: MonitoringConfiguration [C]\\nNúcleo independiente de Spring y Prometheus.'),
    dict(id='dp', title='02  DATA PROCESSING | Python / FastAPI',
         incoming='ADAPTADORES DE ENTRADA [C]\\nroutes.py + CLI ETL\\n/api/v1/metrics/history · historical-logs\\n/api/v1/prediction/dataset',
         pin='PUERTOS DE ENTRADA [H]\\nProcesar histórico / preparar dataset\\nHoy: métodos execute de casos de uso',
         app='APLICACIÓN [C]\\nProcessMetrics / ReadHistoricalLogs\\nPreparePredictionDataset / ProcessGreenAIDataset',
         domain='DOMINIO [C]\\nmonitoring_contract / validation / errors\\nidentidad · unidades · reglas de datos',
         pout='PUERTOS DE SALIDA [C]\\nMetricsSource / HistoricalLogsSource\\nDatasetSource / DatasetRepository',
         adapter='ADAPTADORES EXTERNOS [C]\\nMonitoringHttpAdapter / SupabaseHistoricalLogsAdapter\\nGreenAIExcelAdapter / CsvDatasetRepository',
         extra='ENSAMBLAJE: main.py + routes.py [C]\\nLa ruta Monitoring instancia su adaptador directamente.\\ninput/ del repositorio incluye lectores externos.'),
    dict(id='pred', title='03  PREDICTION | Python / FastAPI',
         incoming='ADAPTADORES DE ENTRADA [C]\\nservice/app.py + adapt_input + CLI\\nPOST /v1/predictions',
         pin='PUERTO DE ENTRADA [H]\\nPredecir demanda computacional\\nHoy: predict_from_payload',
         app='APLICACIÓN [C]\\ninference/predict.py\\nvalidar ventana · preparar features · inferir',
         domain='NÚCLEO ML [C] / AISLAMIENTO [H]\\nesquema · reglas temporales · horizonte\\nimplementación usa pandas / numpy / modelos',
         pout='PUERTOS DE SALIDA [H]\\nRepositorio de modelos / motor de inferencia\\nAbstracciones por extraer',
         adapter='INTEGRACIONES ACTUALES [C]\\nload_selected_model / joblib / metadata JSON\\nmodel.predict / adapt_output',
         extra='Hoy la inferencia carga archivos directamente.\\nHexágono = separación objetivo, no pureza ya lograda.\\nSin acceso a Prometheus ni Supabase.'),
    dict(id='sim', title='04  SIMULATOR | Python / CLI',
         incoming='ADAPTADOR DE ENTRADA [C]\\nCLI argparse: validate / run\\nSin API REST de control de runs',
         pin='PUERTO DE ENTRADA [H]\\nEjecutar simulación\\nHoy: función run_simulation',
         app='APLICACIÓN [C]\\nrunner.py\\nsemilla · tick · duración · offline/realtime',
         domain='DOMINIO [C]\\nInventory / Scenario / EngineState\\ncompute_next_state / derive_noise',
         pout='PUERTOS DE SALIDA [H]\\nInventario / registro / publicar snapshot\\nAbstracciones por extraer',
         adapter='ADAPTADORES [C]\\nJSON parsers / RunLogger / SimulatorCollector\\nHTTP /metrics: lectura del snapshot',
         extra='runner.py construye adaptadores concretos.\\nDominio usa biblioteca estándar de Python.\\nResultados siempre origin=simulated.'),
]

def service(s):
    p = s['id']
    # Dependency direction is towards application-owned contracts and domain.
    return f'''package "{s['title']}" as {p}_box #F8FAFC {{
  rectangle "{s['incoming']}" as {p}_in #DBEAFE
  package "NÚCLEO Y CONTRATOS" as {p}_core #F0FDF4 {{
    rectangle "{s['pin']}" as {p}_pi #EDE9FE
    rectangle "{s['app']}" as {p}_app #DCFCE7
    hexagon "{s['domain']}" as {p}_dom #BBF7D0
    rectangle "{s['pout']}" as {p}_po #EDE9FE
    {p}_app .up.|> {p}_pi : realiza contrato*
    {p}_app -down-> {p}_dom : usa
    {p}_app -right-> {p}_po : requiere*
  }}
  rectangle "{s['adapter']}" as {p}_out #DBEAFE
  {p}_in -down-> {p}_pi : invoca*
  {p}_out .up.|> {p}_po : implementa*
  {p}_dom -[hidden]down-> {p}_out
  note bottom of {p}_out
    {s['extra'].replace(chr(92)+'n', chr(10)+'    ')}
  end note
}}
'''

def build_main():
    parts = ['@startuml diagrama-hibrido', STYLE,
        'title GREEN AI | Microservicios + arquitectura hexagonal\\nVista general actual y separación objetivo · 01 octubre 2026',
        '''rectangle "FRONTEND [C]\\nUI + adaptador HTTP\\n1. GET dataset → 2. POST predicción" as fe #DBEAFE
package "API GATEWAY [C] | Spring Cloud Gateway / WebFlux" as edge #EFF6FF {
 rectangle "ENTRADA HTTP\\nJWT · roles · CORS · Request ID" as gw_in #DBEAFE
 rectangle "POLÍTICA DE ENRUTAMIENTO\\nallowlist · prefijos · timeouts\\nSin dominio analítico ni SQL" as gw_policy #DCFCE7
 rectangle "SALIDA HTTP\\nProxy a rutas aprobadas" as gw_out #DBEAFE
 gw_in -right-> gw_policy
 gw_policy -right-> gw_out
}
cloud "SUPABASE AUTH [C]\\nSesión / JWT / JWKS\\nDistinto de acceso a tablas" as auth #F1F5F9
fe -[#2563EB]-> gw_in : HTTPS + Bearer JWT
fe -[#2563EB]-> auth : login / refresh
gw_in -[#2563EB]-> auth : obtener claves JWKS
''']
    parts.append('together {')
    parts.extend(service(s) for s in SERVICES)
    parts.append('}')
    parts.append('sim_in -[hidden]right-> mon_in\nmon_in -[hidden]right-> dp_in\ndp_in -[hidden]right-> pred_in')
    parts.append('''database "PROMETHEUS [C]\\nSeries temporales / PromQL" as prom #FEF3C7
database "SUPABASE DATA / PostgreSQL\\nlogs: lectura por Data Processing [C]\\nhardware: inventario futuro [P]\\nusuario: fuera de métricas" as db #FEF3C7
folder "ARCHIVOS LOCALES [C]\\nSimulator: inventario + escenarios + JSONL\\nData Processing: Excel / CSV\\nPrediction: modelos + metadatos" as files #FEF3C7
node "WORKLOADS KUBERNETES [P]\\nExporters / métricas de aplicación\\nGrupo B e integración pendientes" as wk #FFF7ED
sim_out -[hidden]down-> prom
mon_out -[hidden]down-> db
pred_out -[hidden]down-> files
prom -[hidden]right-> db
db -[hidden]right-> files
gw_out -[#2563EB]-> mon_in : /api/monitoring/v1/*
gw_out -[#2563EB]-> dp_in : /api/processing/v1/*
gw_out -[#2563EB]-> pred_in : /api/prediction/v1/predictions
dp_out -[#2563EB,norank]-> mon_in : REST interno / history
dp_out -[#2563EB]-> db : PostgREST / logs\\nrequiere configuración y permisos
mon_out -[#2563EB]-> prom : query / query_range
prom -[#2563EB,norank]-> sim_out : scrape /metrics
prom -[#D97706,dashed]-> wk : scrape previsto
sim_out -[#D97706,dashed]-> db : lectura hardware futura
sim_out -[#2563EB]-> files : JSON / JSONL
dp_out -[#2563EB]-> files : ETL Excel / CSV
pred_out -[#2563EB]-> files : modelo / metadata
legend bottom
  |= Lectura del diagrama |= Significado |
  | [C] | Existe código o configuración local; no afirma validación en ejecución |
  | [H] | Separación hexagonal propuesta; no implica una interfaz ya implementada |
  | [P] | Integración pendiente |
  | Azul continuo | Solicitud HTTP o E/S: la flecha indica quién la inicia |
  | Gris continuo | Uso o dependencia interna; apunta al contrato o dominio |
  | Triángulo discontinuo | Realización del contrato; * conceptual donde figura [H] |
  | Naranja discontinuo | Comunicación futura |
  | Verde / violeta / azul claro | Núcleo / puertos / adaptadores |
  No hay llamada directa Data Processing → Prediction: el frontend coordina dos solicitudes vía Gateway.
  El dominio no debe depender de HTTP/BD; el aislamiento aún es parcial en Prediction y el ensamblaje de Simulator.
  Configuración, health, OpenAPI y observabilidad son infraestructura transversal; no reglas del dominio.
endlegend
@enduml
''')
    return '\n'.join(parts)

def build_detail(s):
    return '\n'.join(['@startuml detalle-' + s['id'], STYLE,
        'title ' + s['title'] + '\\nSeparación de responsabilidades y dependencias',
        service(s),
        '''legend bottom
 [C] código existente · [H] contrato/separación objetivo
 Flechas: dependencia hacia el núcleo. Triángulo: realización de contrato.
 * En puertos [H], la relación es propuesta; hoy existen llamadas concretas.
 El flujo de ejecución de salida va del caso de uso al adaptador mediante el puerto.
 No confundir flujo de llamadas con dirección de dependencia del código.
endlegend
@enduml'''])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jar', type=Path, default=ROOT/'tools'/'plantuml-1.2025.10.jar')
    parser.add_argument('--java', default='java')
    parser.add_argument('--render-only', action='store_true', help='Preserve manual edits to .puml files')
    args = parser.parse_args()
    if not args.jar.is_file():
        parser.error(f'PlantUML JAR not found: {args.jar}')
    names = ['diagrama-hibrido'] + ['detalle-' + s['id'] for s in SERVICES]
    if not args.render_only:
        (ROOT/'diagrama-hibrido.puml').write_text(build_main(), encoding='utf-8')
        for s in SERVICES:
            (ROOT/f"detalle-{s['id']}.puml").write_text(build_detail(s), encoding='utf-8')
    sources = [str(ROOT/(name+'.puml')) for name in names]
    for fmt in ['svg', 'png']:
        result = subprocess.run([args.java, '-Djava.awt.headless=true', '-DPLANTUML_LIMIT_SIZE=20000',
            '-jar', str(args.jar.resolve()), '-charset', 'UTF-8', '-failfast2', '-t'+fmt, *sources],
            capture_output=True, text=True, encoding='utf-8', errors='replace')
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
    for name in names:
        for fmt in ['svg','png']:
            path = ROOT/(name+'.'+fmt)
            if not path.exists() or path.stat().st_size < 100:
                raise RuntimeError(f'Missing/empty output: {path}')
    report = dict(plantuml_jar=args.jar.name,
                  jar_sha256=hashlib.sha256(args.jar.read_bytes()).hexdigest(),
                  sources={Path(p).name:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sources})
    try:
        from PIL import Image
        with Image.open(ROOT/'diagrama-hibrido.png') as img:
            report['size'] = img.size
            img.thumbnail((1800,1800))
            img.save(ROOT/'vista-previa.png')
    except ImportError:
        pass
    (ROOT/'generacion.json').write_text(json.dumps(report,indent=2), encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__ == '__main__':
    main()
