"""Organization-owned data exports with explicit source and epoch fields."""
import csv
from io import StringIO
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import text
from backend.database.db import engine
from backend.security.auth import membership

router = APIRouter()


def csv_response(columns: list[str], records: list[dict], filename: str) -> Response:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for record in records:
        writer.writerow([csv_safe(record.get(column)) for column in columns])
    return Response(output.getvalue(), media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'})


def csv_safe(value):
    if value is None:
        return ''
    text_value = value.isoformat() if hasattr(value, 'isoformat') else str(value)
    return "'" + text_value if text_value.startswith(('=', '+', '-', '@', '\t', '\r')) else text_value


@router.get('/{organization_id}/reports/fleet.csv')
def fleet_csv(organization_id: int, member: dict = Depends(membership)):
    columns = ['asset_id', 'display_name', 'norad_id', 'constellation', 'catalogue_epoch',
               'inclination_deg', 'eccentricity', 'mean_motion_rev_day', 'catalogue_source',
               'exported_at']
    with engine.connect() as connection:
        rows = connection.execute(text('''SELECT f.id AS asset_id, f.display_name, f.norad_id,
            f.constellation, s.epoch_time AS catalogue_epoch,
            s.inclination AS inclination_deg, s.eccentricity,
            s.mean_motion AS mean_motion_rev_day,
            CASE WHEN s.id IS NULL THEN NULL ELSE 'local catalogue' END AS catalogue_source,
            now() AS exported_at FROM fleet_assets f
            LEFT JOIN satellites s ON s.norad_id=f.norad_id
            WHERE f.organization_id=:org AND f.archived_at IS NULL ORDER BY f.id'''),
            {'org': organization_id}).mappings()
        records = [dict(row) for row in rows]
    return csv_response(columns, records, f'astrocomply-fleet-{organization_id}.csv')


@router.get('/{organization_id}/reports/events.csv')
def events_csv(organization_id: int, member: dict = Depends(membership)):
    columns = ['event_id', 'source', 'external_id', 'primary_norad', 'secondary_norad',
               'tca', 'miss_distance_m', 'relative_speed_m_s', 'status', 'source_sha256',
               'imported_at', 'updated_at', 'exported_at']
    with engine.connect() as connection:
        rows = connection.execute(text('''SELECT id AS event_id,source,external_id,primary_norad,
            secondary_norad,tca,miss_distance_m,relative_speed_m_s,status,
            raw_data->>'sha256' AS source_sha256,created_at AS imported_at,updated_at,
            now() AS exported_at FROM conjunction_events
            WHERE organization_id=:org ORDER BY tca DESC'''), {'org': organization_id}).mappings()
        records = [dict(row) for row in rows]
    return csv_response(columns, records, f'astrocomply-events-{organization_id}.csv')
