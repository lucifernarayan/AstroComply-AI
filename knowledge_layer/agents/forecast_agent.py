"""
forecast_agent.py
-----------------
Forecast Agent — Tool projections + LLM interpretation.

Tool layer:
  - Computes 5/10/25-year debris population growth estimates
  - Reports unavailable collision probability when uncertainty inputs are missing
  - Estimates future sustainability state

LLM layer:
  - Interprets what the numbers mean
  - Highlights inflection points and critical thresholds

Answers:
  - What happens if nothing changes?
  - What will collision risk look like in 25 years?
  - When does the orbital environment become critical?
"""

from datetime import datetime
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from backend.config import GROQ_API_KEY, GROQ_MODEL
from knowledge_layer.agents.state import MOSIPState


# Annual debris growth rate by orbit type (percent per year)
# Based on ESA/IADC 2024 Space Debris Environment Report trends
ANNUAL_DEBRIS_GROWTH = {
    "VLEO":    0.03,   # 3%/yr — partially offset by atmospheric drag
    "LEO":     0.05,   # 5%/yr — driven by mega-constellations
    "MEO":     0.01,   # 1%/yr — relatively stable
    "GEO":     0.02,   # 2%/yr — new slots filling up
    "HEO":     0.01,
    "UNKNOWN": 0.03,
}

def _project_population(orbit_type: str, current_count: int, years: int) -> int:
    """Compound growth projection for object count in this orbital shell."""
    rate = ANNUAL_DEBRIS_GROWTH.get(orbit_type, 0.03)
    projected = int(current_count * ((1 + rate) ** years))
    return projected


def _kessler_risk(orbit_type: str, current_count: int,
                  projected_5yr: int) -> str:
    """Assess Kessler syndrome risk based on growth trajectory."""
    if orbit_type not in ("LEO", "VLEO"):
        return "Not applicable for this orbit type"
    growth_pct = ((projected_5yr - current_count) / max(current_count, 1)) * 100
    if growth_pct > 30:
        return "HIGH — rapid debris accumulation could trigger cascade events within decades"
    if growth_pct > 15:
        return "MODERATE — concerning growth trajectory; active debris removal needed"
    return "LOW — growth within manageable bounds if disposal compliance improves"


def run_forecast_agent(state: MOSIPState) -> dict:
    """
    Forecast Agent node.
    Adds 'forecast' and appends to 'agent_timeline'.
    """
    orbital     = state.get("orbital_data", {})
    risk        = state.get("risk_data", {})
    congestion  = state.get("congestion_data", {})
    satellite   = state.get("satellite_data", {})
    population  = state.get("population_data", {})

    orbit_type    = orbital.get("orbit_type", "UNKNOWN")
    risk_score    = risk.get("risk_score", 50) or 50
    current_count = congestion.get("neighbor_count", 0)
    total_sats    = population.get("total_satellites", 0)

    # ── Tool-based projections ────────────────────────────────────────────────
    projections = {}
    for years in [5, 10, 25]:
        pop_projected  = _project_population(orbit_type, current_count, years)
        risk_projected = min(100, risk_score * (1 + ANNUAL_DEBRIS_GROWTH.get(orbit_type, 0.03)) ** years)

        projections[f"{years}yr"] = {
            "year":                        datetime.utcnow().year + years,
            "projected_objects_in_shell":  pop_projected,
            "shell_growth_pct":            round(((pop_projected - current_count) / max(current_count, 1)) * 100, 1),
            "projected_collision_prob_per_yr": None,
            "projected_risk_score":        round(risk_projected, 1),
        }

    kessler = _kessler_risk(orbit_type, current_count, projections["5yr"]["projected_objects_in_shell"])

    # ── LLM interpretation ────────────────────────────────────────────────────
    interpretation = ""
    try:
        llm = ChatGroq(api_key=GROQ_API_KEY, model=GROQ_MODEL,
                       temperature=0.3, max_tokens=500)

        prompt = f"""
Satellite orbit: {orbit_type} at {orbital.get("altitude_km", "N/A")} km
Current risk score: {risk_score}/100
Current objects in ±100km shell: {current_count}
Total tracked satellites: {total_sats}

5-year projection:
  - Objects in shell: {projections["5yr"]["projected_objects_in_shell"]}
  - Projected risk score: {projections["5yr"]["projected_risk_score"]}

10-year projection:
  - Objects in shell: {projections["10yr"]["projected_objects_in_shell"]}
  - Projected risk score: {projections["10yr"]["projected_risk_score"]}

25-year projection:
  - Objects in shell: {projections["25yr"]["projected_objects_in_shell"]}
  - Projected risk score: {projections["25yr"]["projected_risk_score"]}

Kessler risk assessment: {kessler}

Write a 3-4 sentence forecast interpretation covering:
1. The trajectory of orbital congestion for this satellite's shell
2. When (if ever) the situation becomes critical
3. What would change the forecast most (e.g., increased compliance, ADR missions)
Do not estimate collision probability. Be specific and technical. No bullet points.
"""
        msg = llm.invoke([
            SystemMessage(content="You are a space sustainability forecaster. Write concise, data-driven forecasts."),
            HumanMessage(content=prompt),
        ])
        interpretation = msg.content.strip()
    except Exception:
        interpretation = (
            f"Forecast computed without LLM. Over 25 years, "
            f"the {orbit_type} shell is projected to grow by "
            f"{projections['25yr']['shell_growth_pct']:.0f}%. "
            "This is an illustrative growth scenario."
        )

    forecast = {
        "orbit_type":              orbit_type,
        "collision_probability_status": "Insufficient data for reliable probability-of-collision estimation.",
        "baseline_risk_score":     risk_score,
        "kessler_syndrome_risk":   kessler,
        "projections":             projections,
        "interpretation":          interpretation,
        "assumptions": [
            f"Annual debris growth rate: {ANNUAL_DEBRIS_GROWTH.get(orbit_type, 0.03)*100:.1f}%/yr in {orbit_type}",
            "No active debris removal missions assumed",
            "Current disposal compliance rates maintained",
            "Illustrative constant-growth scenario; coefficients are unvalidated",
        ],
    }

    timeline_entry = {
        "agent":     "Forecast Agent",
        "status":    "complete",
        "timestamp": datetime.utcnow().isoformat(),
        "summary": (
            f"25yr outlook: Shell grows {projections['25yr']['shell_growth_pct']:.0f}% | "
            f"Kessler: {kessler[:30]}..."
        ),
    }

    return {
        "forecast": forecast,
        "agent_timeline": state.get("agent_timeline", []) + [timeline_entry],
    }
