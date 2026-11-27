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
    with engine.begin() as connection:
        connection.execute(text("UPDATE memberships SET role='viewer' WHERE organization_id=:org"), {'org': first_id})
    assert client.get(f'/organizations/{first_id}/fleet/{asset_id}', headers=headers[0]).status_code == 200
    assert client.post(f'/organizations/{first_id}/fleet', json={'display_name': 'Denied'}, headers=headers[0]).status_code == 403
    assert client.post('/auth/logout', headers=headers[0]).status_code == 204
    assert client.get('/auth/me', headers=headers[0]).status_code == 401
