"""Bounded CCSDS 508.0-B-1 KVN reader for core conjunction fields."""
from datetime import datetime, timezone
from math import isfinite

class CDMValidationError(ValueError):
    pass


def parse_cdm_kvn(content: str) -> dict:
    if len(content.encode('utf-8')) > 1_000_000:
        raise CDMValidationError('CDM exceeds 1 MB')
    header = {}
    objects = []
    current = None
    for line_number, line in enumerate(content.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('COMMENT'):
            continue
        if line in {'META_START', 'META_STOP', 'DATA_START', 'DATA_STOP',
                    'COVARIANCE_START', 'COVARIANCE_STOP'}:
            continue
        if '=' not in line:
            raise CDMValidationError(f'Line {line_number} is not a KVN assignment')
        key, value = (part.strip() for part in line.split('=', 1))
        if not key or not value:
            raise CDMValidationError(f'Line {line_number} has an empty key or value')
        if key == 'OBJECT':
            current = {'OBJECT': value}
            objects.append(current)
        elif current is None:
            if key in header:
                raise CDMValidationError(f'Duplicate {key}')
            header[key] = value
        else:
            if key in current:
                raise CDMValidationError(f'Duplicate {key} for {current["OBJECT"]}')
            current[key] = value
    for key in ('CCSDS_CDM_VERS', 'CREATION_DATE', 'ORIGINATOR', 'MESSAGE_ID', 'TCA', 'MISS_DISTANCE'):
        if key not in header:
            raise CDMValidationError(f'Missing required {key}')
    if len(objects) != 2 or {item['OBJECT'] for item in objects} != {'OBJECT1', 'OBJECT2'}:
        raise CDMValidationError('Expected OBJECT1 and OBJECT2 sections')
    for item in objects:
        if not item.get('OBJECT_DESIGNATOR'):
            raise CDMValidationError(f'Missing OBJECT_DESIGNATOR for {item["OBJECT"]}')
    try:
        tca = datetime.fromisoformat(header['TCA'].replace('Z', '+00:00'))
        created = datetime.fromisoformat(header['CREATION_DATE'].replace('Z', '+00:00'))
        if tca.tzinfo is None or created.tzinfo is None:
            raise ValueError('UTC offset required')
        miss = float(header['MISS_DISTANCE'])
        speed = float(header['RELATIVE_SPEED']) if 'RELATIVE_SPEED' in header else None
        if not isfinite(miss) or miss < 0 or (speed is not None and (not isfinite(speed) or speed < 0)):
            raise ValueError('Invalid distance or speed')
    except ValueError as error:
        raise CDMValidationError(f'Invalid timestamp or measurement: {error}') from error
    return {
        'source': header['ORIGINATOR'], 'external_id': header['MESSAGE_ID'],
        'created_at': created.astimezone(timezone.utc).isoformat(),
        'tca': tca.astimezone(timezone.utc), 'miss_distance_m': miss,
        'relative_speed_m_s': speed,
        'objects': objects, 'version': header['CCSDS_CDM_VERS'],
        'covariance_present': all(any(key.startswith('COVARIANCE') or key in ('CR_R', 'CT_T', 'CN_N') for key in item) for item in objects),
        'provider_collision_probability': header.get('COLLISION_PROBABILITY'),
    }
