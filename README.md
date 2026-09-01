# SURGE-SENSE: Hospital Surge Prediction Agent

**SURGE-SENSE** is an AI-powered agent designed to predict patient surges and operational strain in hospitals. It utilizes a **ReAct (Reasoning + Acting)** architecture to analyze multi-source data—including internal hospital metrics, real-time weather/pollution data, and upcoming holidays—to provide actionable risk assessments and resource recommendations.

## 📋 Features

*   **Intelligent Agent:** Uses LangChain and OpenAI to reason through data and formulate clinical recommendations.
*   **Multi-Source Data Integration:**
    *   **Internal:** Analyzes bed occupancy, OPD visits, and supply levels (PPE, Blood Bank, Vaccines).
    *   **Environmental:** Fetches real-time weather and Air Quality Index (AQI) via Open-Meteo and AQICN.
    *   **Social:** Tracks upcoming public holidays and festivals via Calendarific to predict crowd-related incidents.
*   **Synthetic Data Generator:** Includes a script to generate realistic, time-series hospital data for testing and simulation.
*   **REST API:** Exposes the agent via a FastAPI interface for easy integration with front-end dashboards.
*   **Structured Output:** Returns strict JSON responses containing risk levels, confidence scores, and specific operational actions.

## 📂 Project Structure

```text
.
├── api.py                      # FastAPI server entry point
├── surge_predict.py            # Main LangChain Agent logic and Tool definitions
├── synthetic_data.py           # Script to generate realistic hospital data streams
├── testing.py                  # Client script to test the API
├── hospital_synthetic_data.json # Database file (auto-generated)
├── requirements.txt            # Python dependencies
└── .env                        # Environment variables (not included in repo)
```


## 🛠️ Prerequisites

*   Python 3.9+
*   Node.js & npm (for frontend dashboard)
*   An OpenAI API Key
*   (Optional) AQICN Token for live air quality data
*   (Optional) Calendarific API Key for holiday data


## 🚀 Installation

### 1. Clone the repository
```bash
git clone https://github.com/himpar21/SurgeSense.git
cd MumbaiHacks
```

### 2. Backend Setup (FastAPI)

```bash
cd code
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Frontend Setup (React Dashboard)

```bash
cd ../surgesense-frontend
npm install
```

---


## ⚙️ Configuration

Create a `.env` file in the `code/` directory (backend root). You can copy the structure below:

```ini
# --- LLM Configuration ---
SURGE_APP_TITLE="SURGE-SENSE API"
SURGE_SERVER_HOST="0.0.0.0"
SURGE_SERVER_PORT="8000"
SURGE_SERVER_RELOAD="false"
HOSPITAL_DATA_FILE="hospital_synthetic_data.json"
CALENDARIFIC_API_KEY="API_KEY"
AQICN_TOKEN="API_KEY"
LLM_BASE_URL="https://api.pipeshift.com/api/v0/"
LLM_MODEL="neysa-qwen3-vl-30b-a3b"
LLM_API_KEY="API_KEY"
LLM_TEMPERATURE="0.0"
LLM_MAX_TOKENS="1500"
COUNTRY_CODE="IN"
HOSPITAL_DATA_FILE="hospital_synthetic_data.json"
HOSPITAL_GENERATOR_INTERVAL_SEC="300"   # e.g. 300 for 5 minutes
SURGE_API_URL="http://localhost:8000/surge"
SURGE_CITY="Mumbai"
SURGE_QUERY="Assess surge risk for the next 5 days and suggest actions."
```


## 🏃‍♂️ Usage

To run the full system, you typically need **three terminal windows**: one for generating data, one for the API server, and one for the React frontend.

### 1. Start the Data Generator (Backend)
This script simulates a live hospital environment, updating metrics like OPD visits and bed occupancy every few seconds.

```bash
cd code
python synthetic_data.py
```
*Output:* You will see logs indicating updated OPD and ICU metrics. Keep this running in the background.

### 2. Start the API Server (Backend)
This launches the FastAPI server that hosts the SURGE-SENSE agent.

```bash
cd code
uvicorn api:app --reload
```
*Output:* The server will start at `http://0.0.0.0:8000`.

### 3. Start the React Frontend Dashboard
This provides a user-friendly web interface for querying the agent and visualizing results.

```bash
cd surgesense-frontend
npm install axios
npm start
```
*Output:* The app will open at [http://localhost:3000](http://localhost:3000) and connect to the backend at `http://localhost:8000`.

### 4. Query the Agent (API or UI)

You can test the system using the provided test script, via `curl`, or directly from the React dashboard UI.

**Using the Python Test Script:**
```bash
cd code
python testing.py
```

**Using cURL:**
```bash
curl -X POST "http://localhost:8000/surge" \
  -H "Content-Type: application/json" \
  -d '{"query": "Analyze the surge risk for the next 3 days.", "city": "Mumbai"}'
```

**Using the React Dashboard:**

1. Open [http://localhost:3000](http://localhost:3000) in your browser.
2. Enter your query and city, then click "Run Surge Model".
3. View the risk assessment, recommendations, and step-by-step agent logs in the UI.

## 🧠 How It Works

1.  **Request:** The user sends a query (e.g., "Assess surge risk for Mumbai").
2.  **Agent Reasoning:** The LangChain agent receives the query and decides which tools to use based on the `REACT_PROMPT_TEMPLATE`.
3.  **Tool Execution:**
    *   **`get_hospital_state_tool`**: Reads the last entry from `hospital_synthetic_data.json` to understand current capacity (Bed occupancy, Staffing, Blood bank).
    *   **`get_environment_tool`**: Calls Open-Meteo/AQICN to check if weather (heatwaves, rain) or pollution (high AQI) might drive respiratory or vector-borne diseases.
    *   **`get_calendar_events_tool`**: Checks for festivals or holidays that might lead to mass gatherings or accidents.
4.  **Synthesis:** The LLM combines these insights. For example:
    *   *High AQI* + *Respiratory OPD spike* = **High Risk** for Respiratory Ward.
    *   *Upcoming Festival* + *Low Blood Bank Stock* = **Operational Warning**.
5.  **Response:** The agent outputs a structured JSON object containing the risk assessment and recommendations.


## 📡 API & Frontend Documentation


### `POST /surge`

Triggers the SURGE-SENSE agent.

**Request Body:**
```json
{
  "query": "string",      // The question for the agent
  "city": "string"        // Optional: Context city for weather/holidays
}
```

**Response Body:**
```json
{
  "query": "string",
  "city": "string",
  "agent_output": {
    "risk_level": "High",
    "confidence_score": 85,
    "drivers": ["High AQI", "Bed Occupancy > 90%"],
    "predicted_impacts": ["Respiratory Ward", "ICU"],
    "operational_actions": ["Increase nursing staff", "Open overflow ward"],
    "supply_actions": ["Restock N95 masks", "Order O- Blood"],
    "patient_advisory": "Avoid outdoor activities...",
    "summary": "Critical surge expected due to pollution and capacity limits."
  },
  "intermediate_steps": [...] // Trace of agent thoughts/actions
}
```

---

### Frontend (React) Project Structure

```
surgesense-frontend/
  ├── src/
  │   ├── App.js
  │   ├── SurgeAdvisor.jsx   # Main dashboard UI
  │   └── ...
  ├── public/
  ├── package.json
  └── ...
```

* The React app is configured to connect to the backend at `http://localhost:8000` by default. If you change backend ports, update the API URL in the frontend code.
* All agent logs and recommendations are visible in the dashboard UI.
