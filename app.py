import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="FortyGuard Environmental Intelligence",
    page_icon="🌍",
    layout="wide"
)

st.title("🌍 FortyGuard Environmental Intelligence")
st.caption("Interactive environmental analysis powered by saved FortyGuard API results")

HISTORY_FILE = Path("fortyguard_history.json")

if not HISTORY_FILE.exists():
    st.error("History file not found. Place fortyguard_history.json beside app.py.")
    st.stop()

history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))

if not history:
    st.warning("No saved analyses available.")
    st.stop()


# ===== LIVE FORTYGUARD API ANALYSIS =====

import requests
import time
from datetime import date, datetime

API_URL = "https://api.fortyguard.com/v1/env_params"
STATUS_URL = "https://api.fortyguard.com/v1/status/"

CITIES = {
    "New York": (40.7128, -74.0060),
    "Los Angeles": (34.0522, -118.2437),
    "Chicago": (41.8781, -87.6298),
    "Phoenix": (33.4484, -112.0740)
}

st.sidebar.divider()
st.sidebar.header("Live Environmental Analysis")

with st.sidebar.form("live_analysis_form"):

    selected_city = st.selectbox(
        "City",
        list(CITIES.keys())
    )

    selected_date = st.date_input(
        "Analysis date",
        value=date.today()
    )

    selected_time = st.time_input(
        "Local time",
        value=datetime.strptime("13:00", "%H:%M").time()
    )

    reference_temperature = st.number_input(
        "Reference temperature (°C)",
        value=20.0,
        step=0.5
    )

    confirm_credits = st.checkbox(
        "I understand this may consume FortyGuard API credits."
    )

    submit_analysis = st.form_submit_button(
        "Analyze Environment",
        type="primary"
    )

if submit_analysis:

    if not confirm_credits:
        st.sidebar.warning(
            "Please confirm the API credit usage."
        )

    else:
        lat, lon = CITIES[selected_city]

        # Check for an existing analysis with identical inputs
        requested_timestamp = (
            selected_date.isoformat()
            + "T"
            + selected_time.strftime("%H:%M")
        )

        matching = [
            item for item in history
            if item["city"] == selected_city
            and item["result"]["metadata"]["timestamps"][0][:16]
                == requested_timestamp
            and item["result"]["locations"][0].get("temperature")
                == reference_temperature
        ]

        if matching:
            st.sidebar.info(
                "An analysis with these inputs is already saved. "
                "Select it under Dashboard Controls."
            )
            st.stop()

        payload = {
            "latitude": lat,
            "longitude": lon,
            "temperature": reference_temperature,
            "date_time": {
                "start_date": selected_date.isoformat(),
                "start_time": selected_time.strftime("%H:%M"),
                "filter_type": 1
            },
            "analysis": [
                "heat_index_celsius",
                "relative_humidity_percent",
                "apparent_temperature_celsius"
            ]
        }

        headers = {
            "api-key": st.secrets["FORTYGUARD_API_KEY"],
            "Content-Type": "application/json"
        }

        with st.spinner("Submitting FortyGuard analysis..."):

            try:
                response = requests.post(
                    API_URL,
                    headers=headers,
                    json=payload,
                    timeout=60
                )

                response.raise_for_status()

                activity_id = response.json()["data"]["activity_id"]

                completed = False

                for attempt in range(60):

                    status_response = requests.get(
                        STATUS_URL + activity_id,
                        headers=headers,
                        timeout=30
                    )

                    status_response.raise_for_status()

                    status_data = status_response.json()["data"]
                    status = status_data["status"].lower()

                    if status == "completed":

                        new_entry = {
                            "city": selected_city,
                            "activity_id": activity_id,
                            "result": status_data["result"]
                        }

                        history = [
                            entry for entry in history
                            if entry["activity_id"] != activity_id
                        ]

                        history.append(new_entry)

                        HISTORY_FILE.write_text(
                            json.dumps(history, indent=2),
                            encoding="utf-8"
                        )

                        completed = True
                        st.sidebar.success(
                            "Analysis completed and saved!"
                        )
                        st.rerun()

                    elif status in ("failed", "error"):
                        st.sidebar.error(
                            "FortyGuard analysis failed."
                        )
                        break

                    time.sleep(5)

                if not completed:
                    st.sidebar.info(
                        "Check the activity status if still processing."
                    )

            except requests.RequestException as exc:
                st.sidebar.error(
                    f"API request failed: {exc}"
                )

# ===== END LIVE ANALYSIS =====

# Sidebar controls
st.sidebar.header("Dashboard Controls")

labels = [
    f"{entry['city']} | {entry['result']['metadata']['timestamps'][0]}"
    for entry in history
]

selected_index = st.sidebar.selectbox(
    "Choose an analysis",
    range(len(history)),
    format_func=lambda i: labels[i]
)

entry = history[selected_index]
result = entry["result"]
location = result["locations"][0]
params = location["parameters"]
timestamp = result["metadata"]["timestamps"][0]

def get_metric(key):
    values = params.get(key, [])
    if not values:
        return None
    value = values[0]
    if value is None or value == -999:
        return None
    return value

def display_metric(value, unit=""):
    return "N/A" if value is None else f"{value:.1f}{unit}"

st.subheader(f"{entry['city']} — Environmental Overview")
st.caption(f"Analysis timestamp: {timestamp}")

# Main indicators
c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Heat Index",
    display_metric(get_metric("heat_index_celsius"), "°C")
)

c2.metric(
    "Apparent Temperature",
    display_metric(get_metric("apparent_temperature_celsius"), "°C")
)

c3.metric(
    "Relative Humidity",
    display_metric(get_metric("relative_humidity_percent"), "%")
)

c4.metric(
    "Overall AQI",
    display_metric(get_metric("air_quality:idx"))
)

tab1, tab2, tab3, tab4 = st.tabs([
    "Air Quality",
    "Thermal Comfort",
    "Solar Irradiance",
    "Location"
])

with tab1:
    fields = {
        "Overall AQI": "air_quality:idx",
        "PM2.5": "air_quality_pm2p5:idx",
        "PM10": "air_quality_pm10:idx",
        "NO2": "air_quality_no2:idx",
        "CO": "aqi_us_co",
        "O3": "air_quality_o3:idx",
        "SO2": "air_quality_so2:idx"
    }

    rows = [
        {"Pollutant": name, "AQI": get_metric(key)}
        for name, key in fields.items()
        if get_metric(key) is not None
    ]

    if rows:
        fig = px.bar(
            pd.DataFrame(rows),
            x="Pollutant",
            y="AQI",
            color="AQI",
            title="Air Quality Analysis"
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No air-quality data available.")

with tab2:
    thermal_fields = {
        "Heat Index": "heat_index_celsius",
        "Apparent Temperature": "apparent_temperature_celsius",
        "Wet-Bulb Temperature": "wet_bulb_temperature_celsius"
    }

    rows = [
        {"Metric": name, "Temperature (°C)": get_metric(key)}
        for name, key in thermal_fields.items()
        if get_metric(key) is not None
    ]

    if rows:
        fig = px.bar(
            pd.DataFrame(rows),
            x="Metric",
            y="Temperature (°C)",
            color="Metric",
            title="Thermal Comfort Analysis"
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No thermal data available.")

with tab3:
    solar = location.get(
        "solar_irradiance", {}
    ).get("clear_sky", {})

    rows = [
        {"Component": key.upper(), "Irradiance (W/m²)": value}
        for key, value in solar.items()
        if isinstance(value, (int, float))
        and value != -999
    ]

    if rows:
        fig = px.bar(
            pd.DataFrame(rows),
            x="Component",
            y="Irradiance (W/m²)",
            color="Component",
            title="Modeled Clear-Sky Solar Irradiance"
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No solar data available.")

with tab4:
    map_df = pd.DataFrame([{
        "lat": location["lat"],
        "lon": location["lon"]
    }])
    st.map(map_df, zoom=10)
    st.caption("Map shows the analyzed coordinate, not a spatial heatmap.")

st.divider()

# Download selected analysis
st.download_button(
    "Download Selected Analysis (JSON)",
    data=json.dumps(entry, indent=2),
    file_name=f"fortyguard_analysis_{selected_index + 1}.json",
    mime="application/json"
)

# Export comparison data
comparison = []

for item in history:
    loc = item["result"]["locations"][0]
    p = loc["parameters"]

    def first(key):
        values = p.get(key, [])
        if not values or values[0] in (None, -999):
            return None
        return values[0]

    comparison.append({
        "City": item["city"],
        "Timestamp": item["result"]["metadata"]["timestamps"][0],
        "Heat Index": first("heat_index_celsius"),
        "Humidity": first("relative_humidity_percent"),
        "AQI": first("air_quality:idx")
    })

comparison_df = pd.DataFrame(comparison)

st.download_button(
    "Download Comparison CSV",
    data=comparison_df.to_csv(index=False),
    file_name="FortyGuard_Comparison.csv",
    mime="text/csv"
)


# ===== ENVIRONMENTAL RISK ASSESSMENT =====

st.divider()
st.header("Environmental Risk Assessment")

aqi = get_metric("air_quality:idx")
wet_bulb = get_metric("wet_bulb_temperature_celsius")
apparent = get_metric("apparent_temperature_celsius")
humidity = get_metric("relative_humidity_percent")

def classify_aqi(value):
    if value is None:
        return "Unavailable", "No AQI data available."
    if value <= 50:
        return "Good", "Air quality is generally satisfactory."
    if value <= 100:
        return "Moderate", (
            "Air quality is acceptable for most people. "
            "Unusually sensitive individuals may experience effects."
        )
    if value <= 150:
        return "Unhealthy for Sensitive Groups", (
            "Sensitive groups may experience health effects."
        )
    if value <= 200:
        return "Unhealthy", (
            "Health effects may occur across the general population."
        )
    if value <= 300:
        return "Very Unhealthy", (
            "Health alert: increased risk of health effects."
        )
    return "Hazardous", (
        "Health warning of emergency conditions."
    )

aqi_label, aqi_description = classify_aqi(aqi)

st.subheader("Air Quality Assessment")
st.metric("Air Quality Category", aqi_label)
st.write(aqi_description)

# Display thermal indicators without assigning
# an unsupported occupational heat-risk category
st.subheader("Thermal Conditions")

c1, c2, c3 = st.columns(3)

c1.metric(
    "Wet-Bulb Temperature",
    "N/A" if wet_bulb is None else f"{wet_bulb:.1f}°C"
)
c2.metric(
    "Apparent Temperature",
    "N/A" if apparent is None else f"{apparent:.1f}°C"
)
c3.metric(
    "Relative Humidity",
    "N/A" if humidity is None else f"{humidity:.1f}%"
)

st.info(
    "Wet-bulb temperature is a useful thermal indicator, "
    "but it is not the same as Wet Bulb Globe Temperature "
    "(WBGT). Occupational heat risk also depends on "
    "radiant heat, air movement, workload, clothing, "
    "and exposure duration."
)

st.subheader("Environmental Summary")

if aqi is not None:
    st.write(
        f"**Air quality:** {aqi_label} "
        f"(reported index: {aqi:.1f})."
    )

if apparent is not None:
    st.write(
        f"**Apparent temperature:** {apparent:.1f}°C."
    )

if wet_bulb is not None:
    st.write(
        f"**Wet-bulb temperature:** {wet_bulb:.1f}°C."
    )

st.caption(
    "This assessment summarizes FortyGuard outputs. "
    "It does not replace official air-quality alerts "
    "or a site-specific heat-safety assessment."
)

# ===== END ENVIRONMENTAL RISK ASSESSMENT =====


# ===== HISTORICAL ENVIRONMENTAL COMPARISON =====

st.divider()
st.header("Historical Environmental Comparison")

historical_rows = []

for item in history:
    result_item = item.get("result", {})
    locations = result_item.get("locations", [])
    timestamps = result_item.get("metadata", {}).get(
        "timestamps", []
    )

    if not locations or not timestamps:
        continue

    loc = locations[0]
    p = loc.get("parameters", {})

    def historical_value(key):
        values = p.get(key, [])
        if not values:
            return None
        value = values[0]
        return None if value in (None, -999) else value

    historical_rows.append({
        "City": item["city"],
        "Timestamp": timestamps[0],
        "Heat Index (°C)": historical_value(
            "heat_index_celsius"
        ),
        "Apparent Temperature (°C)": historical_value(
            "apparent_temperature_celsius"
        ),
        "Wet-Bulb (°C)": historical_value(
            "wet_bulb_temperature_celsius"
        ),
        "Humidity (%)": historical_value(
            "relative_humidity_percent"
        ),
        "AQI": historical_value("air_quality:idx")
    })

if historical_rows:
    historical_df = pd.DataFrame(historical_rows)

    city_options = sorted(historical_df["City"].unique())

    selected_cities = st.multiselect(
        "Select cities",
        options=city_options,
        default=city_options
    )

    metric_options = [
        "Heat Index (°C)",
        "Apparent Temperature (°C)",
        "Wet-Bulb (°C)",
        "Humidity (%)",
        "AQI"
    ]

    selected_metric = st.selectbox(
        "Select environmental metric",
        metric_options
    )

    filtered_df = historical_df[
        historical_df["City"].isin(selected_cities)
    ].copy()

    filtered_df = filtered_df.dropna(
        subset=[selected_metric]
    )

    if not filtered_df.empty:
        filtered_df["Date"] = pd.to_datetime(
            filtered_df["Timestamp"],
            utc=True
        )

        filtered_df = filtered_df.sort_values("Date")

        fig_history = px.line(
            filtered_df,
            x="Date",
            y=selected_metric,
            color="City",
            markers=True,
            hover_data=["Timestamp"],
            title=f"Historical {selected_metric}"
        )

        fig_history.update_layout(
            template="plotly_white",
            height=450
        )

        st.plotly_chart(
            fig_history,
            width="stretch"
        )

        if len(filtered_df) == 1:
            st.info(
                "Only one saved observation is available. "
                "More completed analyses are needed "
                "to display a meaningful trend."
            )

    else:
        st.info("No observations match your selection.")

    st.subheader("Historical Data Table")

    st.dataframe(
        historical_df,
        width="stretch",
        hide_index=True
    )

    st.download_button(
        "Download Historical Data (CSV)",
        data=historical_df.to_csv(index=False),
        file_name="FortyGuard_Historical_Data.csv",
        mime="text/csv"
    )

else:
    st.info("No saved historical analyses available.")

# ===== END HISTORICAL ENVIRONMENTAL COMPARISON =====


# ===== PDF ENVIRONMENTAL REPORT =====

from io import BytesIO
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

def create_environmental_pdf():
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=(595, 842)
    )

    styles = getSampleStyleSheet()
    elements = []

    elements.append(
        Paragraph(
            "FortyGuard Environmental Analysis Report",
            styles["Title"]
        )
    )

    elements.append(Spacer(1, 20))

    elements.append(
        Paragraph(
            f"Location: {entry['city']}",
            styles["Normal"]
        )
    )

    elements.append(
        Paragraph(
            f"Timestamp: {timestamp}",
            styles["Normal"]
        )
    )

    elements.append(Spacer(1, 20))

    metrics_table = [
        ["Environmental Parameter", "Value"],
        ["Heat Index",
         display_metric(get_metric("heat_index_celsius"), " C")],
        ["Apparent Temperature",
         display_metric(get_metric("apparent_temperature_celsius"), " C")],
        ["Wet-Bulb Temperature",
         display_metric(get_metric("wet_bulb_temperature_celsius"), " C")],
        ["Relative Humidity",
         display_metric(get_metric("relative_humidity_percent"), "%")],
        ["Air Quality Index",
         display_metric(get_metric("air_quality:idx"))]
    ]

    table = Table(metrics_table, colWidths=[280, 180])

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#122844")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10)
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))

    elements.append(
        Paragraph(
            "Note: Reference temperature is an analysis input. "
            "Solar irradiance values, when provided, are modeled "
            "clear-sky estimates.",
            styles["Normal"]
        )
    )

    document.build(elements)
    buffer.seek(0)

    return buffer.getvalue()

st.divider()
st.header("Download Environmental Report")

st.download_button(
    "Download PDF Report",
    data=create_environmental_pdf(),
    file_name="FortyGuard_Environmental_Report.pdf",
    mime="application/pdf"
)

# ===== END PDF ENVIRONMENTAL REPORT =====

st.caption(
    "Temperature is a reference input to the FortyGuard analysis. "
    "Solar irradiance values are modeled clear-sky estimates."
)
