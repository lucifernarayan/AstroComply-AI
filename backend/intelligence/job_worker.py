"""Durable, bounded database job worker for conjunction investigations."""
import json
import time
from sqlalchemy import text
from backend.database.db import engine


def run_once() -> bool:
    with engine.begin() as connection:
        connection.execute(text('''INSERT INTO worker_heartbeat(worker_name,last_seen_at)
          VALUES ('investigations',now()) ON CONFLICT (worker_name)
          DO UPDATE SET last_seen_at=now()'''))
        job = connection.execute(text('''SELECT id,organization_id,event_id,query,attempts,max_attempts
          FROM investigation_jobs WHERE attempts<max_attempts AND
          (status='queued' OR (status='running' AND updated_at < now() - interval '10 minutes'))
          ORDER BY created_at
          FOR UPDATE SKIP LOCKED LIMIT 1''')).mappings().first()
        if not job:
            return False
        connection.execute(text('''UPDATE investigation_jobs SET status='running', attempts=attempts+1,
          updated_at=now() WHERE id=:id'''), {'id':job['id']})
        connection.execute(text('''UPDATE worker_heartbeat SET last_job_at=now()
          WHERE worker_name='investigations' '''))
    try:
        with engine.connect() as connection:
            event = connection.execute(text('''SELECT id,source,external_id,primary_norad,secondary_norad,tca,
                miss_distance_m,relative_speed_m_s,collision_probability,raw_data,status
                FROM conjunction_events WHERE id=:id AND organization_id=:org'''),
                {'id':job['event_id'],'org':job['organization_id']}).mappings().first()
        if not event:
            raise ValueError('Event no longer exists in workspace')
        evidence = {key: value for key, value in dict(event).items() if key != 'raw_data'}
        evidence['tca'] = evidence['tca'].isoformat()
        source_metadata = event['raw_data']
        steps = [
            {'tool':'get_conjunction_event','status':'complete','source':event['source'],
             'external_id':event['external_id']},
            {'tool':'inspect_uncertainty','status':'complete',
             'covariance_present':bool(source_metadata.get('fields',{}).get('covariance_present')),
             'probability_available':event['collision_probability'] is not None},
        ]
        conclusion = (f"Provider {event['source']} reports a closest approach at {evidence['tca']} "
                      f"with miss distance {event['miss_distance_m']} m. "
                      "Insufficient data for reliable probability-of-collision estimation. "
                      "Operator review of the original CDM and updated orbital data is required.")
        result = {'query':job['query'],'workflow':'conjunction_investigation','evidence':evidence,
                  'conclusion':conclusion,'limitations':['No validated probability calculation',
                  'No independently verified covariance or ephemeris']}
        with engine.begin() as connection:
            connection.execute(text('''UPDATE investigation_jobs SET status='succeeded',result=CAST(:result AS jsonb),
                steps=CAST(:steps AS jsonb),updated_at=now() WHERE id=:id AND status='running' '''),
                {'id':job['id'],'result':json.dumps(result),'steps':json.dumps(steps)})
    except Exception as error:
        with engine.begin() as connection:
            connection.execute(text('''UPDATE investigation_jobs SET
                status=CASE WHEN attempts<max_attempts THEN 'queued' ELSE 'failed' END,
                error=:error,updated_at=now() WHERE id=:id AND status='running' '''),
                {'id':job['id'],'error':str(error)[:500]})
    return True


if __name__ == '__main__':
    while True:
        if not run_once():
            time.sleep(2)
