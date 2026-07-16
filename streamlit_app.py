import streamlit as st
import ee
import geemap
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

st.set_page_config(layout="wide")

EE_PROJECT = "ee-passeionamatamapas"
GOES_16_START = date(2017, 12, 18)
GOES_19_START = date(2025, 4, 8)


@dataclass(frozen=True)
class RegionBBox:
    west: float
    south: float
    east: float
    north: float

    def to_ee(self) -> ee.Geometry:
        return ee.Geometry.BBox(self.west, self.south, self.east, self.north)


REGION_PRESETS: dict[str, RegionBBox] = {
    "South America": RegionBBox(-85.0, -56.0, -34.0, 13.0),
    "Continental US": RegionBBox(-130.0, 24.0, -65.0, 50.0),
    "Full Disk": RegionBBox(-180.0, -90.0, 180.0, 90.0),
}
REGION_PRESET_NAMES = tuple(REGION_PRESETS)


def init_ee() -> None:
    credentials_info = st.secrets["ee"]
    credentials = ee.ServiceAccountCredentials(
        credentials_info["client_email"], key_data=credentials_info["private_key"]
    )
    ee.Initialize(credentials, project=EE_PROJECT)


@st.cache_resource
def get_ee_initialized() -> bool:
    init_ee()
    return True


@st.cache_resource
def get_br_estados_fc() -> ee.FeatureCollection:
    return ee.FeatureCollection(f"projects/{EE_PROJECT}/assets/br_estados")


def select_goes_satellite(start_d: date) -> str:
    return "GOES-16" if start_d < GOES_19_START else "GOES-19"


def generate_timelapse(
    output_path: Path,
    start_date_str: str,
    end_date_str: str,
    goes_data: str,
    scan: str,
    region: ee.Geometry,
    dimensions: int,
    fps: int,
) -> None:
    fc = get_br_estados_fc()

    geemap.goes_fire_timelapse(
        roi=region,
        out_gif=str(output_path),
        start_date=start_date_str,
        end_date=end_date_str,
        data=goes_data,
        scan=scan,
        dimensions=dimensions,
        framesPerSecond=fps,
        date_format="YYYY-MM-dd HH:mm",
        crs="EPSG:3857",
        overlay_data=fc,
        overlay_color="#ECF71B",
        overlay_width=1,
        overlay_opacity=1.0,
        add_progress_bar=True,
        mp4=False,
    )


# --- App UI ---

st.title("GOES Fire Timelapse App")
get_ee_initialized()

st.session_state.setdefault("last_settings", {})
st.session_state.setdefault("pending_gif_path", None)

col1, col2 = st.columns([1, 3])

with col1:
    st.subheader("1. Select Region")
    preset = st.selectbox("Region Preset", REGION_PRESET_NAMES, index=0)
    region = REGION_PRESETS[preset].to_ee()

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
    if start_dt >= end_dt:
        st.error("End time must be after start time.")
    elif start_d < GOES_16_START:
        st.error(
            f"GOES-16 data available from {GOES_16_START.strftime('%B %d, %Y')} "
            "onwards."
        )
    else:
        start_date_str = start_dt.strftime("%Y-%m-%dT%H:%M")
        end_date_str = end_dt.strftime("%Y-%m-%dT%H:%M")

        st.session_state.last_settings = {
            "start_d": start_d,
            "end_d": end_d,
            "start_t": start_t,
            "end_t": end_t,
        }
        st.session_state.start_date_str = start_date_str

        goes_data = select_goes_satellite(start_d)
        st.info(f"Using {goes_data} satellite data")

        with st.spinner(
            f"Generating timelapse from {start_date_str} to {end_date_str}..."
        ):
            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                status_text.text("Processing satellite imagery...")
                progress_bar.progress(25)

                with TemporaryDirectory() as tmp_dir:
                    output_gif_path = Path(tmp_dir) / "timelapse.gif"

                    generate_timelapse(
                        output_path=output_gif_path,
                        start_date_str=start_date_str,
                        end_date_str=end_date_str,
                        goes_data=goes_data,
                        scan=scan,
                        region=region,
                        dimensions=dimensions,
                        fps=frames_per_second,
                    )

                    if not output_gif_path.exists():
                        st.error(
                            "Timelapse generation failed. The server did not "
                            "return a GIF — likely a timeout. Try a shorter "
                            "time range or smaller dimensions."
                        )
                        st.stop()

                    # Read GIF bytes into session state so it survives temp dir cleanup
                    st.session_state["generated_gif_bytes"] = (
                        output_gif_path.read_bytes()
                    )

                progress_bar.progress(100)
                status_text.text("Complete!")
                st.success("Timelapse generated!")
                st.rerun()

            except Exception as e:
                progress_bar.empty()
                status_text.empty()
                error_msg = str(e)
                if "quota" in error_msg.lower():
                    st.error(
                        "Earth Engine quota exceeded. "
                        "Try a shorter time range or wait and try again."
                    )
                elif "invalid date" in error_msg.lower():
                    st.error("Invalid date range. Please check the selected dates.")
                else:
                    st.error(f"Error generating timelapse: {error_msg}")

if "generated_gif_bytes" in st.session_state:
    st.divider()
    st.subheader("Generated Timelapse GIF")
    st.image(st.session_state["generated_gif_bytes"], width="content")

    filename = f"goes_fire_{st.session_state.get('start_date_str', 'output')}.gif"
    st.download_button(
        label="Download GIF",
        data=st.session_state["generated_gif_bytes"],
        file_name=filename,
        mime="image/gif",
    )
