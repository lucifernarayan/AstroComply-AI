from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.routes import uipath
from backend.database.catalogue import CatalogueUnavailable
from knowledge_layer.agents.forecast_agent import run_forecast_agent


def test_raw_analysis_and_regulation_search():
    client = TestClient(app)
    response = client.post("/analyze/raw", json={"mean_motion": 15.5})
    assert response.status_code == 200
    results = client.get("/regulations/search", params={"q": "orbital debris disposal"}).json()["results"]
    assert results and all(hit["text"] and hit["document"] for hit in results)


def test_catalogue_outage_is_visible():
    with patch("backend.api.routes.satellites.repo.get_count", side_effect=CatalogueUnavailable("Unavailable")):
        assert TestClient(app).get("/satellites/count").status_code == 503


def test_forecast_withholds_collision_probability():
    with patch("knowledge_layer.agents.forecast_agent.ChatGroq", side_effect=RuntimeError):
        forecast = run_forecast_agent({})["forecast"]
    assert all(row["projected_collision_prob_per_yr"] is None for row in forecast["projections"].values())
    assert "Insufficient data" in forecast["collision_probability_status"]


def test_incomplete_assessment_cannot_autoapprove(monkeypatch):
    monkeypatch.setitem(uipath.uipath_jobs, "test-job", {})
    monkeypatch.setattr(uipath, "run_full_assessment", lambda **kwargs: {"errors": ["Missing evidence"]})
    uipath.run_uipath_audit_background("test-job", {}, 50)
    assert uipath.uipath_jobs["test-job"]["status"] == "FAILED"


def test_tle_propagation_validates_and_labels_state():
    client = TestClient(app)
    tle = {
        "line1": "1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991",
        "line2": "2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482",
        "at": "2019-12-09T20:42:00Z",
    }
    response = client.post("/propagation/tle", json=tle)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["norad_id"] == 25544
    assert result["frame"] == "TEME"
    assert result["method"] == "SGP4/WGS72"
    assert len(result["position_km"]) == len(result["velocity_km_s"]) == 3
    assert client.post("/propagation/tle", json={**tle, "line1": tle["line1"][:-1] + "0"}).status_code == 422
