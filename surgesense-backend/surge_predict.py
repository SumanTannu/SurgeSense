# surge_main_agent.py

"""
SURGE-SENSE Agent for hospitals.

Features:
- Pydantic schemas for tool inputs/outputs
- Tools for:
    - Latest hospital state (synthetic JSON)
    - Environment (weather + AQI) for a city
    - Upcoming Indian holidays/festivals
- Custom ReAct-style agent with JSON-only action inputs
- Final JSON schema for surge risk recommendations
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import holidays
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import BaseTool
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

# --------------------------------------------------------------------
# ENV + CONFIG
# --------------------------------------------------------------------
load_dotenv()

FILE_NAME = os.getenv("HOSPITAL_DATA_FILE", "hospital_synthetic_data.json")
AQICN_TOKEN = os.getenv("AQICN_TOKEN")
CALENDARIFIC_API_KEY = os.getenv("CALENDARIFIC_API_KEY")
COUNTRY = os.getenv("COUNTRY_CODE", "IN")

LLM_BASE_URL = os.getenv("LLM_BASE_URL")
LLM_MODEL = os.getenv("LLM_MODEL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS"))

llm: BaseChatModel = ChatOpenAI(
    base_url=LLM_BASE_URL,
    model=LLM_MODEL,
    api_key=LLM_API_KEY,
    temperature=LLM_TEMPERATURE,
    max_tokens=LLM_MAX_TOKENS,
)

# --------------------------------------------------------------------
# CORE UTILS
# --------------------------------------------------------------------
def read_latest_record() -> Dict[str, Any]:
    """Read the latest hospital synthetic record from JSON file."""
    if not os.path.exists(FILE_NAME):
        raise FileNotFoundError(f"Dataset file '{FILE_NAME}' missing.")

    with open(FILE_NAME, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not data:
        raise ValueError("Dataset is empty.")

    return data[-1]


def get_coords(city_name: str) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
    """Geocode city name to (lat, lon, resolved_city, country)."""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    response = requests.get(url, params={"name": city_name, "count": 1}, timeout=10)
    payload = response.json()

    if payload.get("results"):
        result = payload["results"][0]
        return (
            result["latitude"],
            result["longitude"],
            result["name"],
            result["country"],
        )

    return None, None, None, None


def get_forecast(lat: float, lon: float, timezone: str = "Asia/Kolkata") -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Get 5-day weather + air-quality forecast from Open-Meteo."""
    weather_url = "https://api.open-meteo.com/v1/forecast"
    aqi_url = "https://air-quality-api.open-meteo.com/v1/air-quality"

    weather_response = requests.get(
        weather_url,
        params={
            "latitude": lat,
            "longitude": lon,
            "timezone": timezone,
            "forecast_days": 5,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        },
        timeout=10,
    )
    weather = weather_response.json()

    aqi_response = requests.get(
        aqi_url,
        params={
            "latitude": lat,
            "longitude": lon,
            "timezone": timezone,
            "forecast_days": 5,
            "hourly": "european_aqi,pm10,pm2_5",
        },
        timeout=10,
    )
    aqi = aqi_response.json()

    return weather, aqi


def get_live_aqi(city: str) -> Optional[Dict[str, Any]]:
    """Get live AQI from AQICN if token is configured."""
    if not AQICN_TOKEN:
        return None

    url = f"https://api.waqi.info/feed/{city}/"
    try:
        response = requests.get(url, params={"token": AQICN_TOKEN}, timeout=10)
        payload = response.json()

        if payload.get("status") != "ok":
            return None

        data = payload["data"]
        return {
            "aqi": data.get("aqi"),
            "pm25": data.get("iaqi", {}).get("pm25", {}).get("v"),
            "pm10": data.get("iaqi", {}).get("pm10", {}).get("v"),
        }
    except Exception:  # noqa: BLE001
        return None


def classify_aqi(value: Optional[int]) -> str:
    """Return qualitative AQI category."""
    if value is None:
        return "Unknown"
    if value <= 50:
        return "Good"
    if value <= 100:
        return "Moderate"
    if value <= 150:
        return "Unhealthy for Sensitive Groups"
    if value <= 200:
        return "Unhealthy"
    if value <= 300:
        return "Very Unhealthy"
    return "Hazardous"


def get_public_holidays(year: int) -> Dict[datetime.date, str]:
    """Return mapping of Indian public holidays for the given year."""
    india_holidays = holidays.India(years=year)
    return {date: f"Public Holiday: {name}" for date, name in india_holidays.items()}


def get_festivals(year: int) -> Dict[datetime.date, List[str]]:
    """Return mapping of festival/holiday dates to labels using Calendarific."""
    if not CALENDARIFIC_API_KEY:
        return {}

    url = "https://calendarific.com/api/v2/holidays"
    response = requests.get(
        url,
        params={
            "api_key": CALENDARIFIC_API_KEY,
            "country": COUNTRY,
            "year": year,
        },
        timeout=10,
    )
    payload = response.json()

    festivals: Dict[datetime.date, List[str]] = {}
    for holiday in payload["response"]["holidays"]:
        date_obj = datetime.fromisoformat(holiday["date"]["iso"]).date()
        name = holiday["name"]
        category = holiday["type"]

        if any(kind in category for kind in ["religious", "observance", "national", "local", "government"]):
            festivals.setdefault(date_obj, []).append(f"Festival: {name}")

    return festivals


def build_indian_calendar(year: int) -> Dict[datetime.date, List[str]]:
    """Combine public holidays and festivals into a single date -> events map."""
    public = get_public_holidays(year)
    festivals = get_festivals(year)

    combined: Dict[datetime.date, List[str]] = {}

    for date, name in public.items():
        combined.setdefault(date, []).append(name)

    for date, events in festivals.items():
        for event in events:
            if event not in combined.get(date, []):
                combined.setdefault(date, []).append(event)

    return dict(sorted(combined.items()))


# --------------------------------------------------------------------
# Pydantic Schemas (Tool Inputs/Outputs)
# --------------------------------------------------------------------
class GetEnvironmentInput(BaseModel):
    city: str = Field(description="Name of the city to fetch environment data for.")


class GetEnvironmentOutput(BaseModel):
    location: Dict[str, Any]
    weather: Dict[str, Any]
    air_quality: Dict[str, Any]


class GetCalendarEventsInput(BaseModel):
    days_ahead: int = Field(
        default=30,
        description="Number of days from today to look ahead for holidays/festivals.",
    )


class GetCalendarEventsOutput(BaseModel):
    from_date: str = Field(description="Start date of the window (YYYY-MM-DD).")
    to_date: str = Field(description="End date of the window (YYYY-MM-DD).")
    events: Dict[str, List[str]] = Field(
        description="Mapping date -> list of event descriptions.",
    )
    message: Optional[str] = None


class GetHospitalStateInput(BaseModel):
    dummy: Optional[str] = Field(
        default=None,
        description="No actual input required; kept for JSON compatibility.",
    )


class GetHospitalStateOutput(BaseModel):
    hospital_metrics: Dict[str, Any]
    resources_and_supplies: Dict[str, Any]


# --------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------
class GetEnvironmentTool(BaseTool):
    """Retrieve environment data (weather + AQI) for a given city."""

    name: str = "get_environment_tool"
    description: str = (
        "Get environment conditions (min/max temperature, rainfall, live/forecast AQI) "
        'for an Indian city. Input MUST be a JSON string like {"city": "Mumbai"}.'
    )

    def _run(self, tool_input: str) -> str:  # type: ignore[override]
        try:
            parsed_input = json.loads(tool_input)
            validated = GetEnvironmentInput(**parsed_input)
            city = validated.city.strip()

            lat, lon, resolved_city, country = get_coords(city)
            if lat is None:
                return json.dumps(
                    {
                        "status": "error",
                        "message": f"City '{city}' not found.",
                    },
                )

            weather_data, forecast_data = get_forecast(lat, lon)
            min_temp = min(weather_data["daily"]["temperature_2m_min"])
            max_temp = max(weather_data["daily"]["temperature_2m_max"])
            rainfall = sum(weather_data["daily"]["precipitation_sum"])

            live = get_live_aqi(city)
            forecast_aqi = forecast_data["hourly"]["european_aqi"][0]
            status_label = classify_aqi(forecast_aqi)

            env_output = GetEnvironmentOutput(
                location={
                    "city": resolved_city,
                    "country": country,
                    "lat": lat,
                    "lon": lon,
                },
                weather={
                    "min_temp": min_temp,
                    "max_temp": max_temp,
                    "rainfall_mm": rainfall,
                },
                air_quality=live
                or {
                    "aqi": forecast_aqi,
                    "status": status_label,
                },
            )

            return json.dumps(
                {
                    "status": "success",
                    "data": env_output.model_dump(),
                },
            )

        except (json.JSONDecodeError, ValidationError) as exc:
            return json.dumps(
                {
                    "status": "error",
                    "message": (
                        "Invalid input for GetEnvironmentTool: "
                        f"{exc}. Raw input: {tool_input}"
                    ),
                },
            )
        except Exception as exc:  # noqa: BLE001
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Unexpected error in GetEnvironmentTool: {exc}",
                },
            )


class GetCalendarEventsTool(BaseTool):
    """Retrieve upcoming public holidays and festivals in India."""

    name: str = "get_calendar_events_tool"
    description: str = (
        "Get upcoming Indian public holidays and festivals for the next N days. "
        'Input MUST be a JSON string like {"days_ahead": 30}.'
    )

    def _run(self, tool_input: str) -> str:  # type: ignore[override]
        try:
            parsed_input = json.loads(tool_input)
            validated = GetCalendarEventsInput(**parsed_input)
            days_ahead = validated.days_ahead

            today = datetime.now().date()
            year = today.year
            calendar = build_indian_calendar(year)

            upcoming: Dict[str, List[str]] = {}
            for date, events in calendar.items():
                if today <= date <= today + timedelta(days=days_ahead):
                    upcoming[str(date)] = events

            message: Optional[str] = None
            if not upcoming:
                message = "No festivals or holidays in the selected window."

            output = GetCalendarEventsOutput(
                from_date=str(today),
                to_date=str(today + timedelta(days=days_ahead)),
                events=upcoming,
                message=message,
            )

            return json.dumps(
                {
                    "status": "success",
                    "data": output.model_dump(),
                },
            )

        except (json.JSONDecodeError, ValidationError) as exc:
            return json.dumps(
                {
                    "status": "error",
                    "message": (
                        "Invalid input for GetCalendarEventsTool: "
                        f"{exc}. Raw input: {tool_input}"
                    ),
                },
            )
        except Exception as exc:  # noqa: BLE001
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Unexpected error in GetCalendarEventsTool: {exc}",
                },
            )


class GetHospitalStateTool(BaseTool):
    """Retrieve the latest synthetic hospital state from local JSON."""

    name: str = "get_hospital_state_tool"
    description: str = (
        "Get the latest hospital metrics and resources from local synthetic dataset. "
        'Input MUST be a JSON string (contents ignored), e.g. {}.'
    )

    def _run(self, tool_input: str) -> str:  # type: ignore[override]
        try:
            if tool_input.strip():
                try:
                    parsed_input = json.loads(tool_input)
                    GetHospitalStateInput(**parsed_input)
                except Exception:  # noqa: BLE001
                    pass

            latest = read_latest_record()
            hospital_metrics = latest.get("hospital_metrics", {})
            resources = latest.get("resources_and_supplies", {})

            output = GetHospitalStateOutput(
                hospital_metrics=hospital_metrics,
                resources_and_supplies=resources,
            )

            return json.dumps(
                {
                    "status": "success",
                    "data": output.model_dump(),
                },
            )

        except FileNotFoundError as exc:
            return json.dumps(
                {
                    "status": "error",
                    "message": str(exc),
                },
            )
        except Exception as exc:  # noqa: BLE001
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Unexpected error in GetHospitalStateTool: {exc}",
                },
            )


# --------------------------------------------------------------------
# ReAct Prompt (with JSON Action Input + Surge JSON Final Answer)
# --------------------------------------------------------------------
REACT_PROMPT_TEMPLATE = """
You are SURGE-SENSE, a medical surge prediction and planning AI agent for hospitals.

Your role is to analyze multi-source data and predict possible patient surges
and operational strain within the next 1–5 days.

You base decisions ONLY on:
- Hospital load and patient mix
- Staff capacity
- Supply availability
- Weather and pollution trends (especially AQI)
- Upcoming public holidays or festivals
- Typical epidemiological patterns (injuries during festivals, respiratory cases during high AQI, pediatric spikes during flu seasons)

You have access to the following tools:

{tools}

Use the following format exactly:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action, MUST be valid JSON format like {{"a": 5, "b": 3}}
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

IMPORTANT RULES FOR TOOL USAGE:
- For environment queries, ALWAYS use get_environment_tool with JSON: {{"city": "<CITY_NAME>"}}.
- For upcoming holidays/festivals, use get_calendar_events_tool with JSON: {{"days_ahead": 30}} (or other integer).
- For hospital internal state, use get_hospital_state_tool with JSON: {{}}.
- NEVER pass plain text as Action Input. It must always be valid JSON.

FINAL ANSWER FORMAT (STRICT):
Your Final Answer MUST be ONLY valid JSON with this exact structure:

{{
  "risk_level": "",
  "confidence_score": 0,
  "drivers": [],
  "predicted_impacts": [],
  "operational_actions": [],
  "supply_actions": [],
  "patient_advisory": "",
  "summary": ""
}}

- risk_level: "Low" | "Moderate" | "High" | "Critical"
- confidence_score: integer 0–100
- drivers: list of key factors driving the surge risk
- predicted_impacts: list of department-level impacts (e.g., "Emergency", "Respiratory", "Pediatrics")
- operational_actions: list of concrete staffing/bed/protocol recommendations
- supply_actions: list of supply/logistics recommendations
- patient_advisory: <= 90 words, simple language for the public
- summary: 1-sentence admin briefing (max 20 words)

Tone: calm, clinical, professional. Do NOT mention AI, models, or guesses.

Begin!

Question: {input}
Thought:{agent_scratchpad}
"""

react_prompt = PromptTemplate.from_template(REACT_PROMPT_TEMPLATE)

# --------------------------------------------------------------------
# Agent Setup
# --------------------------------------------------------------------
tools: List[BaseTool] = [
    GetEnvironmentTool(),
    GetCalendarEventsTool(),
    GetHospitalStateTool(),
]

agent = create_react_agent(
    llm=llm,
    tools=tools,
    prompt=react_prompt,
)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    max_iterations=30,
    handle_parsing_errors=True,
    return_intermediate_steps=True,
)

# --------------------------------------------------------------------
# Manual Test
# --------------------------------------------------------------------
if __name__ == "__main__":
    print("--- Running SURGE-SENSE Agent ---")

    city = "Mumbai"
    query = (
        f"Using all relevant tools, assess the surge risk for hospitals in {city} "
        "for the next 1–5 days and recommend actions."
    )

    result = agent_executor.invoke({"input": query})

    print("\n--- Final JSON Output ---")
    print(result["output"])

    print("\n--- Intermediate Steps (Tools used) ---")
    for action, observation in result.get("intermediate_steps", []):
        print(f"\nTool: {action.tool}")
        print(f"Tool Input: {action.tool_input}")
        print(f"Observation: {observation}")
