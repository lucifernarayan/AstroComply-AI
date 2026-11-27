from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from backend.database.db import engine
from backend.security.auth import current_user, membership, require_role, audit

router = APIRouter()
WRITERS = {'owner','administrator','operator'}

class OrganizationInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)

class AssetInput(BaseModel):
    norad_id: int | None = Field(default=None, gt=0)
    display_name: str = Field(min_length=1, max_length=255)
    constellation: str | None = Field(default=None, max_length=120)

@router.get('')
def list_organizations(user: dict = Depends(current_user)):
    with engine.connect() as connection:
        rows = connection.execute(text('''SELECT o.id,o.name,m.role FROM organizations o JOIN memberships m
            ON m.organization_id=o.id WHERE m.user_id=:user ORDER BY o.name'''), {'user': user['id']}).mappings()
        return [dict(row) for row in rows]

@router.post('', status_code=201)
def create_organization(payload: OrganizationInput, user: dict = Depends(current_user)):
    with engine.begin() as connection:
        org_id = connection.execute(text('INSERT INTO organizations(name) VALUES (:name) RETURNING id'),
            {'name': payload.name}).scalar_one()
        connection.execute(text("INSERT INTO memberships(user_id,organization_id,role) VALUES (:user,:org,'owner')"),
            {'user': user['id'], 'org': org_id})
        audit(connection, {'organization_id': org_id,'user_id':user['id']}, 'create', 'organization', org_id)
    return {'id': org_id,'name':payload.name,'role':'owner'}

@router.get('/{organization_id}/fleet')
def list_fleet(organization_id: int, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
               member: dict = Depends(membership)):
    with engine.connect() as connection:
        rows = connection.execute(text('''SELECT f.id,f.norad_id,f.display_name,f.constellation,f.created_at,
            s.epoch_time,s.inclination,s.eccentricity,s.mean_motion FROM fleet_assets f
            LEFT JOIN satellites s ON s.norad_id=f.norad_id
            WHERE f.organization_id=:org AND f.archived_at IS NULL ORDER BY f.id DESC LIMIT :limit OFFSET :offset'''),
            {'org':organization_id,'limit':limit,'offset':offset}).mappings()
        return {'items':[dict(row) for row in rows], 'limit':limit,'offset':offset}

@router.post('/{organization_id}/fleet', status_code=201)
def add_asset(organization_id: int, payload: AssetInput, member: dict = Depends(membership)):
    require_role(member, WRITERS)
    try:
        with engine.begin() as connection:
            asset_id = connection.execute(text('''INSERT INTO fleet_assets(organization_id,norad_id,display_name,constellation)
                VALUES (:org,:norad,:name,:constellation) RETURNING id'''),
                {'org':organization_id,'norad':payload.norad_id,'name':payload.display_name,
                 'constellation':payload.constellation}).scalar_one()
            audit(connection, member, 'create', 'fleet_asset', asset_id)
    except IntegrityError:
        raise HTTPException(409, 'Catalogue ID missing or asset already belongs to workspace')
    return {'id':asset_id,**payload.model_dump()}

@router.get('/{organization_id}/fleet/{asset_id}')
def get_asset(organization_id: int, asset_id: int, member: dict = Depends(membership)):
    with engine.connect() as connection:
        row = connection.execute(text('''SELECT f.id,f.norad_id,f.display_name,f.constellation,f.created_at,
            s.epoch_time,s.inclination,s.eccentricity,s.mean_motion,s.raan,s.arg_of_perigee
            FROM fleet_assets f LEFT JOIN satellites s ON s.norad_id=f.norad_id
            WHERE f.organization_id=:org AND f.id=:id AND f.archived_at IS NULL'''),
            {'org':organization_id,'id':asset_id}).mappings().first()
    if not row:
        raise HTTPException(404, 'Asset not found')
    return dict(row)

@router.patch('/{organization_id}/fleet/{asset_id}')
def update_asset(organization_id: int, asset_id: int, payload: AssetInput, member: dict = Depends(membership)):
    require_role(member, WRITERS)
    with engine.begin() as connection:
        row = connection.execute(text('''UPDATE fleet_assets SET norad_id=:norad,display_name=:name,
            constellation=:constellation,updated_at=now() WHERE id=:id AND organization_id=:org
            AND archived_at IS NULL RETURNING id'''), {'norad':payload.norad_id,'name':payload.display_name,
            'constellation':payload.constellation,'id':asset_id,'org':organization_id}).first()
        if not row:
            raise HTTPException(404, 'Asset not found')
        audit(connection, member, 'update', 'fleet_asset', asset_id)
    return {'id':asset_id,**payload.model_dump()}

@router.delete('/{organization_id}/fleet/{asset_id}', status_code=204)
def archive_asset(organization_id: int, asset_id: int, member: dict = Depends(membership)):
    require_role(member, WRITERS)
    with engine.begin() as connection:
        row = connection.execute(text('''UPDATE fleet_assets SET archived_at=now(),updated_at=now()
            WHERE id=:id AND organization_id=:org AND archived_at IS NULL RETURNING id'''),
            {'id':asset_id,'org':organization_id}).first()
        if not row:
            raise HTTPException(404, 'Asset not found')
        audit(connection, member, 'archive', 'fleet_asset', asset_id)
