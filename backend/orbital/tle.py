"""TLE validation and SGP4 position conversion for display.

SGP4 returns a TEME state. Skyfield converts that state to WGS84 geodetic
latitude, longitude and height. These are predictions from mean elements,
not observations or precision orbit determination.
"""
from datetime import datetime, timezone
from math import isfinite
from sgp4.api import Satrec, SGP4_ERRORS, jday
from sgp4.conveniences import sat_epoch_datetime
from sgp4.earth_gravity import wgs72
from sgp4.io import twoline2rv, verify_checksum
from skyfield.api import EarthSatellite, load, wgs84
import sgp4
import skyfield

TIMESCALE = load.timescale(builtin=True)
MAX_ELEMENT_AGE_DAYS = 14


class TLEValidationError(ValueError):
    pass


def parse_tle(content: str) -> dict:
    if len(content.encode('utf-8')) > 4096:
        raise TLEValidationError('TLE exceeds 4 KB')
    lines = [line.strip('\r\n') for line in content.splitlines() if line.strip()]
    if len(lines) == 3 and not lines[0].startswith('1 '):
        lines = lines[1:]
    if len(lines) != 2:
        raise TLEValidationError('Expected a two-line element set')
    first, second = lines
    try:
        if len(first) != 69 or len(second) != 69 or not first.startswith('1 ') or not second.startswith('2 '):
            raise ValueError('Invalid line length or prefix')
        if not all(line.isascii() and line[-1].isdigit() for line in lines):
            raise ValueError('Missing checksum')
        verify_checksum(first, second)
        twoline2rv(first, second, wgs72)
        sat = Satrec.twoline2rv(first, second)
        if not (sat.no_kozai > 0 and 0 <= sat.ecco < 1 and 0 <= sat.inclo <= 3.141592653589793):
            raise ValueError('Invalid orbital elements')
        epoch = sat_epoch_datetime(sat).astimezone(timezone.utc)
    except (ValueError, IndexError, OverflowError, ZeroDivisionError) as error:
        raise TLEValidationError(f'Invalid TLE format, checksum or orbital elements: {error}') from error
    return {'line1': first, 'line2': second, 'norad_id': sat.satnum, 'epoch': epoch}


def propagate(tle: dict, at: datetime) -> dict:
    at = at.astimezone(timezone.utc)
    sat = Satrec.twoline2rv(tle['line1'], tle['line2'])
    jd, fraction = jday(at.year, at.month, at.day, at.hour, at.minute, at.second + at.microsecond / 1e6)
    error, position, velocity = sat.sgp4(jd, fraction)
    if error or not all(isfinite(value) for value in (*position, *velocity)):
        raise TLEValidationError(SGP4_ERRORS.get(error, 'Unable to compute a finite state vector'))
    sky_sat = EarthSatellite(tle['line1'], tle['line2'], ts=TIMESCALE)
    geocentric = sky_sat.at(TIMESCALE.from_datetime(at))
    location = wgs84.geographic_position_of(geocentric)
    lat, lon, height = (float(location.latitude.degrees), float(location.longitude.degrees),
                        float(location.elevation.km))
    if not all(isfinite(value) for value in (lat, lon, height)):
        raise TLEValidationError('Unable to compute a finite geographic position')
    seconds_from_epoch = (at - tle['epoch']).total_seconds()
    return {'at': at, 'epoch': tle['epoch'], 'seconds_from_epoch': seconds_from_epoch,
            'state': 'stale' if abs(seconds_from_epoch) > MAX_ELEMENT_AGE_DAYS * 86400 else 'propagated',
            'frame': 'TEME', 'position_km': position, 'velocity_km_s': velocity,
            'geodetic_frame': 'WGS84', 'latitude_deg': lat, 'longitude_deg': lon,
            'altitude_km': height, 'method': 'SGP4/WGS72',
            'software': {'sgp4': sgp4.__version__, 'skyfield': skyfield.__version__},
            'quality': 'Predicted from uploaded mean elements; accuracy degrades with element age and maneuvers.'}
