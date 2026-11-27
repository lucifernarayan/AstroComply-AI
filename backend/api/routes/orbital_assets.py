"""Organization-scoped TLE upload and SGP4 globe position feed."""
from datetime import datetime, timezone
import hashlib
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import AwareDatetime
from sqlalchemy import text
from backend.database.db import engine
from backend.orbital.tle import TLEValidationError, parse_tle, propagate
from backend.security.auth import audit, membership, require_role

router = APIRouter()
WRITERS = {'owner', 'administrator', 'operator'}


@router.post('/{organization_id}/fleet/{asset_id}/tle', status_code=201)
async def upload_tle(organization_id: int, asset_id: int, file: UploadFile = File(...),
                     source: str = Form(...), member: dict = Depends(membership)):
    require_role(member, WRITERS)
    if not source.strip() or len(source) > 120:
        raise HTTPException(422, 'Source must be 1 to 120 characters')
    content = await file.read(4097)
    if len(content) > 4096:
        raise HTTPException(413, 'TLE exceeds 4 KB')
    try:
        original = content.decode('ascii')
        parsed = parse_tle(original)
    except (UnicodeDecodeError, TLEValidationError) as error:
        raise HTTPException(422, str(error)) from error
    digest = hashlib.sha256(content).hexdigest()
    with engine.begin() as connection:
        asset = connection.execute(text('''SELECT norad_id FROM fleet_assets
            WHERE id=:asset AND organization_id=:org AND archived_at IS NULL FOR UPDATE'''),
            {'asset': asset_id, 'org': organization_id}).mappings().first()
        if not asset:
            raise HTTPException(404, 'Asset not found')
        if asset['norad_id'] is not None and asset['norad_id'] != parsed['norad_id']:
            raise HTTPException(422, 'TLE catalogue number does not match fleet asset')
        row = connection.execute(text('''INSERT INTO fleet_orbital_elements
            (organization_id,asset_id,norad_id,line1,line2,original_text,source,filename,sha256,epoch,uploaded_by)
            VALUES (:org,:asset,:norad,:first,:second,:original,:source,:filename,:sha,:epoch,:user)
            ON CONFLICT (asset_id,sha256) DO NOTHING RETURNING id'''),
            {'org': organization_id, 'asset': asset_id, 'norad': parsed['norad_id'],
             'first': parsed['line1'], 'second': parsed['line2'], 'original': original,
             'source': source.strip(), 'filename': file.filename, 'sha': digest,
             'epoch': parsed['epoch'], 'user': member['user_id']}).first()
        if not row:
            raise HTTPException(409, 'TLE already uploaded for this asset')
        audit(connection, member, 'upload', 'fleet_orbital_element', row[0])
    return {'id': row[0], 'asset_id': asset_id, 'norad_id': parsed['norad_id'],
            'epoch': parsed['epoch'], 'source': source.strip(), 'sha256': digest,
            'uploaded_state': 'stored'}


@router.get('/{organization_id}/fleet/{asset_id}/elements')
def list_elements(organization_id: int, asset_id: int, member: dict = Depends(membership)):
    with engine.connect() as connection:
        asset = connection.execute(text('''SELECT id FROM fleet_assets
            WHERE organization_id=:org AND id=:asset AND archived_at IS NULL'''),
            {'org': organization_id, 'asset': asset_id}).first()
        if not asset:
            raise HTTPException(404, 'Asset not found')
        rows = connection.execute(text('''SELECT id,norad_id,source,filename,sha256,epoch,uploaded_at
            FROM fleet_orbital_elements WHERE organization_id=:org AND asset_id=:asset
            ORDER BY uploaded_at DESC,id DESC'''),
            {'org': organization_id, 'asset': asset_id}).mappings()
        return [dict(row) for row in rows]


def _position(row: dict, at: datetime) -> dict:
    base = {'asset_id': row['asset_id'], 'display_name': row['display_name'],
            'norad_id': row.get('norad_id'), 'at': at}
    if not row.get('line1'):
        return base | {'status': 'unavailable', 'reason': 'No uploaded TLE'}
    tle = {'line1': row['line1'], 'line2': row['line2'], 'epoch': row['epoch']}
    metadata = {'source': row['source'], 'filename': row['filename'],
                'sha256': row['sha256'], 'uploaded_at': row['uploaded_at'], 'epoch': row['epoch']}
    if abs((at - row['epoch']).total_seconds()) > 14 * 86400:
        return base | metadata | {'status': 'stale', 'reason': 'Element epoch exceeds 14-day display window'}
    try:
        prediction = propagate(tle, at)
    except TLEValidationError as error:
        return base | metadata | {'status': 'failed', 'reason': str(error)}
    return base | metadata | prediction | {'status': 'propagated'}


@router.get('/{organization_id}/orbital/positions')
def positions(organization_id: int, at: AwareDatetime | None = Query(None),
              member: dict = Depends(membership)):
    instant = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    with engine.connect() as connection:
        rows = connection.execute(text('''SELECT f.id AS asset_id,f.display_name,
            e.norad_id,e.line1,e.line2,e.epoch,e.source,e.filename,e.sha256,e.uploaded_at
            FROM fleet_assets f LEFT JOIN LATERAL (
              SELECT norad_id,line1,line2,epoch,source,filename,sha256,uploaded_at
              FROM fleet_orbital_elements WHERE asset_id=f.id AND organization_id=:org
              ORDER BY uploaded_at DESC,id DESC LIMIT 1
            ) e ON true
            WHERE f.organization_id=:org AND f.archived_at IS NULL ORDER BY f.id LIMIT 200'''),
            {'org': organization_id}).mappings()
        return {'at': instant, 'positions': [_position(dict(row), instant) for row in rows]}


@router.get('/{organization_id}/fleet/{asset_id}/position')
def asset_position(organization_id: int, asset_id: int, at: AwareDatetime | None = Query(None),
                   member: dict = Depends(membership)):
    instant = (at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    with engine.connect() as connection:
        row = connection.execute(text('''SELECT f.id AS asset_id,f.display_name,
            e.norad_id,e.line1,e.line2,e.epoch,e.source,e.filename,e.sha256,e.uploaded_at
            FROM fleet_assets f LEFT JOIN LATERAL (
              SELECT norad_id,line1,line2,epoch,source,filename,sha256,uploaded_at
              FROM fleet_orbital_elements WHERE asset_id=f.id AND organization_id=:org
              ORDER BY uploaded_at DESC,id DESC LIMIT 1
            ) e ON true
            WHERE f.organization_id=:org AND f.id=:asset AND f.archived_at IS NULL'''),
            {'org': organization_id, 'asset': asset_id}).mappings().first()
    if not row:
        raise HTTPException(404, 'Asset not found')
    return _position(dict(row), instant)
