"""Durable, bounded database worker for organization investigations."""
import json
import time
from sqlalchemy import text
from backend.database.db import engine
from backend.intelligence.workflows import execute


def run_once() -> bool:
    with engine.begin() as connection:
        connection.execute(text('''INSERT INTO worker_heartbeat(worker_name,last_seen_at)
          VALUES ('investigations',now()) ON CONFLICT (worker_name)
          DO UPDATE SET last_seen_at=now()'''))
        connection.execute(text('''UPDATE investigation_jobs SET status='failed',
          error=COALESCE(error,'Worker lease expired after final attempt'),finished_at=now(),updated_at=now()
          WHERE status='running' AND attempts>=max_attempts
          AND updated_at < now() - interval '10 minutes' '''))
        job = connection.execute(text('''SELECT id,organization_id,event_id,asset_id,workflow,query,
          attempts,max_attempts
          FROM investigation_jobs WHERE attempts<max_attempts AND
          (status='queued' OR (status='running' AND updated_at < now() - interval '10 minutes'))
          ORDER BY created_at
          FOR UPDATE SKIP LOCKED LIMIT 1''')).mappings().first()
        if not job:
            return False
        connection.execute(text('''UPDATE investigation_jobs SET status='running', attempts=attempts+1,
          progress=10,started_at=COALESCE(started_at,now()),updated_at=now(),error=NULL
          WHERE id=:id'''), {'id':job['id']})
        connection.execute(text('''UPDATE worker_heartbeat SET last_job_at=now()
          WHERE worker_name='investigations' '''))
    try:
        with engine.connect() as connection:
            result, steps = execute(dict(job), connection)
        with engine.begin() as connection:
            connection.execute(text('''UPDATE investigation_jobs SET status='succeeded',result=CAST(:result AS jsonb),
                steps=CAST(:steps AS jsonb),progress=100,finished_at=now(),updated_at=now()
                WHERE id=:id AND status='running' '''),
                {'id':job['id'],'result':json.dumps(result),'steps':json.dumps(steps)})
    except Exception as error:
        with engine.begin() as connection:
            connection.execute(text('''UPDATE investigation_jobs SET
                status=CASE WHEN attempts<max_attempts THEN 'queued' ELSE 'failed' END,
                error=:error,progress=0,updated_at=now(),
                finished_at=CASE WHEN attempts>=max_attempts THEN now() ELSE NULL END
                WHERE id=:id AND status='running' '''),
                {'id':job['id'],'error':str(error)[:500]})
    return True


if __name__ == '__main__':
    while True:
        if not run_once():
            time.sleep(2)
