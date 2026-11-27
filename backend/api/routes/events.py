from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from backend.database.db import engine
from backend.security.auth import membership, require_role, audit

router = APIRouter()
WRITERS = {'owner','administrator','operator'}

class CDMInput(BaseModel):
    external_id: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=120)
    primary_norad: int | None = Field(default=None, gt=0)
    secondary_norad: int | None = Field(default=None, gt=0)
    tca: AwareDatetime
    miss_distance_m: float | None = Field(default=None, ge=0)
    relative_speed_m_s: float | None = Field(default=None, ge=0)
    collision_probability: float | None = Field(default=None, ge=0, le=1)

class EventUpdate(BaseModel):
    status: str = Field(pattern='^(unverified|review|resolved)$')
    note: str | None = Field(default=None, max_length=4000)

@router.post('/{organization_id}/events', status_code=201)
def import_event(organization_id: int, payload: CDMInput, member: dict = Depends(membership)):
    require_role(member, WRITERS)
    if payload.collision_probability is not None:
        raise HTTPException(422, 'Probability import requires a validated covariance and calculation workflow')
    if payload.primary_norad and payload.primary_norad == payload.secondary_norad:
        raise HTTPException(422, 'Object identifiers must differ')
    with engine.begin() as connection:
        row = connection.execute(text('''INSERT INTO conjunction_events
          (organization_id,source,external_id,primary_norad,secondary_norad,tca,miss_distance_m,
           relative_speed_m_s,collision_probability,raw_data)
          VALUES (:org,:source,:external,:primary,:secondary,:tca,:miss,:speed,:pc,CAST(:raw AS jsonb))
          ON CONFLICT (organization_id,source,external_id) DO NOTHING RETURNING id'''),
          {'org':organization_id,'source':payload.source,'external':payload.external_id,
           'primary':payload.primary_norad,'secondary':payload.secondary_norad,'tca':payload.tca,
           'miss':payload.miss_distance_m,'speed':payload.relative_speed_m_s,'pc':payload.collision_probability,
           'raw':payload.model_dump_json()}).first()
        if not row:
            raise HTTPException(409, 'Event already imported')
        audit(connection, member, 'import', 'conjunction_event', row[0])
    return {'id':row[0], 'probability_status':'Insufficient data for reliable probability-of-collision estimation.'}

@router.get('/{organization_id}/events')
def list_events(organization_id: int, limit: int = Query(50,ge=1,le=200), member: dict = Depends(membership)):
    with engine.connect() as connection:
        rows = connection.execute(text('''SELECT id,source,external_id,primary_norad,secondary_norad,tca,
          miss_distance_m,relative_speed_m_s,collision_probability,status,created_at
          FROM conjunction_events WHERE organization_id=:org ORDER BY tca DESC LIMIT :limit'''),
          {'org':organization_id,'limit':limit}).mappings()
        return [dict(row) for row in rows]

@router.get('/{organization_id}/events/{event_id}')
def get_event(organization_id: int, event_id: int, member: dict = Depends(membership)):
    with engine.connect() as connection:
        row = connection.execute(text('SELECT * FROM conjunction_events WHERE organization_id=:org AND id=:id'),
          {'org':organization_id,'id':event_id}).mappings().first()
    if not row:
        raise HTTPException(404,'Event not found')
    return dict(row)

@router.patch('/{organization_id}/events/{event_id}')
def update_event(organization_id: int, event_id: int, payload: EventUpdate, member: dict = Depends(membership)):
    require_role(member, WRITERS)
    with engine.begin() as connection:
        row = connection.execute(text('''UPDATE conjunction_events SET status=:status,note=:note,updated_at=now()
          WHERE organization_id=:org AND id=:id RETURNING id'''),
          {'status':payload.status,'note':payload.note,'org':organization_id,'id':event_id}).first()
        if not row:
            raise HTTPException(404,'Event not found')
        audit(connection,member,'update','conjunction_event',event_id)
    return {'id':event_id,'status':payload.status,'note':payload.note}
