import os
import json
import requests


def run_surge_request() -> None:
    """Send a POST request to the Surge-Sense API and print the response."""
    url = os.getenv("SURGE_API_URL", "http://localhost:8000/surge")

    payload = {
        "query": os.getenv(
            "SURGE_QUERY",
            "Assess surge risk for the next 5 days and suggest actions.",
        ),
        "city": os.getenv("SURGE_CITY", "Mumbai"),
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()
        print(json.dumps(data, indent=2))

    except requests.exceptions.RequestException as exc:
        print(f"[Error] Failed to reach Surge API: {exc}")
    except ValueError:
        print("[Error] Invalid JSON response from server.")
    except Exception as exc:  # noqa: BLE001
        print(f"[Error] Unexpected issue: {exc}")


if __name__ == "__main__":
    run_surge_request()
