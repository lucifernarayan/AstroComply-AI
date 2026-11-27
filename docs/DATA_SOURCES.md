# Data sources and orbital limits

The bundled `data/raw/celestrak_active.json` holds 15,680 CelesTrak GP JSON records dated June 2026. The snapshot loader now validates identity, epoch and core elements, processes all records, skips older epochs and logs partial imports. It stores the latest catalogue state and derived element rows. The schema still needs source provenance and immutable observation revisions before operational use.

`POST /propagation/tle` accepts a checksum-valid TLE pair and an optional timezone-aware time. The response contains SGP4 position and velocity in the TEME frame, source epoch and time offset. These coordinates must be transformed before plotting on an Earth-fixed globe. Element age, maneuvers and tracking quality affect accuracy. The endpoint does not estimate uncertainty or collision probability. [SGP4 package documentation](https://pypi.org/project/sgp4/)

The packaged regulatory JSON is searched lexically. Returned scores indicate ranking within one result set. Document versions, jurisdictions and page references need a controlled publishing workflow before a compliance conclusion can be relied on.
