from uuid import uuid4
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.database.db import engine
from sqlalchemy import text


def test_account_and_workspace_isolation():
    client = TestClient(app)
    headers = []
    for index in range(2):
        email = f'pilot-{uuid4()}@example.com'
        created = client.post('/auth/register', json={'email': email, 'password': 'very-long-test-password'})
        assert created.status_code == 201, created.text
        headers.append({'Authorization': f"Bearer {created.json()['access_token']}"})
    first = client.post('/organizations', json={'name': 'Operator One'}, headers=headers[0])
    second = client.post('/organizations', json={'name': 'Operator Two'}, headers=headers[1])
    assert first.status_code == second.status_code == 201
    first_id, second_id = first.json()['id'], second.json()['id']
    asset = client.post(f'/organizations/{first_id}/fleet', json={'display_name': 'Private asset'}, headers=headers[0])
    assert asset.status_code == 201, asset.text
    asset_id = asset.json()['id']
    assert client.get(f'/organizations/{first_id}/fleet/{asset_id}', headers=headers[1]).status_code == 404
    assert client.get(f'/organizations/{second_id}/fleet/{asset_id}', headers=headers[1]).status_code == 404
    assert client.patch(f'/organizations/{first_id}/fleet/{asset_id}', json={'display_name': 'Hijacked'}, headers=headers[1]).status_code == 404
    assert client.delete(f'/organizations/{first_id}/fleet/{asset_id}', headers=headers[1]).status_code == 404
    assert client.get(f'/organizations/{first_id}/fleet/{asset_id}', headers=headers[0]).status_code == 200
    fleet_report = client.get(f'/organizations/{first_id}/reports/fleet.csv', headers=headers[0])
    assert fleet_report.status_code == 200 and 'Private asset' in fleet_report.text
    assert client.get(f'/organizations/{first_id}/reports/fleet.csv', headers=headers[1]).status_code == 404
    event = client.post(f'/organizations/{first_id}/events', headers=headers[0], json={
        'source':'customer-CDM', 'external_id':str(uuid4()), 'primary_norad':900,
        'secondary_norad':901, 'tca':'2026-12-01T12:00:00Z', 'miss_distance_m':840,
    })
    assert event.status_code == 201, event.text
    assert 'Insufficient data' in event.json()['probability_status']
    assert client.post(f'/organizations/{first_id}/events', headers=headers[0], json={
        'source':'customer-CDM', 'external_id':str(uuid4()), 'tca':'2026-12-01T12:00:00Z',
        'collision_probability':0.001,
    }).status_code == 422
    event_id = event.json()['id']
    assert client.get(f'/organizations/{first_id}/events/{event_id}', headers=headers[1]).status_code == 404
    assert client.get(f'/organizations/{second_id}/events/{event_id}', headers=headers[1]).status_code == 404
    assert client.patch(f'/organizations/{first_id}/events/{event_id}', headers=headers[1],
        json={'status':'resolved'}).status_code == 404
    from backend.ingestion.test_cdm import VALID
    upload = client.post(f'/organizations/{first_id}/events/cdm', headers=headers[0],
        files={'file': ('example.cdm', VALID.encode(), 'text/plain')})
    assert upload.status_code == 201, upload.text
    assert client.post(f'/organizations/{first_id}/events/cdm', headers=headers[0],
        files={'file': ('example.cdm', VALID.encode(), 'text/plain')}).status_code == 409
    updated_cdm = VALID.replace('MISS_DISTANCE = 840', 'MISS_DISTANCE = 750')
    update = client.post(f'/organizations/{first_id}/events/cdm', headers=headers[0],
        files={'file': ('updated.cdm', updated_cdm.encode(), 'text/plain')})
    assert update.status_code == 201, update.text
    assert update.json()['id'] == upload.json()['id'] and update.json()['version'] == 2
    versions_path = f"/organizations/{first_id}/events/{upload.json()['id']}/versions"
    versions = client.get(versions_path, headers=headers[0])
    assert [item['version_number'] for item in versions.json()] == [2, 1]
    assert versions.json()[0]['raw_data']['fields']['miss_distance_m'] == 750
    assert client.get(versions_path, headers=headers[1]).status_code == 404
    events_report = client.get(f'/organizations/{first_id}/reports/events.csv', headers=headers[0])
    assert events_report.status_code == 200 and 'ABC-1' in events_report.text
    assert '750.0' in events_report.text and 'TEST' in events_report.text
    assert client.get(f'/organizations/{first_id}/reports/events.csv', headers=headers[1]).status_code == 404
    assert client.get(f"/organizations/{first_id}/events/{upload.json()['id']}", headers=headers[1]).status_code == 404
    investigation = client.post(f'/organizations/{first_id}/investigations', headers=headers[0],
        json={'event_id': upload.json()['id'], 'query':'Investigate this conjunction'})
    assert investigation.status_code == 202, investigation.text
    job_id = investigation.json()['id']
    assert client.get(f'/organizations/{first_id}/investigations/{job_id}', headers=headers[1]).status_code == 404
    from backend.intelligence.job_worker import run_once
    assert run_once()
    assert client.get('/health/worker').json()['status'] == 'healthy'
    result = client.get(f'/organizations/{first_id}/investigations/{job_id}', headers=headers[0]).json()
    assert result['status'] == 'succeeded', result
    assert result['result']['evidence']['external_id'] == 'ABC-1'
    assert result['steps'][0]['tool'] == 'get_conjunction_event'
    report_path = f'/organizations/{first_id}/investigations/{job_id}/report'
    assert client.get(report_path, headers=headers[1]).status_code == 404
    report = client.get(report_path, headers=headers[0])
    assert report.status_code == 200
    assert 'ABC-1' in report.text and 'Operator One' in report.text
    assert client.get('/assess/900', headers=headers[1]).status_code == 422
    assert client.get('/assess/900', headers={**headers[1], 'X-Organization-Id': str(first_id)}).status_code == 404
    assert client.get('/assess/900', headers={'X-Organization-Id': str(first_id)}).status_code == 401
    from backend.api.routes.uipath import uipath_jobs
    uipath_jobs['tenant-check'] = {'organization_id': first_id, 'status': 'PENDING'}
    assert client.get('/uipath/job/status/tenant-check', headers={**headers[1],
        'X-Organization-Id': str(second_id)}).status_code == 404
    assert client.get('/uipath/job/status/tenant-check', headers={**headers[0],
        'X-Organization-Id': str(first_id)}).status_code == 200
    uipath_jobs.pop('tenant-check')
    with engine.begin() as connection:
        connection.execute(text("UPDATE memberships SET role='viewer' WHERE organization_id=:org"), {'org': first_id})
    assert client.get(f'/organizations/{first_id}/fleet/{asset_id}', headers=headers[0]).status_code == 200
    assert client.post(f'/organizations/{first_id}/fleet', json={'display_name': 'Denied'}, headers=headers[0]).status_code == 403
    assert client.post(f'/organizations/{first_id}/investigations', headers=headers[0],
        json={'event_id': event_id, 'query':'Investigate this event'}).status_code == 403
    assert client.post('/auth/logout', headers=headers[0]).status_code == 204
    assert client.get('/auth/me', headers=headers[0]).status_code == 401
