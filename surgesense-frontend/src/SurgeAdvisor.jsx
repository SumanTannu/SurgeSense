import React, { useState } from "react";

const API_BASE_URL = "http://localhost:8000";

export default function SurgeAdvisor() {
  const [city, setCity] = useState("Delhi");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const res = await fetch(`${API_BASE_URL}/surge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ city, query }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Request failed.");
      }

      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const getRiskColor = (risk) => {
    if (!risk) return "#6b7280";
    switch (risk?.toLowerCase()) {
      case "low": return "#22c55e";
      case "moderate": return "#eab308";
      case "high": return "#f97316";
      case "critical": return "#ef4444";
      default: return "#6b7280";
    }
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: "radial-gradient(circle at top, #1f2933 0, #020617 55%)",
      color: "#f1f5f9",
      padding: "2rem",
      display: "flex",
      justifyContent: "center"
    }}>
      <div style={{ width: "100%", maxWidth: "1100px" }}>

        <h1 style={{ fontSize: "2rem", fontWeight: "700", marginBottom: ".4rem" }}>
          SURGE-SENSE
        </h1>
        <p style={{ color: "#94a3b8", marginBottom: "2rem" }}>
          AI-Powered Surge Prediction for Hospitals.
        </p>

        <section style={{
          background: "rgba(15,23,42,.9)",
          padding: "1.5rem",
          borderRadius: "1rem",
          border: "1px solid rgba(255,255,255,0.1)",
        }}>
          <form 
            onSubmit={handleSubmit} 
            style={{ display: "flex", flexDirection: "column", gap: "1rem" }}
          >
            <div>
              <label>City</label>
              <input
                value={city}
                onChange={(e) => setCity(e.target.value)}
                style={{
                  width: "97%", padding: "1rem", marginTop: ".3rem",
                  background: "#020617", border: "1px solid #334155",
                  color: "white", borderRadius: ".6rem"
                }}
              />
            </div>

            <div>
              <label>Query Instruction</label>
              <textarea
                rows="3"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Example: Predict respiratory surge and staffing needs."
                style={{
                  width: "97%", padding: "1rem", resize: "none", marginTop: ".3rem",
                  background: "#020617", border: "1px solid #334155",
                  color: "white", borderRadius: ".6rem"
                }}
              />
            </div>

            <button
              disabled={loading}
              style={{
                padding: "1rem",
                background: "linear-gradient(135deg,#4f46e5,#7c3aed,#ec4899)",
                borderRadius: "999px",
                border: "none",
                color: "white",
                cursor: loading ? "wait" : "pointer",
                fontWeight: 600
              }}
            >
              {loading ? "Analyzing..." : "Run Surge Model"}
            </button>
          </form>

          {error && (
            <div style={{
              marginTop: "1rem",
              background: "#7f1d1d",
              padding: ".7rem",
              borderRadius: ".5rem",
              border: "1px solid #ef4444",
              color: "#fecaca"
            }}>
              {error}
            </div>
          )}
        </section>

        {result && <SurgeResultView result={result} getRiskColor={getRiskColor} />}
      </div>
    </div>
  );
}


/* -------- Parse structured intermediate steps -------- */

function parseIntermediateSteps(steps) {
  if (!steps) return [];

  return steps.map(([actionObj, result], index) => {
    const log = actionObj.log || "";

    // Extract thought text before "Action:"
    const thoughtMatch = log.match(/Thought:(.*?)(?=Action:)/s);
    const thought = thoughtMatch ? thoughtMatch[1].trim() : "No reasoning logged.";

    return {
      id: index + 1,
      action: actionObj.tool,
      input: actionObj.tool_input,
      result,
      thought,
    };
  });
}


/* -------- Result View -------- */

function SurgeResultView({ result, getRiskColor }) {
  const [showDebug, setShowDebug] = useState(false);

  const raw = result.agent_output;
  let parsed = {};

  try {
    const jsonIndex = raw.lastIndexOf("{");
    parsed = JSON.parse(raw.slice(jsonIndex));
  } catch {
    parsed = { error: "Unable to parse JSON." };
  }

  const steps = parseIntermediateSteps(result.intermediate_steps);

  return (
    <div style={{ marginTop: "2rem", display: "grid", gap: "1.5rem" }}>

      <button
        onClick={() => setShowDebug(!showDebug)}
        style={{
          padding: ".9rem",
          borderRadius: "10px",
          border: "none",
          marginTop: "1rem",
          background: "#1e293b",
          color: "#e2e8f0",
          cursor: "pointer",
          fontWeight: 600
        }}
      >
        {showDebug ? "Hide Tool Use Logs" : "Show Tool Use Logs"}
      </button>


{showDebug && (
  <div style={{
    marginTop: "1rem",
    background: "#0f172a",
    padding: "1.5rem",
    borderRadius: "12px",
    border: "1px solid rgba(255,255,255,0.08)",
    maxHeight: "400px",
    overflowY: "auto",
    scrollbarWidth: "none",    // Firefox
    msOverflowStyle: "none",   // Edge/IE
  }} 
  className="no-scrollbar"
  >

    <style>{`
      .no-scrollbar::-webkit-scrollbar { display: none; }
    `}</style>

    <h3 style={{ 
      color: "#93c5fd", 
      fontWeight: 600, 
      fontSize: "1.1rem",
      marginBottom: "1rem"
    }}>
      Tool Execution Trace
    </h3>
    
    {steps.length === 0 ? (
      <p style={{ marginTop: "1rem", color: "#64748b", fontStyle: "italic" }}>
        No tool calls used in this reasoning.
      </p>
    ) : (
      steps.map(step => (
        <div key={step.id} style={{
          background: "#1e293b",
          marginBottom: "1.2rem",
          padding: "1.2rem",
          borderRadius: "10px",
          border: "1px solid rgba(255,255,255,0.08)",
        }}>

          <h4 style={{ color: "#f8fafc", fontWeight: 600 }}>Thought</h4>
          <p style={{ color: "#cbd5e1", marginBottom: "1rem" }}>{step.thought}</p>

          <h4 style={{ color: "#f8fafc", fontWeight: 600 }}>Action</h4>
          <p style={{ color: "#60a5fa", marginBottom: "1rem" }}>{step.action}</p>

          <h4 style={{ color: "#f8fafc", fontWeight: 600 }}>Input</h4>
          <pre style={{
            background: "#0f172a",
            padding: ".8rem",
            borderRadius: "8px",
            whiteSpace: "pre-wrap",
            fontSize: ".85rem",
            color: "#38bdf8",
            border: "1px solid rgba(255,255,255,0.08)"
          }}>
{step.input}
          </pre>

          <h4 style={{ color: "#f8fafc", marginTop: "1rem", fontWeight: 600 }}>Result</h4>
          <pre style={{
            background: "#0f172a",
            padding: ".8rem",
            borderRadius: "8px",
            whiteSpace: "pre-wrap",
            fontSize: ".85rem",
            color: "#86efac",
            border: "1px solid rgba(255,255,255,0.08)"
          }}>
{step.result}
          </pre>

        </div>
      ))
    )}
  </div>
)}




      {/* Risk Overview */}
      <div style={{
        background: "rgba(15,23,42,.95)",
        padding: "1.5rem",
        borderRadius: "1rem",
        border: "1px solid rgba(255,255,255,0.15)"
      }}>
        <h3 style={{ fontSize: "1.2rem", marginBottom: ".6rem" }}>Risk Overview</h3>

        <div style={{ display: "flex", gap: ".8rem", alignItems: "center" }}>
          <span style={{ fontSize: "1.4rem", fontWeight: "700" }}>
            {parsed.risk_level}
          </span>
          <span style={{
            padding: ".3rem .7rem",
            borderRadius: "20px",
            border: `1px solid ${getRiskColor(parsed.risk_level)}`,
            color: getRiskColor(parsed.risk_level),
            fontSize: ".75rem",
            textTransform: "uppercase",
            fontWeight: 600
          }}>
            Surge Risk
          </span>
        </div>

        <p style={{ marginTop: ".4rem" }}>
          <strong>Confidence:</strong> {parsed.confidence_score}%
        </p>

        <p style={{ marginTop: ".8rem", color: "#cbd5e1" }}>
          {parsed.summary}
        </p>
      </div>

      <Card title="Patient Advisory" items={[parsed.patient_advisory]} />

      <div style={{
        display: "grid",
        gap: "1rem",
        gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))"
      }}>
        <Card title="Primary Drivers" items={parsed.drivers} />
        <Card title="Predicted Impacts" items={parsed.predicted_impacts} />
      </div>

      <div style={{
        display: "grid",
        gap: "1rem",
        gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))"
      }}>
        <Card title="Operational Actions" items={parsed.operational_actions} />
        <Card title="Supply Actions" items={parsed.supply_actions} />
      </div>
    </div>
  );
}


/* -------- Card Component -------- */

function Card({ title, items }) {
  if (!items || !items.length) return null;

  return (
    <div
      style={{
        backgroundColor: "rgba(15, 23, 42, 0.95)",
        borderRadius: "1rem",
        padding: "1rem",
        border: "1px solid rgba(255,255,255,0.1)",
      }}
    >
      <h3 style={{ fontSize: "1rem", marginBottom: ".6rem" }}>{title}</h3>
      <ul style={{ paddingLeft: "1rem", color: "#cbd5e1" }}>
        {items.map((i, idx) => (
          <li key={idx}>{i}</li>
        ))}
      </ul>
    </div>
  );
}
