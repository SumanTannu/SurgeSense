import json
import os
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

FILE_NAME = os.getenv("HOSPITAL_DATA_FILE", "hospital_synthetic_data.json")
GENERATOR_INTERVAL_SEC = int(os.getenv("HOSPITAL_GENERATOR_INTERVAL_SEC", "1"))

history_opd: List[int] = []


def load_file() -> List[Dict[str, Any]]:
    """Load existing hospital synthetic data from JSON file."""
    if os.path.exists(FILE_NAME):
        try:
            with open(FILE_NAME, "r", encoding="utf-8") as file:
                return json.load(file)
        except Exception:  # noqa: BLE001
            return []
    return []


def rebuild_history(data: List[Dict[str, Any]]) -> None:
    """Rebuild OPD history from the last 7 entries."""
    global history_opd
    history_opd = []
    for entry in data[-7:]:
        try:
            history_opd.append(entry["hospital_metrics"]["opd_visits_today"])
        except Exception:  # noqa: BLE001
            continue


def same_day(timestamp: Optional[str]) -> bool:
    """Check if the given timestamp string belongs to the current day."""
    if not timestamp:
        return False
    return timestamp.split(" ")[0] == datetime.now().strftime("%Y-%m-%d")


def adjust_stock(
    current: int,
    use_min: int,
    use_max: int,
    threshold: int,
    refill: int,
) -> int:
    """Randomly decrement stock and refill when below a threshold."""
    used = random.randint(use_min, use_max)
    current -= used
    if current < threshold:
        current += refill
    return max(0, current)


def compute_rolling(new: int) -> int:
    """Maintain and return a rolling 7-day total for OPD visits."""
    global history_opd
    history_opd.append(new)
    if len(history_opd) > 7:
        history_opd = history_opd[-7:]
    return sum(history_opd)


def generate_opd_categories(
    total: int,
    prev: Optional[Dict[str, int]] = None,
    continue_day: bool = False,
) -> Dict[str, int]:
    """Generate or update OPD category distribution."""
    if continue_day and prev:
        return {
            key: prev[key] + random.randint(0, max(1, int(total * 0.01)))
            for key in prev
        }

    ratios = {
        "emergency": 0.20,
        "general_medicine": 0.30,
        "pediatrics": 0.10,
        "orthopedics": 0.08,
        "respiratory": 0.12,
        "cardiology": 0.08,
        "dermatology": 0.05,
        "others": 0.07,
    }

    allocated = {key: int(total * value) for key, value in ratios.items()}
    diff = total - sum(allocated.values())
    if diff > 0:
        allocated[random.choice(list(allocated.keys()))] += diff

    return allocated


def generate_snapshot(last_entry: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate a new synthetic snapshot based on the last entry (if any)."""
    last_ts = last_entry.get("timestamp") if last_entry else None
    continue_today = same_day(last_ts)

    last_metrics = last_entry.get("hospital_metrics") if last_entry else None
    last_supplies = last_entry.get("resources_and_supplies") if last_entry else None

    now = datetime.now()

    # OPD calculation (time aware)
    if continue_today and last_metrics:
        last_time = datetime.strptime(last_entry["timestamp"], "%Y-%m-%d %H:%M:%S")
        minutes_passed = max(1, int((now - last_time).total_seconds() / 60))

        hour = now.hour
        if 8 <= hour <= 18:
            patients_per_min = random.randint(4, 12)
        elif 18 <= hour <= 22:
            patients_per_min = random.randint(2, 6)
        else:
            patients_per_min = random.randint(0, 2)

        opd_today = last_metrics["opd_visits_today"] + (patients_per_min * minutes_passed)
        opd_categories = generate_opd_categories(
            opd_today,
            last_metrics["opd_categories"],
            True,
        )
    else:
        opd_today = random.randint(5, 30)
        opd_categories = generate_opd_categories(opd_today)

    past_7_day = compute_rolling(opd_today)

    # Emergency and occupancy
    if continue_today and last_metrics:
        emergency_today = last_metrics["emergency_intake_today"] + random.randint(0, 4)
        bed_occ = max(
            50,
            min(100, last_metrics["current_bed_occupancy"] + random.randint(-2, 2)),
        )
        icu_occ = max(
            60,
            min(100, last_metrics["icu_occupancy"] + random.randint(-2, 2)),
        )
    else:
        emergency_today = opd_categories["emergency"]
        bed_occ = random.randint(60, 90)
        icu_occ = random.randint(70, 95)

    available_beds = 100 - bed_occ
    available_icu = max(0, 20 - int(icu_occ / 5))

    wait_triage = int(bed_occ / 100 * random.randint(10, 25))
    wait_er = wait_triage + random.randint(10, 20)
    wait_icu = int(icu_occ / 100 * random.randint(5, 15))

    # Staff
    hour = now.hour
    if 8 <= hour <= 20:
        doctors = random.randint(15, 22)
        nurses = random.randint(35, 48)
        support = random.randint(20, 30)
    else:
        doctors = random.randint(8, 14)
        nurses = random.randint(18, 30)
        support = random.randint(10, 20)

    hospital_metrics = {
        "past_7_day_opd_visits": past_7_day,
        "opd_visits_today": opd_today,
        "opd_categories": opd_categories,
        "current_bed_occupancy": bed_occ,
        "icu_occupancy": icu_occ,
        "emergency_intake_today": emergency_today,
        "available_beds": available_beds,
        "available_icu_beds": available_icu,
        "triage_wait_time_minutes": wait_triage,
        "avg_er_wait_time_minutes": wait_er,
        "avg_icu_wait_time_minutes": wait_icu,
        "doctor_count_on_shift": doctors,
        "nurse_count_on_shift": nurses,
        "support_staff_on_shift": support,
    }

    # Supplies
    if not last_supplies:
        last_supplies = {
            "test_kits": {
                "rt_pcr": 500,
                "flu": 800,
                "dengue": 200,
                "covid": 600,
                "typhoid": 300,
            },
            "ppe": {
                "n95": 1500,
                "gloves": 4000,
                "sanitizer_liters": 100,
            },
            "vaccine": {
                "flu": 400,
                "hepb": 200,
            },
            "blood_bank": {
                "A+": 25,
                "A-": 6,
                "B+": 20,
                "B-": 4,
                "O+": 30,
                "O-": 4,
                "AB+": 12,
                "AB-": 2,
            },
        }

    supplies = {
        "test_kits": {
            key: adjust_stock(value, 1, 5, 120, 300)
            for key, value in last_supplies["test_kits"].items()
        },
        "ppe": {
            "n95": adjust_stock(last_supplies["ppe"]["n95"], 5, 20, 300, 600),
            "gloves": adjust_stock(
                last_supplies["ppe"]["gloves"],
                30,
                100,
                700,
                2000,
            ),
            "sanitizer_liters": adjust_stock(
                last_supplies["ppe"]["sanitizer_liters"],
                1,
                5,
                20,
                50,
            ),
        },
        "vaccine": {
            "flu": adjust_stock(last_supplies["vaccine"]["flu"], 1, 6, 100, 200),
            "hepb": adjust_stock(last_supplies["vaccine"]["hepb"], 0, 5, 40, 120),
        },
        "blood_bank": {
            key: max(0, value - random.randint(0, 1))
            for key, value in last_supplies["blood_bank"].items()
        },
    }

    return {
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "hospital_metrics": hospital_metrics,
        "resources_and_supplies": supplies,
    }


def run() -> None:
    """Continuously generate and append synthetic hospital data snapshots."""
    print("🏥 Synthetic Realistic Hospital Data Generator Running...")

    while True:
        data = load_file()
        if data and not history_opd:
            rebuild_history(data)

        last_entry: Dict[str, Any] = data[-1] if data else {}
        new_snapshot = generate_snapshot(last_entry)

        data.append(new_snapshot)
        with open(FILE_NAME, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)

        print(
            f"[{new_snapshot['timestamp']}]  "
            f"OPD: {new_snapshot['hospital_metrics']['opd_visits_today']} | "
            f"ICU: {new_snapshot['hospital_metrics']['icu_occupancy']}%",
        )

        time.sleep(GENERATOR_INTERVAL_SEC)


if __name__ == "__main__":
    run()
