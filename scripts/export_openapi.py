"""Export Prediction and its compatibility routes exposed by Gateway."""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.service.app import app


def export(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    (output_dir / 'prediction.openapi.json').write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    external = copy.deepcopy(schema)
    external['info']['title'] = 'Prediction recommendations via Gateway'
    external['servers'] = [{'url': '/'}]
    external['security'] = [{'bearerAuth': []}]
    external['components']['securitySchemes'] = {
        'bearerAuth': {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT'}}
    external['paths'] = {'/api/recommendations' + path: value
        for path, value in external['paths'].items()
        if path in ('/v1/recommendations', '/v1/energy')}
    for path in external['paths'].values():
        for operation in path.values():
            operation['description'] = (
                'Responsabilidad de Prediction. JWT ADMIN/OPERATOR; máximo 2 MB, '
                'timeout 30 s y sin reintentos.')
            operation['responses'].update({str(code): {'description': message}
                for code, message in [(401, 'JWT ausente o inválido'),
                    (403, 'Rol insuficiente'), (413, 'Cuerpo demasiado grande'),
                    (504, 'Timeout del Gateway')]})
    (output_dir / 'recommendations-gateway.openapi.json').write_text(
        json.dumps(external, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    export(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'contracts')
