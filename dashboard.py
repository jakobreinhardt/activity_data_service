import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import Dash, html, dcc, Input, Output, callback

DATA_DIR = Path(__file__).parent / "garmin_data"
DATE = "2026-05-04"
TZ = timezone(timedelta(hours=2))

GPX_NS = {
    "gpx": "http://www.topografix.com/GPX/1/1",
    "ns3": "http://www.garmin.com/xmlschemas/TrackPointExtension/v1",
}


def ms_to_local(epoch_ms):
    return datetime.fromtimestamp(epoch_ms / 1000, tz=TZ)


def load_json(name):
    path = DATA_DIR / f"{name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_heart_rate():
    data = load_json(f"heart_rate_{DATE}")
    if not data:
        return pd.DataFrame()
    rows = [
        {"time": ms_to_local(ts), "hr": val}
        for ts, val in data["heartRateValues"]
        if val is not None
    ]
    return pd.DataFrame(rows)


def load_stress():
    data = load_json(f"stress_{DATE}")
    if not data:
        return pd.DataFrame(), pd.DataFrame()

    stress_rows = [
        {"time": ms_to_local(ts), "stress": val}
        for ts, val in data.get("stressValuesArray", [])
        if val is not None and val >= 0
    ]

    bb_rows = [
        {"time": ms_to_local(row[0]), "body_battery": row[2]}
        for row in data.get("bodyBatteryValuesArray", [])
        if row[2] is not None
    ]

    return pd.DataFrame(stress_rows), pd.DataFrame(bb_rows)


def load_respiration():
    data = load_json(f"respiration_{DATE}")
    if not data:
        return pd.DataFrame()
    rows = [
        {"time": ms_to_local(ts), "respiration": val}
        for ts, val in data.get("respirationValuesArray", [])
        if val is not None and val > 0
    ]
    return pd.DataFrame(rows)


def load_steps():
    data = load_json(f"steps_{DATE}")
    if not data:
        return pd.DataFrame()
    rows = []
    for entry in data:
        start = datetime.fromisoformat(entry["startGMT"]).replace(tzinfo=timezone.utc).astimezone(TZ)
        rows.append({
            "time": start,
            "steps": entry["steps"],
            "activity_level": entry["primaryActivityLevel"],
        })
    return pd.DataFrame(rows)


def load_activity_summary():
    data = load_json(f"activities_{DATE}")
    if not data:
        return None
    return data[0]


def load_gpx():
    gpx_files = list(DATA_DIR.glob("activity_*.gpx"))
    if not gpx_files:
        return pd.DataFrame()

    tree = ET.parse(str(gpx_files[0]))
    root = tree.getroot()
    rows = []
    for pt in root.findall(".//gpx:trkpt", GPX_NS):
        lat = float(pt.get("lat"))
        lon = float(pt.get("lon"))
        ele_el = pt.find("gpx:ele", GPX_NS)
        time_el = pt.find("gpx:time", GPX_NS)
        ele = float(ele_el.text) if ele_el is not None else None
        time = datetime.fromisoformat(time_el.text.replace("Z", "+00:00")).astimezone(TZ) if time_el is not None else None

        hr, cad, temp = None, None, None
        ext = pt.find(".//ns3:TrackPointExtension", GPX_NS)
        if ext is not None:
            hr_el = ext.find("ns3:hr", GPX_NS)
            cad_el = ext.find("ns3:cad", GPX_NS)
            temp_el = ext.find("ns3:atemp", GPX_NS)
            hr = int(hr_el.text) if hr_el is not None else None
            cad = int(cad_el.text) if cad_el is not None else None
            temp = float(temp_el.text) if temp_el is not None else None

        rows.append({"lat": lat, "lon": lon, "ele": ele, "time": time, "hr": hr, "cad": cad, "temp": temp})

    df = pd.DataFrame(rows)
    if not df.empty and "time" in df.columns:
        df["elapsed_km"] = 0.0
        # Approximate cumulative distance using haversine
        import math
        total = 0.0
        dists = [0.0]
        for i in range(1, len(df)):
            lat1, lon1 = math.radians(df.iloc[i - 1]["lat"]), math.radians(df.iloc[i - 1]["lon"])
            lat2, lon2 = math.radians(df.iloc[i]["lat"]), math.radians(df.iloc[i]["lon"])
            dlat, dlon = lat2 - lat1, lon2 - lon1
            a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
            total += 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            dists.append(total)
        df["elapsed_km"] = dists
    return df


def build_map(gpx_df):
    fig = go.Figure()
    fig.add_trace(go.Scattermap(
        lat=gpx_df["lat"],
        lon=gpx_df["lon"],
        mode="lines",
        line=dict(width=3, color="#e74c3c"),
        name="Route",
        hoverinfo="skip",
    ))

    fig.add_trace(go.Scattermap(
        lat=[gpx_df.iloc[0]["lat"]],
        lon=[gpx_df.iloc[0]["lon"]],
        mode="markers",
        marker=dict(size=12, color="#2ecc71", symbol="circle"),
        name="Start",
    ))
    fig.add_trace(go.Scattermap(
        lat=[gpx_df.iloc[-1]["lat"]],
        lon=[gpx_df.iloc[-1]["lon"]],
        mode="markers",
        marker=dict(size=12, color="#e74c3c", symbol="circle"),
        name="Finish",
    ))

    # Trace index 3: hover highlight marker (initially hidden)
    fig.add_trace(go.Scattermap(
        lat=[None],
        lon=[None],
        mode="markers",
        marker=dict(size=16, color="#ffff00", symbol="circle"),
        name="Position",
        showlegend=False,
    ))

    center_lat = gpx_df["lat"].mean()
    center_lon = gpx_df["lon"].mean()
    fig.update_layout(
        map=dict(
            style="open-street-map",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=11,
        ),
        height=500,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=True,
        legend=dict(
            bgcolor="rgba(17,17,34,0.8)",
            font=dict(color="white"),
            x=0.01, y=0.99,
        ),
        uirevision="constant",
    )
    return fig


def build_elevation_profile(gpx_df):
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=("Elevation", "Heart Rate", "Cadence"),
        row_heights=[0.4, 0.35, 0.25],
    )

    fig.add_trace(go.Scatter(
        x=gpx_df["elapsed_km"], y=gpx_df["ele"],
        mode="lines", name="Elevation",
        line=dict(color="#2ecc71", width=1.2),
        fill="tozeroy", fillcolor="rgba(46,204,113,0.15)",
    ), row=1, col=1)
    fig.update_yaxes(title_text="m", row=1, col=1)

    if gpx_df["hr"].notna().any():
        fig.add_trace(go.Scatter(
            x=gpx_df["elapsed_km"], y=gpx_df["hr"],
            mode="lines", name="HR",
            line=dict(color="#e74c3c", width=1),
        ), row=2, col=1)
        fig.update_yaxes(title_text="bpm", row=2, col=1)

    if gpx_df["cad"].notna().any():
        fig.add_trace(go.Scatter(
            x=gpx_df["elapsed_km"], y=gpx_df["cad"],
            mode="lines", name="Cadence",
            line=dict(color="#f39c12", width=1),
        ), row=3, col=1)
        fig.update_yaxes(title_text="spm", row=3, col=1)

    fig.update_xaxes(title_text="Distance (km)", row=3, col=1)
    fig.update_layout(
        height=500,
        template="plotly_dark",
        showlegend=False,
        margin=dict(l=60, r=30, t=30, b=40),
        hovermode="x unified",
    )
    return fig


def build_wellness_figure(hr_df, stress_df, bb_df, resp_df, steps_df):
    fig = make_subplots(
        rows=5, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=("Heart Rate (Full Day)", "Stress Level", "Body Battery", "Respiration Rate", "Steps (15-min intervals)"),
        row_heights=[0.25, 0.18, 0.18, 0.18, 0.21],
    )

    if not hr_df.empty:
        fig.add_trace(go.Scatter(
            x=hr_df["time"], y=hr_df["hr"],
            mode="lines", name="Heart Rate",
            line=dict(color="#e74c3c", width=1.2),
            fill="tozeroy", fillcolor="rgba(231,76,60,0.15)",
        ), row=1, col=1)
        fig.update_yaxes(title_text="bpm", row=1, col=1)

    if not stress_df.empty:
        colors = [
            "#2ecc71" if v <= 25 else "#f39c12" if v <= 50 else "#e67e22" if v <= 75 else "#e74c3c"
            for v in stress_df["stress"]
        ]
        fig.add_trace(go.Bar(
            x=stress_df["time"], y=stress_df["stress"],
            name="Stress", marker_color=colors,
        ), row=2, col=1)
        fig.update_yaxes(title_text="0–100", range=[0, 100], row=2, col=1)

    if not bb_df.empty:
        fig.add_trace(go.Scatter(
            x=bb_df["time"], y=bb_df["body_battery"],
            mode="lines+markers", name="Body Battery",
            line=dict(color="#3498db", width=1.5),
            marker=dict(size=3),
            fill="tozeroy", fillcolor="rgba(52,152,219,0.12)",
        ), row=3, col=1)
        fig.update_yaxes(title_text="Level", range=[0, 100], row=3, col=1)

    if not resp_df.empty:
        fig.add_trace(go.Scatter(
            x=resp_df["time"], y=resp_df["respiration"],
            mode="lines", name="Respiration",
            line=dict(color="#9b59b6", width=1.2),
            fill="tozeroy", fillcolor="rgba(155,89,182,0.12)",
        ), row=4, col=1)
        fig.update_yaxes(title_text="br/min", row=4, col=1)

    if not steps_df.empty:
        level_colors = {
            "sedentary": "#555",
            "active": "#2ecc71",
            "highlyActive": "#e67e22",
            "generic": "#3498db",
        }
        colors = [level_colors.get(lv, "#888") for lv in steps_df["activity_level"]]
        fig.add_trace(go.Bar(
            x=steps_df["time"], y=steps_df["steps"],
            name="Steps", marker_color=colors,
        ), row=5, col=1)
        fig.update_yaxes(title_text="Steps", row=5, col=1)

    fig.update_xaxes(title_text="Time (local)", row=5, col=1)
    fig.update_layout(
        height=1000,
        template="plotly_dark",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        margin=dict(l=60, r=30, t=40, b=40),
        hovermode="x unified",
    )
    return fig


def card(title, value, color):
    return html.Div([
        html.Div(title, style={"color": "#aaa", "fontSize": "12px", "marginBottom": "2px"}),
        html.Div(value, style={"color": color, "fontSize": "24px", "fontWeight": "bold"}),
    ], style={
        "backgroundColor": "#1e1e2f",
        "borderRadius": "10px",
        "padding": "14px 20px",
        "flex": "1",
        "textAlign": "center",
        "minWidth": "130px",
    })


def section_header(text):
    return html.H2(text, style={
        "color": "#ddd", "fontSize": "18px", "margin": "24px 30px 8px 30px",
        "borderBottom": "1px solid #333", "paddingBottom": "6px",
    })


def create_app():
    activity = load_activity_summary()
    gpx_df = load_gpx()
    hr_df = load_heart_rate()
    stress_df, bb_df = load_stress()
    resp_df = load_respiration()
    steps_df = load_steps()

    children = []

    # --- Title ---
    title = "Garmin Dashboard"
    if activity:
        title = activity.get("activityName", title)
    children.append(html.H1(title, style={
        "color": "#fff", "textAlign": "center", "margin": "0",
        "padding": "20px 0 6px 0", "fontSize": "26px",
    }))
    children.append(html.Div(DATE, style={
        "color": "#888", "textAlign": "center", "fontSize": "14px", "marginBottom": "12px",
    }))

    # --- Activity summary cards ---
    if activity:
        dist_km = (activity.get("distance") or 0) / 1000
        duration_s = activity.get("duration") or 0
        hours, rem = divmod(int(duration_s), 3600)
        mins, secs = divmod(rem, 60)
        dur_str = f"{hours}h {mins:02d}m"
        elev = activity.get("elevationGain") or 0
        avg_hr = activity.get("averageHR") or 0
        max_hr = activity.get("maxHR") or 0
        cals = activity.get("calories") or 0
        avg_pace_s = duration_s / dist_km if dist_km > 0 else 0
        pace_min, pace_sec = divmod(int(avg_pace_s), 60)

        cards = [
            card("Distance", f"{dist_km:.1f} km", "#3498db"),
            card("Duration", dur_str, "#2ecc71"),
            card("Elevation", f"{elev:.0f} m", "#2ecc71"),
            card("Avg Pace", f"{pace_min}:{pace_sec:02d} /km", "#f39c12"),
            card("Avg HR", f"{avg_hr:.0f} bpm", "#e74c3c"),
            card("Max HR", f"{max_hr:.0f} bpm", "#e74c3c"),
            card("Calories", f"{cals:.0f}", "#e67e22"),
        ]
        children.append(html.Div(cards, style={
            "display": "flex", "gap": "10px", "padding": "0 30px",
            "flexWrap": "wrap", "justifyContent": "center",
        }))

    # --- GPS Map + Elevation ---
    if not gpx_df.empty:
        children.append(section_header("GPS Track"))
        children.append(html.Div([
            dcc.Graph(
                id="gps-map",
                figure=build_map(gpx_df),
                config={"scrollZoom": True},
                style={"flex": "1", "minWidth": "400px"},
            ),
        ], style={"padding": "0 30px"}))

        children.append(section_header("Activity Profile"))
        children.append(html.Div([
            dcc.Graph(
                id="elevation-profile",
                figure=build_elevation_profile(gpx_df),
                config={"displayModeBar": True, "scrollZoom": True},
            ),
        ], style={"padding": "0 20px"}))

    # --- Wellness time series ---
    children.append(section_header("Daily Wellness"))
    wellness_fig = build_wellness_figure(hr_df, stress_df, bb_df, resp_df, steps_df)
    children.append(html.Div([
        dcc.Graph(
            figure=wellness_fig,
            config={"displayModeBar": True, "scrollZoom": True},
        ),
    ], style={"padding": "0 20px"}))

    app = Dash(__name__)
    app.layout = html.Div(children, style={
        "backgroundColor": "#111122",
        "minHeight": "100vh",
        "fontFamily": "system-ui",
        "paddingBottom": "40px",
    })

    if not gpx_df.empty:
        km_arr = gpx_df["elapsed_km"].values
        lat_arr = gpx_df["lat"].values
        lon_arr = gpx_df["lon"].values
        ele_arr = gpx_df["ele"].values
        hr_arr = gpx_df["hr"].values

        @app.callback(
            Output("gps-map", "figure"),
            Input("elevation-profile", "hoverData"),
            prevent_initial_call=True,
        )
        def update_map_marker(hover_data):
            fig = build_map(gpx_df)
            if not hover_data or "points" not in hover_data:
                return fig

            x_val = hover_data["points"][0].get("x")
            if x_val is None:
                return fig

            idx = int(np.clip(np.searchsorted(km_arr, x_val), 0, len(km_arr) - 1))
            lat, lon = float(lat_arr[idx]), float(lon_arr[idx])
            ele = float(ele_arr[idx]) if ele_arr[idx] is not None else 0
            hr = int(hr_arr[idx]) if hr_arr[idx] is not None and not np.isnan(hr_arr[idx]) else None

            label = f"{x_val:.1f} km | {ele:.0f} m"
            if hr is not None:
                label += f" | {hr} bpm"

            fig.data[3].lat = [lat]
            fig.data[3].lon = [lon]
            fig.data[3].text = [label]
            fig.data[3].hoverinfo = "text"
            return fig

    return app


if __name__ == "__main__":
    app = create_app()
    print("Starting dashboard at http://127.0.0.1:8050")
    app.run(debug=False, port=8050)
