import streamlit as st
import ee
import geemap
from datetime import date, datetime, time, timedelta
import tempfile
import os
import io
import contextlib
from PIL import Image

import geemap.timelapse
_add_overlay = geemap.timelapse.add_overlay

def _patched_add_overlay(collection, data, color, width, opacity, region=None):
    fc = data if isinstance(data, ee.FeatureCollection) else ee.FeatureCollection(data)
    crs = collection.first().projection()
    overlay = (
        ee.Image()
        .byte()
        .setDefaultProjection(crs)
        .paint(fc, 1, width)
        .visualize(palette=geemap.coreutils.check_color(color), opacity=opacity)
    )
    return collection.map(
        lambda img: img.blend(overlay).set(
            "system:time_start", img.get("system:time_start")
        )
    )

geemap.timelapse.add_overlay = _patched_add_overlay

st.set_page_config(layout="wide")

GOES_16_START = date(2017, 12, 18)
GOES_19_START = date(2025, 4, 8)

REGION_PRESETS = {
    "South America": (-85.0, -56.0, -34.0, 13.0),
    "Continental US": (-130.0, 24.0, -65.0, 50.0),
    "Full Disk": (-180.0, -90.0, 180.0, 90.0),
}


def init_ee():
    credentials_info = st.secrets["ee"]
    credentials = ee.ServiceAccountCredentials(
        credentials_info["client_email"], key_data=credentials_info["private_key"]
    )
    ee.Initialize(credentials, project="ee-passeionamatamapas")


@st.cache_resource
def get_ee_initialized():
    init_ee()
    return True


def get_goes_data(start_d: date) -> str:
    return "GOES-16" if start_d < GOES_19_START else "GOES-19"


st.title("GOES Fire Timelapse App")

get_ee_initialized()

if "last_settings" not in st.session_state:
    st.session_state.last_settings = {}

col1, col2 = st.columns([1, 3])

with col1:
    st.subheader("1. Select Region")
    preset = st.selectbox("Region Preset", list(REGION_PRESETS.keys()), index=0)
    region_coords = REGION_PRESETS[preset]
    region = ee.Geometry.BBox(*region_coords)

with col2:
    st.subheader("2. Select Time Range")
    col_date, col_time = st.columns(2)

    with col_date:
        default_start = st.session_state.last_settings.get(
            "start_d", date.today() - timedelta(days=1)
        )
        start_d = st.date_input("Start date", default_start)
        default_end = st.session_state.last_settings.get("end_d", date.today())
        end_d = st.date_input("End date", default_end)

    with col_time:
        default_start_t = st.session_state.last_settings.get("start_t", time(0, 0))
        start_t = st.time_input("Start time", default_start_t)
        default_end_t = st.session_state.last_settings.get("end_t", time(23, 59))
        end_t = st.time_input("End time", default_end_t)

st.subheader("3. Customize GIF")

col_dim, col_fps, col_scan = st.columns(3)

with col_dim:
    dimensions = st.slider("Dimensions (px)", 300, 1200, 600, step=50)

with col_fps:
    frames_per_second = st.slider("Frames per Second", 1, 12, 6)

with col_scan:
    scan = st.selectbox("Scan Type", ["full_disk", "regional"], index=0)

if st.button("Generate Timelapse GIF"):
    start_dt = datetime.combine(start_d, start_t)
    end_dt = datetime.combine(end_d, end_t)
    start_date_str = start_dt.strftime("%Y-%m-%dT%H:%M")
    end_date_str = end_dt.strftime("%Y-%m-%dT%H:%M")

    if start_dt >= end_dt:
        st.error("End time must be after start time.")
    elif start_d < GOES_16_START:
        st.error(
            f"GOES-16 data available from {GOES_16_START.strftime('%B %d, %Y')} onwards."
        )
    else:
        st.session_state.last_settings = {
            "start_d": start_d,
            "end_d": end_d,
            "start_t": start_t,
            "end_t": end_t,
        }
        st.session_state.start_date_str = start_date_str

        goes_data = get_goes_data(start_d)
        st.info(f"Using {goes_data} satellite data")

        with st.spinner(
            f"Generating timelapse from {start_date_str} to {end_date_str}..."
        ):
            progress_bar = st.progress(0)
            status_text = st.empty()

            with tempfile.NamedTemporaryFile(
                suffix=".gif", delete=False
            ) as tmp_gif_file:
                output_gif_path = tmp_gif_file.name

            try:
                status_text.text("Processing satellite imagery...")
                progress_bar.progress(25)

                with open("br_states.json") as f:
                    estados_fc = ee.FeatureCollection(f.read())

                with io.StringIO() as buf, contextlib.redirect_stdout(buf):
                    timelapse_result = geemap.goes_fire_timelapse(
                        roi=region,
                        out_gif=output_gif_path,
                        start_date=start_date_str,
                        end_date=end_date_str,
                        data=goes_data,
                        scan=scan,
                        dimensions=dimensions,
                        framesPerSecond=frames_per_second,
                        date_format="YYYY-MM-dd HH:mm",
                        add_progress_bar=False,
                        mp4=False,
                        overlay_data=estados_fc,
                        overlay_color="#FF0000",
                        overlay_width=1,
                        overlay_opacity=0.8,
                    )
                    geemap_output = buf.getvalue()

                if not os.path.exists(output_gif_path):
                    raise RuntimeError(
                        f"GIF download failed: {geemap_output}"
                    )

                with Image.open(output_gif_path) as validate_img:
                    validate_img.verify()

                progress_bar.progress(100)
                status_text.text("Complete!")

                st.session_state["generated_gif_path"] = output_gif_path
                st.success("Timelapse generated!")
                st.rerun()

            except Exception as e:
                progress_bar.empty()
                status_text.empty()
                error_msg = str(e)
                if "quota" in error_msg.lower():
                    st.error(
                        "Earth Engine quota exceeded. Try a shorter time range or wait and try again."
                    )
                elif "invalid date" in error_msg.lower():
                    st.error("Invalid date range. Please check the selected dates.")
                else:
                    st.error(f"Error generating timelapse: {error_msg}")
                if os.path.exists(output_gif_path):
                    os.remove(output_gif_path)

if "generated_gif_path" in st.session_state and os.path.exists(
    st.session_state["generated_gif_path"]
):
    st.divider()
    st.subheader("Generated Timelapse GIF")
    st.image(st.session_state["generated_gif_path"], use_container_width=False)

    filename = f"goes_fire_{st.session_state.get('start_date_str', 'output')}.gif"
    with open(st.session_state["generated_gif_path"], "rb") as f:
        st.download_button(
            label="Download GIF", data=f, file_name=filename, mime="image/gif"
        )
