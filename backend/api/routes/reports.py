"""Organization-owned data exports with explicit source and epoch fields."""
import csv
from datetime import datetime, timezone
from io import StringIO
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import text
from backend.database.db import engine
from backend.security.auth import membership
from backend.reports.pdf import render_pdf

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


@router.get('/{organization_id}/reports/fleet.pdf')
def fleet_pdf(organization_id: int, member: dict = Depends(membership)):
    with engine.connect() as connection:
        organization = connection.execute(text('SELECT name FROM organizations WHERE id=:org'),
            {'org': organization_id}).scalar_one()
        rows = connection.execute(text('''SELECT f.id,f.display_name,f.norad_id,f.constellation,
            e.epoch,e.source,e.filename,e.sha256,e.uploaded_at
            FROM fleet_assets f LEFT JOIN LATERAL (
              SELECT epoch,source,filename,sha256,uploaded_at FROM fleet_orbital_elements
              WHERE organization_id=:org AND asset_id=f.id ORDER BY uploaded_at DESC,id DESC LIMIT 1
            ) e ON true WHERE f.organization_id=:org AND f.archived_at IS NULL
            ORDER BY f.id LIMIT 200'''), {'org': organization_id}).mappings()
        assets = [dict(row) for row in rows]
    now = datetime.now(timezone.utc)
    sections = [('Report metadata', [('Organization', organization), ('Generated UTC', now.isoformat()),
                                     ('Asset count', len(assets)), ('Scope', 'Current non-archived fleet assets')])]
    for asset in assets:
        age_days = abs((now - asset['epoch']).total_seconds()) / 86400 if asset['epoch'] else None
        sections.append((f"Asset {asset['id']}: {asset['display_name']}", [
            ('NORAD ID', asset['norad_id']), ('Constellation', asset['constellation']),
            ('Uploaded TLE source', asset['source']), ('Source filename', asset['filename']),
            ('Source SHA-256', asset['sha256']), ('Element epoch UTC', asset['epoch']),
            ('Uploaded UTC', asset['uploaded_at']),
            ('Data quality', 'No uploaded TLE' if age_days is None else
             'Stale: epoch more than 14 days old' if age_days > 14 else 'Epoch within 14 days'),
        ]))
    sections.append(('Method and limitations', [
        ('Method', 'Inventory and source metadata from organization-owned database rows'),
        ('Positions', 'No orbital position or collision probability is calculated in this report'),
        ('Limitations', 'Element age and provenance must be reviewed before operational use'),
    ]))
    return Response(render_pdf('Fleet data quality report', sections), media_type='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="astrocomply-fleet-{organization_id}.pdf"'})


@router.get('/{organization_id}/reports/events/{event_id}.pdf')
def event_pdf(organization_id: int, event_id: int, member: dict = Depends(membership)):
    with engine.connect() as connection:
        row = connection.execute(text('''SELECT o.name AS organization,e.id,e.source,e.external_id,
            e.primary_norad,e.secondary_norad,e.tca,e.miss_distance_m,e.relative_speed_m_s,
            e.status,e.raw_data,e.created_at,e.updated_at,
            v.version_number,s.filename,s.parser_version,s.uploaded_at AS source_uploaded_at
            FROM conjunction_events e JOIN organizations o ON o.id=e.organization_id
            LEFT JOIN LATERAL (SELECT version_number FROM conjunction_event_versions
              WHERE event_id=e.id ORDER BY version_number DESC LIMIT 1) v ON true
            LEFT JOIN cdm_source_files s ON s.event_id=e.id AND s.version_number=v.version_number
            WHERE e.organization_id=:org AND e.id=:event'''),
            {'org': organization_id, 'event': event_id}).mappings().first()
    if not row:
        raise HTTPException(404, 'Event not found')
    raw = row['raw_data'] or {}
    fields = raw.get('fields', {}) if isinstance(raw, dict) else {}
    sections = [
        ('Report metadata', [('Organization', row['organization']), ('Generated UTC', datetime.now(timezone.utc).isoformat()),
                             ('Event ID', row['id']), ('Event version', row['version_number']),
                             ('Review status', row['status'])]),
        ('Provider-supplied conjunction data', [('Provider', row['source']),
            ('Source record ID', row['external_id']), ('Primary NORAD ID', row['primary_norad']),
            ('Secondary NORAD ID', row['secondary_norad']), ('TCA UTC', row['tca']),
            ('Miss distance metres', row['miss_distance_m']),
            ('Relative speed metres per second', row['relative_speed_m_s']),
            ('Covariance supplied', fields.get('covariance_present'))]),
        ('Source provenance', [('Format', raw.get('format') if isinstance(raw, dict) else None),
            ('Source SHA-256', raw.get('sha256') if isinstance(raw, dict) else None),
            ('Filename', row['filename']), ('Parser version', row['parser_version']),
            ('CDM creation UTC', fields.get('created_at')), ('Uploaded UTC', row['source_uploaded_at']),
            ('Event imported UTC', row['created_at']), ('Event updated UTC', row['updated_at'])]),
        ('Method and limitations', [
            ('Method', 'Source record transcription and deterministic metadata extraction'),
            ('Collision probability', 'Unavailable: no validated uncertainty calculation'),
            ('Limitations', 'Provider values are not independently verified; no maneuver recommendation'),
        ]),
    ]
    return Response(render_pdf('Conjunction event report', sections), media_type='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="astrocomply-event-{event_id}.pdf"'})
