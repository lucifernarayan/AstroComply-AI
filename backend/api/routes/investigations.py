from uuid import uuid4, UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from backend.database.db import engine
from backend.security.auth import membership, require_role, audit

router = APIRouter()

class InvestigationRequest(BaseModel):
    event_id: int = Field(gt=0)
    query: str = Field(min_length=5, max_length=1000)

@router.post('/{organization_id}/investigations', status_code=202)
def submit(organization_id: int, payload: InvestigationRequest, member: dict = Depends(membership)):
    require_role(member, {'owner','administrator','operator','analyst'})
    job_id = uuid4()
    with engine.begin() as connection:
        event = connection.execute(text('SELECT id FROM conjunction_events WHERE id=:id AND organization_id=:org'),
            {'id':payload.event_id,'org':organization_id}).first()
        if not event:
            raise HTTPException(404,'Event not found')
        connection.execute(text('''INSERT INTO investigation_jobs(id,organization_id,user_id,event_id,query)
            VALUES (:id,:org,:user,:event,:query)'''),
            {'id':job_id,'org':organization_id,'user':member['user_id'],
             'event':payload.event_id,'query':payload.query})
        audit(connection,member,'submit','investigation_job',None)
    return {'id':job_id,'status':'queued'}

@router.get('/{organization_id}/investigations')
def list_jobs(organization_id: int, member: dict = Depends(membership)):
    with engine.connect() as connection:
        rows = connection.execute(text('''SELECT id,event_id,status,query,created_at,updated_at
            FROM investigation_jobs WHERE organization_id=:org ORDER BY created_at DESC LIMIT 50'''),
            {'org':organization_id}).mappings()
        return [dict(row) for row in rows]

@router.get('/{organization_id}/investigations/{job_id}')
def get_job(organization_id: int, job_id: UUID, member: dict = Depends(membership)):
    with engine.connect() as connection:
        row = connection.execute(text('''SELECT id,event_id,status,attempts,query,result,steps,error,created_at,updated_at
            FROM investigation_jobs WHERE organization_id=:org AND id=:id'''),
            {'org':organization_id,'id':job_id}).mappings().first()
    if not row:
        raise HTTPException(404,'Investigation not found')
    return dict(row)


@router.get('/{organization_id}/investigations/{job_id}/report', response_class=PlainTextResponse)
def report(organization_id: int, job_id: UUID, member: dict = Depends(membership)):
    with engine.connect() as connection:
        row = connection.execute(text('''SELECT j.status,j.result,j.created_at,j.updated_at,o.name
            FROM investigation_jobs j JOIN organizations o ON o.id=j.organization_id
            WHERE j.organization_id=:org AND j.id=:id'''),
            {'org':organization_id,'id':job_id}).mappings().first()
    if not row:
        raise HTTPException(404,'Investigation not found')
    if row['status'] != 'succeeded':
        raise HTTPException(409,'Investigation is not complete')
    result = row['result']
    evidence = result['evidence']
    return '\n'.join([
        'ASTROCOMPLY CONJUNCTION INVESTIGATION',
        f"Organization: {row['name']}",
        f"Generated at: {row['updated_at'].isoformat()}",
        f"Query: {result['query']}",
        f"Source: {evidence['source']}",
        f"Source record: {evidence['external_id']}",
        f"Primary NORAD: {evidence['primary_norad']}",
        f"Secondary NORAD: {evidence['secondary_norad']}",
        f"Closest approach: {evidence['tca']}",
        f"Provider miss distance (m): {evidence['miss_distance_m']}",
        f"Provider relative speed (m/s): {evidence['relative_speed_m_s']}",
        'Method: Provider event review with deterministic data extraction',
        'Collision probability: Insufficient data for reliable probability-of-collision estimation.',
        f"Conclusion: {result['conclusion']}",
        'Limitations: ' + '; '.join(result['limitations']),
    ]) + '\n'

@router.post('/{organization_id}/investigations/{job_id}/cancel')
def cancel(organization_id: int, job_id: UUID, member: dict = Depends(membership)):
    require_role(member, {'owner','administrator','operator','analyst'})
    with engine.begin() as connection:
        row = connection.execute(text('''UPDATE investigation_jobs SET status='cancelled',updated_at=now()
            WHERE id=:id AND organization_id=:org AND status='queued' RETURNING id'''),
            {'id':job_id,'org':organization_id}).first()
        if not row:
            raise HTTPException(409,'Queued investigation not found')
    return {'id':job_id,'status':'cancelled'}
