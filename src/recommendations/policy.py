"""Demonstration policy, independent of HTTP and model loading."""
from datetime import datetime


def evaluate_policy(prediction: dict, telemetry: dict | None, limits: dict, now: datetime):
    checks = []
    def check(name, status):
        checks.append({"name": name, "status": status})

    age = (now - prediction['generatedAt']).total_seconds()
    fresh = 0 <= age <= limits['freshnessSeconds'] and now < prediction['predictedFor']
    check('prediction_freshness', 'pass' if fresh else 'unknown')
    valid = telemetry is not None and telemetry['resource'] == prediction['resource']
    if valid:
        age = (now - telemetry['observedAt']).total_seconds()
        valid = 0 <= age <= limits['freshnessSeconds']
    check('telemetry_identity_and_freshness', 'pass' if valid else 'unknown')
    for field, limit in [('memoryPercent', limits['memoryMaxPercent']),
                         ('latencyP95Ms', limits['latencyP95MaxMs']),
                         ('errorRatePercent', limits['errorRateMaxPercent'])]:
        value = telemetry.get(field) if valid else None
        check(field, 'unknown' if value is None else ('pass' if value <= limit else 'fail'))
    states = {c['status'] for c in checks}
    status = 'blocked' if 'fail' in states else ('not_evaluable' if 'unknown' in states else 'eligible_for_review')
    action = 'none'
    if status == 'eligible_for_review':
        action = ('review_capacity_reduction' if prediction['value'] < limits['cpuLowPercent'] else
                  'review_capacity_increase' if prediction['value'] > limits['cpuHighPercent'] else 'maintain')
    return status, action, checks
