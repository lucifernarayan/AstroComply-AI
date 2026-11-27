from uuid import uuid4, UUID
from typing import Literal
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from backend.database.db import engine
from backend.security.auth import membership, require_role, audit

router = APIRouter()

class InvestigationRequest(BaseModel):
    workflow: Literal['conjunction_investigation','satellite_investigation','fleet_health',
                      'regulatory_research','mission_analysis'] = 'conjunction_investigation'
    event_id: int | None = Field(default=None, gt=0)
    asset_id: int | None = Field(default=None, gt=0)
    query: str = Field(min_length=5, max_length=1000)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=120)

@router.post('/{organization_id}/investigations', status_code=202)
def submit(organization_id: int, payload: InvestigationRequest, member: dict = Depends(membership)):
    require_role(member, {'owner','administrator','operator','analyst'})
    job_id = uuid4()
    with engine.begin() as connection:
        if payload.idempotency_key:
            existing = connection.execute(text('''SELECT id,status FROM investigation_jobs
                WHERE organization_id=:org AND idempotency_key=:key'''),
                {'org': organization_id, 'key': payload.idempotency_key}).mappings().first()
            if existing:
                return dict(existing)
        if payload.workflow == 'conjunction_investigation':
            if not payload.event_id:
                raise HTTPException(422, 'Event ID required for conjunction investigation')
            found = connection.execute(text('SELECT id FROM conjunction_events WHERE id=:id AND organization_id=:org'),
                {'id':payload.event_id,'org':organization_id}).first()
            if not found:
                raise HTTPException(404,'Event not found')
        elif payload.workflow in ('satellite_investigation', 'mission_analysis'):
            if not payload.asset_id:
                raise HTTPException(422, 'Asset ID required for this workflow')
            found = connection.execute(text('''SELECT id FROM fleet_assets WHERE id=:id AND organization_id=:org
                AND archived_at IS NULL'''), {'id':payload.asset_id,'org':organization_id}).first()
            if not found:
                raise HTTPException(404, 'Asset not found')
        elif payload.event_id or payload.asset_id:
            raise HTTPException(422, 'Resource ID is not used by this workflow')
        connection.execute(text('''INSERT INTO investigation_jobs
            (id,organization_id,user_id,event_id,asset_id,workflow,query,idempotency_key)
            VALUES (:id,:org,:user,:event,:asset,:workflow,:query,:key)'''),
            {'id':job_id,'org':organization_id,'user':member['user_id'],
             'event':payload.event_id,'asset':payload.asset_id,'workflow':payload.workflow,
             'query':payload.query,'key':payload.idempotency_key})
        audit(connection,member,'submit','investigation_job',None)
    return {'id':job_id,'status':'queued'}

@router.get('/{organization_id}/investigations')
def list_jobs(organization_id: int, member: dict = Depends(membership)):
    with engine.connect() as connection:
        rows = connection.execute(text('''SELECT id,event_id,asset_id,workflow,status,progress,query,created_at,updated_at
            FROM investigation_jobs WHERE organization_id=:org ORDER BY created_at DESC LIMIT 50'''),
            {'org':organization_id}).mappings()
        return [dict(row) for row in rows]

@router.get('/{organization_id}/investigations/{job_id}')
def get_job(organization_id: int, job_id: UUID, member: dict = Depends(membership)):
    with engine.connect() as connection:
        row = connection.execute(text('''SELECT id,event_id,asset_id,workflow,status,progress,attempts,query,
            result,steps,error,created_at,updated_at,started_at,finished_at
            FROM investigation_jobs WHERE organization_id=:org AND id=:id'''),
            {'org':organization_id,'id':job_id}).mappings().first()
    if not row:
        raise HTTPException(404,'Investigation not found')
    return dict(row)


@router.get('/{organization_id}/investigations/{job_id}/report', response_class=PlainTextResponse)
def report(organization_id: int, job_id: UUID, member: dict = Depends(membership)):
    with engine.connect() as connection:
        row = connection.execute(text('''SELECT j.status,j.workflow,j.result,j.created_at,j.updated_at,o.name
            FROM investigation_jobs j JOIN organizations o ON o.id=j.organization_id
            WHERE j.organization_id=:org AND j.id=:id'''),
            {'org':organization_id,'id':job_id}).mappings().first()
    if not row:
        raise HTTPException(404,'Investigation not found')
    if row['status'] != 'succeeded':
        raise HTTPException(409,'Investigation is not complete')
    result = row['result']
    if row['workflow'] != 'conjunction_investigation':
        return '\n'.join([
            'ASTROCOMPLY WORKSPACE INVESTIGATION',
            f"Organization: {row['name']}",
            f"Workflow: {row['workflow']}",
            f"Generated at: {row['updated_at'].isoformat()}",
            f"Query: {result['query']}",
            f"Conclusion: {result['conclusion']}",
            f"Evidence: {json.dumps(result['evidence'], ensure_ascii=True, default=str)}",
            'Limitations: ' + '; '.join(result['limitations']),
        ]) + '\n'
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
