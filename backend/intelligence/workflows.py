"""Deterministic, tenant-scoped investigation tools and evidence traces."""
from datetime import datetime, timezone
from sqlalchemy import text
from backend.api.routes.orbital_assets import _position


def execute(job: dict, connection) -> tuple[dict, list[dict]]:
    workflow = job['workflow']
    if workflow == 'conjunction_investigation':
        event = connection.execute(text('''SELECT id,source,external_id,primary_norad,secondary_norad,tca,
            miss_distance_m,relative_speed_m_s,collision_probability,raw_data,status
            FROM conjunction_events WHERE id=:id AND organization_id=:org'''),
            {'id': job['event_id'], 'org': job['organization_id']}).mappings().first()
        if not event:
            raise ValueError('Event no longer exists in workspace')
        evidence = {key: value for key, value in dict(event).items() if key != 'raw_data'}
        evidence['tca'] = evidence['tca'].isoformat()
        source_metadata = event['raw_data'] or {}
        steps = [
            {'tool': 'get_conjunction_event', 'status': 'complete', 'source': event['source'],
             'external_id': event['external_id'], 'event_id': event['id']},
            {'tool': 'inspect_uncertainty', 'status': 'complete',
             'covariance_present': bool(source_metadata.get('fields', {}).get('covariance_present')),
             'probability_available': event['collision_probability'] is not None},
        ]
        conclusion = (f"Provider {event['source']} reports a closest approach at {evidence['tca']} "
                      f"with miss distance {event['miss_distance_m']} m. "
                      'Insufficient data for reliable probability-of-collision estimation. '
                      'Operator review of the original CDM and updated orbital data is required.')
        result = {'query': job['query'], 'workflow': workflow, 'evidence': evidence,
                  'conclusion': conclusion, 'interpretation': 'deterministic',
                  'limitations': ['No validated probability calculation',
                                  'No independently verified covariance or ephemeris']}
        return result, steps

    if workflow in ('satellite_investigation', 'mission_analysis'):
        row = connection.execute(text('''SELECT f.id AS asset_id,f.display_name,
            e.norad_id,e.line1,e.line2,e.epoch,e.source,e.filename,e.sha256,e.uploaded_at
            FROM fleet_assets f LEFT JOIN LATERAL (
              SELECT norad_id,line1,line2,epoch,source,filename,sha256,uploaded_at
              FROM fleet_orbital_elements WHERE organization_id=:org AND asset_id=f.id
              ORDER BY uploaded_at DESC,id DESC LIMIT 1
            ) e ON true WHERE f.id=:asset AND f.organization_id=:org AND f.archived_at IS NULL'''),
            {'org': job['organization_id'], 'asset': job['asset_id']}).mappings().first()
        if not row:
            raise ValueError('Fleet asset no longer exists in workspace')
        position = _position(dict(row), datetime.now(timezone.utc))
        steps = [{'tool': 'get_fleet_asset', 'status': 'complete', 'asset_id': row['asset_id']},
                 {'tool': 'propagate_uploaded_tle', 'status': position['status'],
                  'source': row['source'], 'sha256': row['sha256'], 'epoch': str(row['epoch'])}]
        evidence = {key: value.isoformat() if hasattr(value, 'isoformat') else value
                    for key, value in position.items()}
        if workflow == 'mission_analysis':
            event_count = connection.execute(text('''SELECT count(*) FROM conjunction_events
                WHERE organization_id=:org AND status <> 'resolved'
                AND (primary_norad=:norad OR secondary_norad=:norad)'''),
                {'org': job['organization_id'], 'norad': row['norad_id']}).scalar_one() if row['norad_id'] else 0
            evidence['unresolved_provider_events'] = event_count
            steps.append({'tool': 'count_unresolved_conjunction_events', 'status': 'complete',
                          'norad_id': row['norad_id'], 'count': event_count})
            conclusion = (f"Asset {row['display_name']} has {event_count} unresolved provider event(s). "
                          f"Uploaded element state: {position['status']}. This is a data readiness review, "
                          'not a licensing or maneuver decision.')
        else:
            conclusion = (f"Asset {row['display_name']} has uploaded element state "
                          f"{position['status']}. Review source and epoch before operational use.")
        return {'query': job['query'], 'workflow': workflow, 'evidence': evidence,
                'conclusion': conclusion, 'interpretation': 'deterministic',
                'limitations': ['Uploaded TLE is not an observation',
                                'No precision orbit determination or collision probability']}, steps

    if workflow == 'fleet_health':
        rows = connection.execute(text('''SELECT f.id,f.display_name,e.epoch,e.source,e.sha256
            FROM fleet_assets f LEFT JOIN LATERAL (
              SELECT epoch,source,sha256 FROM fleet_orbital_elements
              WHERE organization_id=:org AND asset_id=f.id ORDER BY uploaded_at DESC,id DESC LIMIT 1
            ) e ON true WHERE f.organization_id=:org AND f.archived_at IS NULL ORDER BY f.id LIMIT 200'''),
            {'org': job['organization_id']}).mappings()
        now = datetime.now(timezone.utc)
        assets = [{'asset_id': row['id'], 'name': row['display_name'], 'source': row['source'],
                   'sha256': row['sha256'], 'epoch': row['epoch'].isoformat() if row['epoch'] else None,
                   'status': 'unavailable' if not row['epoch'] else
                   'stale' if abs((now - row['epoch']).total_seconds()) > 14 * 86400 else 'current'}
                  for row in rows]
        counts = {state: sum(asset['status'] == state for asset in assets)
                  for state in ('current', 'stale', 'unavailable')}
        evidence = {'assets': assets, 'counts': counts, 'checked_at': now.isoformat()}
        steps = [{'tool': 'list_fleet_elements', 'status': 'complete', 'count': len(assets)}]
        conclusion = (f"Fleet has {counts['current']} asset(s) with recent elements, "
                      f"{counts['stale']} stale, and {counts['unavailable']} without uploaded elements.")
        return {'query': job['query'], 'workflow': workflow, 'evidence': evidence,
                'conclusion': conclusion, 'interpretation': 'deterministic',
                'limitations': ['Element recency is a data quality indicator, not a health or collision assessment']}, steps

    if workflow == 'regulatory_research':
        from knowledge_layer.rag_service import search_regulations
        try:
            references = search_regulations(job['query'], top_k=5)
        except Exception as error:
            raise ValueError(f'Regulation retrieval provider unavailable: {error}') from error
        evidence = {'references': references}
        steps = [{'tool': 'search_regulations', 'status': 'complete',
                  'sources': [item.get('source') for item in references]}]
        conclusion = (f"Retrieved {len(references)} regulation excerpt(s). "
                      'Review source documents for applicability; no legal conclusion was generated.')
        return {'query': job['query'], 'workflow': workflow, 'evidence': evidence,
                'conclusion': conclusion, 'interpretation': 'deterministic retrieval',
                'limitations': ['Search excerpts are not a legal determination',
                                'No LLM interpretation was requested']}, steps
    raise ValueError(f'Unsupported workflow: {workflow}')
