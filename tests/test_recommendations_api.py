import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient
from src.service.app import app


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        now = datetime.now(timezone.utc)
        self.resource = {'type': 'node', 'id': 'n1', 'cluster': 'lab'}
        self.prediction = dict(resource=self.resource, inputDatasetId='ds1',
            predictionId='p1', target='cpu_utilization', unit='%', origin='estimated',
            value=25, generatedAt=now.isoformat(), predictedFor=(now + timedelta(minutes=15)).isoformat())
        self.payload = dict(dataset=dict(datasetId='ds1', resource=self.resource, features=[{}]),
            telemetry=dict(resource=self.resource, observedAt=now.isoformat(),
                origin='simulated', memoryPercent=40, latencyP95Ms=100, errorRatePercent=0.1))

    def recommend(self):
        with patch('src.service.recommendations.predict_from_payload', return_value=self.prediction):
            return self.client.post('/v1/recommendations', json=self.payload)

    def test_complete_demo_requires_human_review(self):
        response = self.recommend()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['status'], 'eligible_for_review')
        self.assertEqual(body['action'], 'review_capacity_reduction')
        self.assertEqual(body['policy']['mode'], 'demonstration')
        self.assertFalse(body['executionAllowed'])

    def test_missing_data_is_not_evaluable(self):
        self.payload.pop('telemetry')
        body = self.recommend().json()
        self.assertEqual(body['status'], 'not_evaluable')
        self.assertEqual(body['action'], 'none')

    def test_limits_block_reduction(self):
        self.payload['telemetry']['latencyP95Ms'] = 900
        self.assertEqual(self.recommend().json()['status'], 'blocked')

    def test_stale_or_other_resource_is_not_evaluable(self):
        for change in [dict(observedAt='2020-01-01T00:00:00Z'),
                       dict(resource=dict(type='node', id='other', cluster='lab'))]:
            with self.subTest(change=change):
                original = self.payload['telemetry'].copy()
                self.payload['telemetry'].update(change)
                self.assertEqual(self.recommend().json()['status'], 'not_evaluable')
                self.payload['telemetry'] = original

    def test_prediction_mismatch_is_upstream_error(self):
        self.prediction['inputDatasetId'] = 'wrong'
        self.assertEqual(self.recommend().status_code, 502)

    def test_expired_prediction_is_not_evaluable(self):
        self.prediction['predictedFor'] = '2020-01-01T00:00:00Z'
        self.assertEqual(self.recommend().json()['status'], 'not_evaluable')

    def test_invalid_telemetry_rejected(self):
        self.payload['telemetry']['memoryPercent'] = -1
        self.assertEqual(self.recommend().status_code, 422)

    def test_nonfinite_and_missing_zone_rejected_without_server_error(self):
        payload = '{"origin":"simulated","samples":[{"timestamp":"2026-10-28T00:00:00Z","watts":NaN},{"timestamp":"2026-10-28T00:01:00Z","watts":10}]}'
        self.assertEqual(self.client.post('/v1/energy', content=payload,
            headers={'Content-Type': 'application/json'}).status_code, 422)
        self.payload['telemetry']['observedAt'] = '2026-10-28T12:00:00'
        self.assertEqual(self.recommend().status_code, 422)

    def test_health_openapi_and_metrics(self):
        self.assertEqual(self.client.get('/health').status_code, 200)
        self.assertIn('/v1/energy', self.client.get('/openapi.json').json()['paths'])
        self.recommend()
        response = self.client.get('/metrics')
        self.assertIn('green_ai_recommendations_total', response.text)

    def test_unavailable_local_model_returns_service_unavailable(self):
        from src.exceptions import ModelNotFoundError
        with patch('src.service.recommendations.predict_from_payload',
                   side_effect=ModelNotFoundError('Model not available')) as predict:
            response = self.client.post('/v1/recommendations', json=self.payload)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(predict.call_count, 1)

    def test_energy_integrates_watts_and_preserves_origin(self):
        payload = dict(origin='simulated', samples=[
            dict(timestamp='2026-10-28T00:00:00Z', watts=100),
            dict(timestamp='2026-10-28T00:05:00Z', watts=200)],
            emissionFactorKgPerKwh=0.5, emissionFactorSource='demo')
        result = self.client.post('/v1/energy', json=payload)
        self.assertEqual(result.status_code, 200)
        self.assertAlmostEqual(result.json()['energyKwh'], 0.0125)
        self.assertAlmostEqual(result.json()['co2eKg'], 0.00625)
        self.assertEqual(result.json()['origin'], 'simulated')
        payload['samples'].reverse()
        self.assertEqual(self.client.post('/v1/energy', json=payload).status_code, 422)

    def test_energy_does_not_invent_carbon_factor_or_bridge_gaps(self):
        payload = dict(origin='observed', samples=[
            dict(timestamp='2026-10-28T00:00:00Z', watts=100),
            dict(timestamp='2026-10-28T00:05:00Z', watts=100)])
        self.assertIsNone(self.client.post('/v1/energy', json=payload).json()['co2eKg'])
        payload['samples'][1]['timestamp'] = '2026-10-28T01:00:00Z'
        self.assertEqual(self.client.post('/v1/energy', json=payload).status_code, 422)


if __name__ == '__main__':
    unittest.main()


def test_recommendations_use_local_inference_without_http(dataprocessing_payload):
    # The selected model in the test environment is a technical demonstration.
    with patch('httpx.AsyncClient.request', side_effect=AssertionError('No internal HTTP')):
        response = TestClient(app).post('/v1/recommendations', json={
            'dataset': dataprocessing_payload,
        })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['inputDatasetId'] == dataprocessing_payload['datasetId']
    assert body['resource'] == dataprocessing_payload['resource']
    assert 0 <= body['predictedCpuPercent'] <= 100
    assert body['status'] == 'not_evaluable'
    assert body['executionAllowed'] is False
