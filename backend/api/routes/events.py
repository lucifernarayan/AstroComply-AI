from datetime import datetime
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from backend.database.db import engine
from backend.security.auth import membership, require_role, audit
from backend.ingestion.cdm import parse_cdm_kvn, CDMValidationError

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

@router.post('/{organization_id}/events/cdm', status_code=201)
async def upload_cdm(organization_id: int, file: UploadFile = File(...), member: dict = Depends(membership)):
    require_role(member, WRITERS)
    content = await file.read(1_000_001)
    if len(content) > 1_000_000:
        raise HTTPException(413, 'CDM exceeds 1 MB')
    try:
        parsed = parse_cdm_kvn(content.decode('utf-8'))
    except (UnicodeDecodeError, CDMValidationError) as error:
        raise HTTPException(422, str(error))
    identifiers = [item['OBJECT_DESIGNATOR'] for item in parsed['objects']]
    norad_ids = [int(identifier) if identifier.isdecimal() else None for identifier in identifiers]
    raw = {'format': 'CCSDS CDM KVN', 'sha256': hashlib.sha256(content).hexdigest(),
           'filename': file.filename, 'fields': parsed | {'tca': parsed['tca'].isoformat()},
           'object_identifiers': identifiers}
    with engine.begin() as connection:
        existing = connection.execute(text('''SELECT id, raw_data FROM conjunction_events
            WHERE organization_id=:org AND source=:source AND external_id=:external FOR UPDATE'''),
            {'org': organization_id, 'source': parsed['source'], 'external': parsed['external_id']}).mappings().first()
        if existing:
            event_id = existing['id']
            old_hash = (existing['raw_data'] or {}).get('sha256')
            if old_hash == raw['sha256']:
                raise HTTPException(409, 'CDM already imported')
            prior_version = connection.execute(text('''SELECT 1 FROM conjunction_event_versions
                WHERE event_id=:id AND source_sha256=:sha'''),
                {'id': event_id, 'sha': raw['sha256']}).first()
            if prior_version:
                raise HTTPException(409, 'CDM version already imported')
            version = connection.execute(text('''SELECT COALESCE(MAX(version_number),0)+1
                FROM conjunction_event_versions WHERE event_id=:id'''), {'id': event_id}).scalar_one()
            connection.execute(text('''UPDATE conjunction_events SET primary_norad=:first,
                secondary_norad=:second,tca=:tca,miss_distance_m=:miss,
                relative_speed_m_s=:speed,raw_data=CAST(:raw AS jsonb),updated_at=now()
                WHERE id=:id AND organization_id=:org'''),
                {'id': event_id, 'org': organization_id, 'first': norad_ids[0], 'second': norad_ids[1],
                 'tca': parsed['tca'], 'miss': parsed['miss_distance_m'],
                 'speed': parsed['relative_speed_m_s'], 'raw': json.dumps(raw)})
            action = 'update'
        else:
            row = connection.execute(text('''INSERT INTO conjunction_events
            (organization_id,source,external_id,primary_norad,secondary_norad,tca,
             miss_distance_m,relative_speed_m_s,raw_data)
            VALUES (:org,:source,:external,:first,:second,:tca,:miss,:speed,CAST(:raw AS jsonb))
            RETURNING id'''),
            {'org': organization_id, 'source': parsed['source'], 'external': parsed['external_id'],
             'first': norad_ids[0], 'second': norad_ids[1], 'tca': parsed['tca'],
             'miss': parsed['miss_distance_m'], 'speed': parsed['relative_speed_m_s'],
             'raw': json.dumps(raw)}).first()
            event_id, version, action = row[0], 1, 'import'
        connection.execute(text('''INSERT INTO conjunction_event_versions
            (organization_id,event_id,version_number,source_sha256,raw_data)
            VALUES (:org,:event,:version,:sha,CAST(:raw AS jsonb))'''),
            {'org': organization_id, 'event': event_id, 'version': version,
             'sha': raw['sha256'], 'raw': json.dumps(raw)})
        audit(connection, member, action, 'conjunction_event', event_id)
    return {'id': event_id, 'version': version, 'source': parsed['source'], 'external_id': parsed['external_id'],
            'probability_status': 'Insufficient data for reliable probability-of-collision estimation.'}

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

@router.get('/{organization_id}/events/{event_id}/versions')
def list_event_versions(organization_id: int, event_id: int, member: dict = Depends(membership)):
    with engine.connect() as connection:
        event = connection.execute(text('''SELECT id FROM conjunction_events
            WHERE organization_id=:org AND id=:id'''), {'org': organization_id, 'id': event_id}).first()
        if not event:
            raise HTTPException(404, 'Event not found')
        rows = connection.execute(text('''SELECT version_number,source_sha256,raw_data,imported_at
            FROM conjunction_event_versions WHERE organization_id=:org AND event_id=:id
            ORDER BY version_number DESC'''), {'org': organization_id, 'id': event_id}).mappings()
        return [dict(row) for row in rows]

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
