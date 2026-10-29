# Herramientas de Codex para Green AI

Instalación local realizada el 27 de octubre de 2026. No se modificó el perfil global de Codex ni el PATH de Windows.

| Herramienta | Instalación |
| --- | --- |
| Ponytail 5.3.2 | 6 skills locales; sin los hooks del plugin completo |
| Agent Skills | 25 skills, 7 referencias compartidas y 4 descripciones de revisores |
| Graphify 0.9.96 | CLI en `.tools/graphify`, una skill local y configuración del proyecto |

Las 32 skills están en `.agents/skills`. Se aplican a chats que usen esta carpeta como directorio de trabajo; no son exclusivas de una conversación. Los repositorios independientes abiertos directamente dentro de las subcarpetas pueden requerir su propia instalación local, porque el descubrimiento de skills se detiene en la raíz del repositorio.

## Uso en el chat

- «Usa Ponytail para este cambio».
- «Usa code-review-and-quality para revisar estos cambios».
- «Usa graphify para mapear este proyecto».

Codex puede seleccionar skills por su descripción. En CLI/IDE se pueden mencionar como `$ponytail`, `$graphify` o `$code-review-and-quality`. Esta instalación de Ponytail usa nombres de skills locales, sin el prefijo de plugin `ponytail:`. Si no aparecen después del siguiente mensaje, reinicia Codex y abre la misma carpeta.

## Graphify desde PowerShell

Desde la raíz de Green AI:

```powershell
& .\.tools\graphify\Scripts\graphify.exe --version
& .\.tools\graphify\Scripts\graphify.exe --help
```

Para código Python que importe Graphify, usa `.tools/graphify/Scripts/python.exe`. No hace falta activar el entorno ni instalar el paquete globalmente. El grafo del proyecto está disponible en `graphify-out/graph.json` y el visor en `graphify-out/graph.html`.

El instalador de Graphify creó `AGENTS.md` y `.codex/hooks.json`. El hook `hook-check` de esta versión es una operación sin efecto para Codex; las indicaciones de uso provienen de `AGENTS.md`. Se ajustaron las rutas para usar el ejecutable local y se trasladó la skill a `.agents/skills`, conservando sus referencias.

## Origen y verificación

- Ponytail: https://github.com/DietrichGebert/ponytail — commit `09c434ab73ca43761c5d8b0c5d341926c2fba710`.
- Agent Skills: https://github.com/addyosmani/agent-skills — commit `aeac41d4d005999432bb7312f7ff06383a91d59d`.
- Graphify: paquete PyPI `graphifyy==0.9.96`; dependencias exactas en `.tools/graphify-requirements.txt`.

Las skills de GitHub se instalaron con el instalador de skills de Codex, indicando `.agents/skills` como destino. Graphify se instaló con `uv venv`, `uv pip install --python .tools/graphify/Scripts/python.exe graphifyy` y se registró con `graphify install --project --platform codex`.

Verificación realizada: 32 nombres de skill únicos, metadatos YAML válidos, referencias compartidas presentes, ejecución de `graphify --version` y del hook local. No se ejecutaron los workflows de las skills ni se analizó el código del proyecto.
