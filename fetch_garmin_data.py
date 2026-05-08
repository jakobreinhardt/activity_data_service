"""
Fetch Garmin Connect data via the garminconnect library.
Credentials are loaded from .env in the project root.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from garminconnect import Garmin

load_dotenv(Path(__file__).parent / ".env")

DATA_DIR = Path(__file__).parent / "garmin_data"
DATA_DIR.mkdir(exist_ok=True)


def login():
    email = os.environ.get("GARMIN_EMAIL")
    password = os.environ.get("GARMIN_PASSWORD")
    if not email or not password:
        print("ERROR: Set GARMIN_EMAIL and GARMIN_PASSWORD in .env file.")
        sys.exit(1)

    token_path = DATA_DIR / ".garmin_session"
    client = Garmin(email, password)

    if token_path.exists():
        try:
            client.login(token_path)
            print("Resumed saved session.")
            return client
        except Exception:
            print("Saved session expired, logging in fresh...")

    client.login()
    try:
        client.garth.dump(str(token_path))
    except AttributeError:
        pass
    print("Logged in successfully.")
    return client


def save_json(name, data):
    path = DATA_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  Saved {path.name} ({len(json.dumps(data, default=str)):,} chars)")


def fetch_all(client, date_str=None):
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    print(f"\nFetching data for {date_str}...")

    # --- User profile ---
    print("\n[1/10] User profile")
    try:
        save_json("user_profile", client.get_full_name())
    except Exception as e:
        print(f"  Skipped: {e}")

    # --- Daily summary ---
    print("[2/10] Daily summary")
    try:
        save_json(f"daily_summary_{date_str}", client.get_stats(date_str))
    except Exception as e:
        print(f"  Skipped: {e}")

    # --- Heart rate ---
    print("[3/10] Heart rate")
    try:
        save_json(f"heart_rate_{date_str}", client.get_heart_rates(date_str))
    except Exception as e:
        print(f"  Skipped: {e}")

    # --- Steps ---
    print("[4/10] Steps")
    try:
        save_json(f"steps_{date_str}", client.get_steps_data(date_str))
    except Exception as e:
        print(f"  Skipped: {e}")

    # --- Stress ---
    print("[5/10] Stress")
    try:
        save_json(f"stress_{date_str}", client.get_stress_data(date_str))
    except Exception as e:
        print(f"  Skipped: {e}")

    # --- Sleep ---
    print("[6/10] Sleep")
    try:
        save_json(f"sleep_{date_str}", client.get_sleep_data(date_str))
    except Exception as e:
        print(f"  Skipped: {e}")

    # --- Body battery ---
    print("[7/10] Body battery")
    try:
        save_json(f"body_battery_{date_str}", client.get_body_battery(date_str))
    except Exception as e:
        print(f"  Skipped: {e}")

    # --- Respiration ---
    print("[8/10] Respiration")
    try:
        save_json(f"respiration_{date_str}", client.get_respiration_data(date_str))
    except Exception as e:
        print(f"  Skipped: {e}")

    # --- SpO2 ---
    print("[9/10] SpO2")
    try:
        save_json(f"spo2_{date_str}", client.get_spo2_data(date_str))
    except Exception as e:
        print(f"  Skipped: {e}")

    # --- Activities (with GPS) ---
    print("[10/10] Activities")
    try:
        activities = client.get_activities_by_date(date_str, date_str)
        save_json(f"activities_{date_str}", activities)

        for act in activities:
            act_id = act["activityId"]
            act_name = act.get("activityName", "unnamed")
            print(f"\n  Activity: {act_name} (ID: {act_id})")

            # GPS track
            try:
                gpx = client.download_activity(act_id, dl_fmt=client.ActivityDownloadFormat.GPX)
                gpx_path = DATA_DIR / f"activity_{act_id}.gpx"
                with open(gpx_path, "wb") as f:
                    f.write(gpx)
                print(f"    Saved GPX track: {gpx_path.name}")
            except Exception as e:
                print(f"    GPX download failed: {e}")

            # Activity details (splits, HR zones, etc.)
            try:
                details = client.get_activity(act_id)
                save_json(f"activity_details_{act_id}", details)
            except Exception as e:
                print(f"    Details failed: {e}")

    except Exception as e:
        print(f"  Skipped: {e}")

    print(f"\nDone! All data saved to {DATA_DIR}")


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else "2026-05-04"
    client = login()
    fetch_all(client, date)
