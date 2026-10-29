"""Genera el PDF completo y el Gantt. Requiere ReportLab, Pillow, Java y PlantUML."""
from pathlib import Path
import re, html, subprocess, base64
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage

ROOT = Path(__file__).resolve().parents[2]
ASSETS = Path(__file__).resolve().parent
OUT = ROOT / 'output/pdf/4. Gestion de Proyecto.pdf'
SOURCE = ROOT / 'project-docs/4. Gestión de Proyecto.md'
JAR = ROOT / 'project-docs/arquitectura-hibrida/tools/plantuml-1.2025.10.jar'
for fmt in ['svg', 'png']:
    subprocess.run(['java', '-Djava.awt.headless=true', '-jar', str(JAR), '-charset', 'UTF-8', '-failfast2', '-t'+fmt, str(ASSETS/'cronograma.puml')], check=True)

for name, file in [('Arial','arial.ttf'),('Arial-Bold','arialbd.ttf'),('Arial-Italic','ariali.ttf'),('Arial-BoldItalic','arialbi.ttf'),('Mono','consola.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(Path('C:/Windows/Fonts')/file)))
pdfmetrics.registerFontFamily('Arial',normal='Arial',bold='Arial-Bold',italic='Arial-Italic',boldItalic='Arial-BoldItalic')
BLUE=colors.HexColor('#163D58'); GREEN=colors.HexColor('#087F72')
W,H=A4; WIDTH=W-86
styles={
 'body':ParagraphStyle('body',fontName='Arial',fontSize=9.5,leading=13.5,spaceAfter=6,textColor=colors.HexColor('#243746')),
 'title':ParagraphStyle('title',fontName='Arial-Bold',fontSize=25,leading=30,spaceAfter=17,textColor=BLUE),
 'h2':ParagraphStyle('h2',fontName='Arial-Bold',fontSize=15,leading=20,spaceBefore=17,spaceAfter=9,textColor=BLUE,keepWithNext=True),
 'h3':ParagraphStyle('h3',fontName='Arial-Bold',fontSize=11.5,leading=15,spaceBefore=11,spaceAfter=6,textColor=GREEN,keepWithNext=True),
 'cell':ParagraphStyle('cell',fontName='Arial',fontSize=8.2,leading=11,spaceAfter=0),
 'head':ParagraphStyle('head',fontName='Arial-Bold',fontSize=8.2,leading=11,textColor=colors.white),
 'caption':ParagraphStyle('caption',fontName='Arial-Italic',fontSize=8,leading=11,spaceAfter=10,textColor=colors.HexColor('#526777')),
 'tree':ParagraphStyle('tree',fontName='Mono',fontSize=7.2,leading=10,spaceAfter=1),
}
def clean(s):
    s=re.sub(r'\\([\\`*_{}\[\]()#+.!<>|\-])',r'\1',s)
    return s.replace('—','-').replace('–','-').replace('\u2011','-').replace('referência','referencia')
def inline(s):
    s=html.escape(clean(s))
    s=re.sub(r'\*\*(.+?)\*\*',r'<b>\1</b>',s)
    s=re.sub(r'\*(.+?)\*',r'<i>\1</i>',s)
    s=re.sub(r'`([^`]+)`',r'<font name="Mono">\1</font>',s)
    s=re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+)\)',r'<link href="\2" color="#087F72">\1</link>',s)
    return s
def p(s,kind='body'): return Paragraph(inline(s),styles[kind])
def fig(path,caption):
    im=PILImage.open(path); iw,ih=im.size
    scale=min(WIDTH/iw,580/ih)
    return [Image(str(path),width=iw*scale,height=ih*scale),Spacer(1,5),p(caption,'caption')]

text=SOURCE.read_text(encoding='utf-8')
for name,data in re.findall(r'\[(image\d+)\]:\s*<?data:image/[^;]+;base64,([^>\s]+)',text):
    (ASSETS/(name+'.png')).write_bytes(base64.b64decode(data))
text=re.sub(r'^\[image\d+\]:.*$', '',text,flags=re.M)
lines=text.splitlines(); story=[]; i=0; tables=0
while i<len(lines):
    line=lines[i].strip(); i+=1
    if not line: continue
    if i==1:
        story += [p('GREEN AI','h3'),p('4. Gestión del Proyecto','title'),p('Documento de planificación | Cronograma de 16 semanas','caption')]
        continue
    if line.startswith('|'):
        raw=[line]
        while i<len(lines) and lines[i].strip().startswith('|'):
            raw.append(lines[i].strip()); i+=1
        rows=[]
        for r in raw:
            cells=re.split(r'(?<!\\)\|',r.strip('|'))
            if all(re.fullmatch(r'\s*:?-+:?\s*',c) for c in cells):continue
            rows.append(cells)
        n=max(map(len,rows))
        weights=[1]*n
        if n==2:weights=[.32,.68]
        elif n==3:weights=[.23,.385,.385]
        elif n==4:weights=[.23,.20,.285,.285]
        elif n==5:weights=[.16,.25,.18,.17,.24]
        widths=[WIDTH*x/sum(weights) for x in weights]
        data=[[p(c,'head' if rn==0 else 'cell') for c in (row+['']*(n-len(row)))] for rn,row in enumerate(rows)]
        tab=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT',splitByRow=1)
        tab.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),BLUE),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F1F6F8')]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,0),(-1,0),.8,GREEN),('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#DCE5E9'))]))
        story += [tab,Spacer(1,10)]; tables+=1;continue
    match=re.search(r'!\[.*?\]\[(image\d+)\]',line)
    if match:
        if match[1]=='image1':
            story += [PageBreak(),p('4.8 - Gantt del cronograma planificado','h2'),p('Diagrama generado con PlantUML a partir de las fechas de la tabla del cronograma. Cada barra representa la ventana estimada de un sprint; los hitos señalan la revisión prevista de cada PMV. No se atribuyen porcentajes de avance ni resultados realizados.'),*fig(ASSETS/'cronograma.png','Gantt añadido: 25 de agosto a 12 de diciembre de 2026. Fuente editable: cronograma.puml.'),p('Lectura del cronograma','h3'),p('PMV1: sprints 1-3, del 25/08 al 03/10. PMV2: sprints 4-6, del 06/10 al 14/11. PMV3: sprints 7-8, del 17/11 al 12/12. Se conservan las ventanas de fechas del documento, incluidos los intervalos entre sprints.'),PageBreak(),p('Cronograma original de referencia','h3')]
        story += fig(ASSETS/(match[1]+'.png'),'Figura original del documento. Su resolución de origen limita el detalle; el contenido se complementa con las tablas y el desarrollo textual.')
        continue
    if line.startswith('#'):
        level=len(line)-len(line.lstrip('#'))
        story.append(p(line.lstrip('# ').replace('**',''),'h2' if level==2 else 'h3'));continue
    if line.startswith(('├','│','└','0. GREEN','0\\. GREEN')):
        tree=clean(line)
        story.append(Paragraph(html.escape(tree).replace(' ','&nbsp;'),styles['tree']));continue
    if re.fullmatch(r'\*\*.+\*\*',line) and len(line)<170:
        story.append(p(line,'h3'));continue
    if line.startswith('* '):
        story.append(p('• '+line[2:]));continue
    story.append(p(line))

story += [PageBreak(),p('Anexo - Observaciones de revisión','h2'),p('Estas observaciones corresponden a una revisión de coherencia del documento de planificación. No certifican el avance de la implementación. Se conserva el contenido original, con normalización tipográfica y el Gantt añadido.'),p('1. Alinear el sprint de infraestructura Kubernetes','h3'),p('La sección 4.8 sitúa el despliegue de Kubernetes en el Sprint 1; la tabla 4.15.2 asigna Infraestructura Kubernetes al Sprint 2. Conviene distinguir preparación y despliegue, o unificar la asignación. El Gantt añadido sigue la sección 4.8.'),p('2. Unificar la definición del baseline','h3'),p('El cronograma y la EDT mencionan ARIMA / media móvil; el alcance de 4.16.1 identifica naive/persistencia como baseline. Debe precisarse cuál será la referencia oficial y qué modelos son comparaciones adicionales.'),p('3. Operacionalizar la meta de precisión','h3'),p('La meta de precisión de al menos 90% aparece junto con MAE, RMSE y sMAPE. Es necesario definir la fórmula que corresponde a ese porcentaje, los umbrales de cada métrica, las variables, unidades, horizonte de predicción y conjunto de evaluación; no son indicadores intercambiables.'),p('4. Diferenciar proyecciones y resultados','h3'),p('Los registros por completar o por registrar y los datos proyectados deben mantenerse como pendientes hasta contar con evidencias. El Gantt muestra planificación, no ejecución comprobada. Los objetivos de ahorro tampoco equivalen a resultados obtenidos.'),p('5. Confirmar la coherencia entre vistas del cronograma','h3'),p('El Gantt nuevo toma las fechas explícitas de la tabla de la sección 4.8. La imagen original se conserva como referencia; cualquier discrepancia de su detalle deberá reconciliarse con la tabla antes de aprobar una línea base definitiva.'),p('6. Ajustar la regla de inclusión en el alcance','h3'),p('La sección 4.16.2 admite un elemento cuando cumple al menos dos criterios. Esa regla podría incluir trabajo que exceda el plazo o requiera intervenir producción si cumple otros dos criterios. Conviene hacer obligatorias las restricciones de entorno, plazo y presupuesto, y aplicar después los criterios de valor y requisitos.')]

def footer(c,doc):
    c.saveState();c.setStrokeColor(colors.HexColor('#DCE5E9'));c.line(43, H-35,W-43,H-35)
    c.setFont('Arial',8);c.setFillColor(BLUE);c.drawString(43,H-27,'GREEN AI  /  GESTIÓN DEL PROYECTO')
    c.setFont('Arial',7.5);c.setFillColor(colors.HexColor('#526777'));c.drawString(43,25,'Planificación, entregas y validación experimental');c.drawRightString(W-43,25,str(doc.page));c.restoreState()
OUT.parent.mkdir(parents=True,exist_ok=True)
doc=SimpleDocTemplate(str(OUT),pagesize=A4,rightMargin=43,leftMargin=43,topMargin=49,bottomMargin=43,title='Green AI - Gestión del Proyecto',author='Equipo Green AI',allowSplitting=1)
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(f'PDF: {OUT}; tablas: {tables}')
