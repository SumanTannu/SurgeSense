import axios from "axios";

const API_BASE = "http://localhost:8000";

// The only relevant endpoint in api.py is /surge (POST), which expects { query, city }
export const fetchSurgeAdvisor = (query, city) =>
  axios.post(`${API_BASE}/surge`, { query, city });
