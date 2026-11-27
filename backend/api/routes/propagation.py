from datetime import datetime, timezone
from math import isfinite

from fastapi import APIRouter, HTTPException
from pydantic import AwareDatetime, BaseModel, Field
from sgp4.api import Satrec, SGP4_ERRORS, jday
from sgp4.conveniences import sat_epoch_datetime
from sgp4.earth_gravity import wgs72
from sgp4.io import twoline2rv, verify_checksum

router = APIRouter()


class PropagationRequest(BaseModel):
    line1: str = Field(min_length=69, max_length=69)
    line2: str = Field(min_length=69, max_length=69)
    at: AwareDatetime | None = None


@router.post("/tle", summary="Propagate a supplied TLE at one UTC instant")
def propagate_tle(request: PropagationRequest):
    first, second = request.line1, request.line2
    try:
        if not all(line.isascii() and line[-1].isdigit() for line in (first, second)):
            raise ValueError("Missing TLE checksum")
        verify_checksum(first, second)
        # The strict parser checks field placement and matching catalogue identifiers.
        twoline2rv(first, second, wgs72)
        sat = Satrec.twoline2rv(first, second)
        if not (sat.no_kozai > 0 and 0 <= sat.ecco < 1 and 0 <= sat.inclo <= 3.141592653589793):
            raise ValueError("Invalid orbital elements")
        epoch = sat_epoch_datetime(sat)
    except (ValueError, IndexError, OverflowError, ZeroDivisionError):
        raise HTTPException(422, "Invalid TLE format, checksum or orbital elements.")

    at = (request.at or epoch).astimezone(timezone.utc)
    jd, fraction = jday(at.year, at.month, at.day, at.hour, at.minute, at.second + at.microsecond / 1e6)
    error, position, velocity = sat.sgp4(jd, fraction)
    if error or not all(isfinite(value) for value in (*position, *velocity)):
        raise HTTPException(422, SGP4_ERRORS.get(error, "Unable to compute a finite state vector."))
    return {
        "norad_id": sat.satnum, "source": "user-supplied TLE", "epoch": epoch, "at": at,
        "seconds_from_epoch": (at - epoch).total_seconds(), "method": "SGP4/WGS72",
        "frame": "TEME", "position_km": position, "velocity_km_s": velocity,
        "quality": "Predicted state from mean elements. Accuracy depends on element age and orbit changes.",
    }
