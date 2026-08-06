import streamlit as st
import ee
import geemap
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

st.set_page_config(
    layout="wide",
    page_title="GOES Fire Timelapse",
    initial_sidebar_state="collapsed",
)

EE_PROJECT = "ee-passeionamatamapas"
GOES_16_START = date(2017, 12, 18)
GOES_19_START = date(2025, 4, 8)

# ---------------------------------------------------------------------------
# Styling — ground-station console. Every color derives from the satellite
# imagery itself: space black, the chartreuse state-boundary signal, ember.
# ---------------------------------------------------------------------------

CONSOLE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+Condensed:wght@600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

:root {
  --bg: #070B0E;
  --panel: #0D1419;
  --panel-2: #121A21;
  --line: #1F2B33;
  --ink: #D9E2E6;
  --ink-dim: #6E7D85;
  --signal: #ECF71B;
  --ember: #FF6A1A;
  --mono: 'IBM Plex Mono', 'SFMono-Regular', Menlo, monospace;
  --sans: 'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif;
  --display: 'IBM Plex Sans Condensed', 'IBM Plex Sans', system-ui, sans-serif;
}

html, body, [data-testid="stAppViewContainer"] {
  background-color: var(--bg);
}

/* Earthshine glow — faint atmosphere scatter at the limb of the disk. */
[data-testid="stAppViewContainer"] {
  background-image:
    radial-gradient(900px 380px at 50% -120px, rgba(41, 74, 92, 0.32), transparent 70%),
    radial-gradient(1400px 600px at 50% -220px, rgba(10, 18, 24, 0.9), transparent 75%);
}

[data-testid="stHeader"], [data-testid="stToolbar"] { display: none; }

.block-container {
  max-width: 1180px;
  padding-top: 1.2rem;
  padding-bottom: 4rem;
}

/* Component masthead iframe */
iframe { border: none !important; }

/* ------------------------------------------------------------------ */
/* Console panels                                                     */
/* ------------------------------------------------------------------ */

[data-testid="stVerticalBlockBorderWrapper"] {
  border: 1px solid var(--line) !important;
  border-radius: 6px !important;
  background: linear-gradient(180deg, var(--panel), rgba(13, 20, 25, 0.6));
  padding: 1rem 1.15rem 1.1rem !important;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
}

.panel-label {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  font-family: var(--mono);
  font-size: 0.68rem;
  font-weight: 500;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--ink-dim);
  margin: 0 0 0.85rem;
  padding-bottom: 0.55rem;
  border-bottom: 1px solid var(--line);
}
.panel-label::before {
  content: "";
  width: 7px;
  height: 7px;
  background: var(--signal);
  clip-path: polygon(0 0, 100% 0, 100% 100%);
}

.field-label {
  font-family: var(--mono);
  font-size: 0.64rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-dim);
  margin-bottom: 0.35rem;
}

.tel-bbox {
  font-family: var(--mono);
  font-size: 0.72rem;
  color: var(--ink-dim);
  letter-spacing: 0.05em;
  margin-top: 0.45rem;
}
.tel-bbox b { color: var(--signal); font-weight: 500; }

/* ------------------------------------------------------------------ */
/* Widgets — pull native Streamlit controls into the console          */
/* ------------------------------------------------------------------ */

[data-testid="stWidgetLabel"] p {
  font-family: var(--mono);
  font-size: 0.64rem !important;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-dim) !important;
}

[data-baseweb="select"] > div,
[data-baseweb="input"],
[data-testid="stDateInput"] [data-baseweb="input"],
[data-testid="stTimeInput"] [data-baseweb="input"] {
  background-color: var(--panel-2) !important;
  border-color: var(--line) !important;
  border-radius: 4px !important;
  color: var(--ink) !important;
}

[data-baseweb="input"] input {
  color: var(--ink) !important;
  font-family: var(--mono) !important;
  font-size: 0.8rem !important;
  letter-spacing: 0.04em;
}

[data-testid="stSelectbox"] [role="listbox"] { background: var(--panel-2) !important; }
[data-testid="stSelectbox"] [role="option"]:hover { background: var(--panel) !important; }

/* Sliders */
[data-testid="stSlider"] [role="slider"] {
  background: var(--signal) !important;
  border: 2px solid var(--bg) !important;
  box-shadow: 0 0 0 1px var(--line);
}
/* Track (skip tick labels & thumb bubble, which carry data-testid) */
[data-testid="stSlider"] div[data-baseweb="slider"] > div > div:not([data-testid]) {
  background-color: var(--line) !important;
}
/* Value bubble above the thumb */
[data-testid="stSlider"] [data-testid="stSliderThumbValue"] {
  background: var(--panel-2) !important;
  border: 1px solid var(--line) !important;
  border-radius: 3px !important;
  color: var(--ink) !important;
  font-family: var(--mono) !important;
  font-size: 0.72rem !important;
  line-height: 1.4 !important;
  text-align: center !important;
}
[data-testid="stSlider"] [data-testid="stMarkdownContainer"] p {
  font-family: var(--mono) !important;
  font-size: 0.8rem !important;
  color: var(--ink) !important;
}

/* Buttons */
.stButton button, .stDownloadButton button {
  font-family: var(--mono) !important;
  font-size: 0.72rem !important;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  border-radius: 4px !important;
  border: 1px solid var(--line) !important;
  background: var(--panel-2) !important;
  color: var(--ink) !important;
  font-weight: 600 !important;
}
.stButton button:hover, .stDownloadButton button:hover {
  border-color: var(--signal) !important;
  color: var(--signal) !important;
  background: var(--panel) !important;
}

.stButton button[kind="primary"] {
  background: var(--ember) !important;
  border-color: var(--ember) !important;
  color: #140500 !important;
  box-shadow: 0 0 18px rgba(255, 106, 26, 0.25);
}
.stButton button[kind="primary"]:hover {
  background: #ff7c36 !important;
  border-color: #ff7c36 !important;
  color: #140500 !important;
}

/* Progress — scan-line sweep (Streamlit 1.41 st.progress uses emotion
   classes, so target the implicit progressbar role on the fill; exclude
   the slider thumb, which also carries aria-valuenow) */
div:has(> div[aria-valuenow]:not([role="slider"])) {
  background: var(--line) !important;
  border-radius: 1px !important;
  height: 4px !important;
  overflow: hidden;
}
div[aria-valuenow]:not([role="slider"]) {
  background: linear-gradient(90deg, var(--signal), #cff24a) !important;
  border-radius: 1px !important;
  height: 4px !important;
  min-height: 4px !important;
  position: relative;
  overflow: hidden;
}
div[aria-valuenow]:not([role="slider"]) > div { display: none; }
div[aria-valuenow]:not([role="slider"])::after {
  content: "";
  position: absolute;
  inset: 0;
  width: 60%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.55), transparent);
  animation: scan-sweep 1.4s linear infinite;
}
@keyframes scan-sweep {
  0%   { transform: translateX(-100%); }
  100% { transform: translateX(180%); }
}

/* Telemetry status line */
.tel-status-line {
  font-family: var(--mono);
  font-size: 0.74rem;
  letter-spacing: 0.06em;
  color: var(--ink-dim);
}
.tel-status-line .ok { color: var(--signal); font-weight: 600; }
.tel-status-line .warn { color: var(--ember); font-weight: 600; }

/* ------------------------------------------------------------------ */
/* Playback stage                                                     */
/* ------------------------------------------------------------------ */

.playback-frame {
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--panel);
  padding: 1.15rem;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
}

.playback-empty {
  border: 1px dashed var(--line);
  border-radius: 4px;
  background:
    radial-gradient(circle at 50% 46%, rgba(41, 74, 92, 0.18), transparent 42%),
    var(--panel);
  min-height: 300px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  padding: 2rem;
  text-align: center;
}

.playback-empty .globe {
  width: 74px;
  height: 74px;
  border-radius: 50%;
  border: 1px solid var(--line);
  background:
    radial-gradient(circle at 34% 30%, rgba(236, 247, 27, 0.5), transparent 8%),
    radial-gradient(circle at 58% 62%, rgba(255, 106, 26, 0.55), transparent 9%),
    radial-gradient(circle at 72% 42%, rgba(236, 247, 27, 0.3), transparent 7%),
    radial-gradient(circle at 44% 74%, rgba(255, 106, 26, 0.3), transparent 8%),
    radial-gradient(circle at 50% 50%, rgba(74, 120, 145, 0.35), rgba(10, 16, 21, 0.9) 70%);
  box-shadow: inset 0 0 22px rgba(0, 0, 0, 0.6), 0 0 34px rgba(59, 100, 124, 0.18);
}

.playback-empty .msg {
  font-family: var(--mono);
  font-size: 0.78rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--ink-dim);
}
.playback-empty .hint {
  font-family: var(--mono);
  font-size: 0.7rem;
  letter-spacing: 0.05em;
  color: var(--ink-dim);
  opacity: 0.7;
  max-width: 340px;
}

.tel-caption {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem 1.4rem;
  font-family: var(--mono);
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  color: var(--ink-dim);
  margin: 0.9rem 0 0.6rem;
}
.tel-caption b { color: var(--ink); font-weight: 500; }

[data-testid="stImage"] img {
  max-width: 100%;
  height: auto;
  border: 1px solid var(--line);
  border-radius: 4px;
}

/* Thermal ramp legend */
.thermal-legend {
  margin-top: 1.1rem;
  font-family: var(--mono);
  font-size: 0.64rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--ink-dim);
}
.thermal-legend .ramp {
  height: 10px;
  margin: 0.45rem 0;
  border-radius: 2px;
  background: linear-gradient(90deg, #0B2E59, #1F6BF0, #8FD0F2, #ECF71B, #FFB31A, #FF6A1A, #D83A00);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.06);
}
.thermal-legend .keys { display: flex; justify-content: space-between; }

/* Alerts */
[data-testid="stAlert"] {
  border-radius: 4px !important;
  border: 1px solid var(--line) !important;
}
[data-testid="stAlert"] p { font-family: var(--mono) !important; font-size: 0.75rem !important; letter-spacing: 0.03em; }

/* Calendar / select popovers */
[data-testid="stDateInput"] [data-baseweb="popover"],
[data-testid="stTimeInput"] [data-baseweb="popover"] { background: var(--panel-2) !important; }

/* Focus rings */
:focus-visible {
  outline: 2px solid var(--signal) !important;
  outline-offset: 1px;
}

/* Mobile */
@media (max-width: 760px) {
  .block-container { padding-top: 0.8rem; }
  .playback-empty { min-height: 220px; }
}

@media (prefers-reduced-motion: reduce) {
  .tel-dot, div[aria-valuenow]:not([role="slider"])::after { animation: none !important; }
}
</style>
"""

st.markdown(CONSOLE_CSS, unsafe_allow_html=True)


def render_masthead(status: str = "STANDBY") -> None:
    """Telemetry masthead: live UTC clock + receiver readout of the
    current capture configuration. Runs as a component so the clock can tick.
    Reads widget keys so the readout is current on the same rerun."""
    sig = select_goes_satellite(
        st.session_state.get(
            "start_d_widget", date.today() - timedelta(days=1)
        )
    )
    scan = st.session_state.get("scan_widget", "full_disk").upper()
    preset = st.session_state.get("preset_widget", "South America")
    if st.session_state.get("receiving"):
        status = "RECEIVING"
    dot_cls = "" if status == "RECEIVING" else "standby"

    html = f"""
    <style>
      :root {{ --bg:#070B0E; --panel:#0D1419; --panel-2:#121A21; --line:#1F2B33;
               --ink:#D9E2E6; --ink-dim:#6E7D85; --signal:#ECF71B; }}
      * {{ box-sizing: border-box; margin: 0; padding: 0; }}
      body {{ font-family: 'IBM Plex Mono', monospace; background: transparent; }}
      .masthead {{ display:flex; align-items:center; justify-content:space-between;
                    gap:1rem; flex-wrap:wrap; border:1px solid var(--line);
                    border-radius:6px; padding:.85rem 1.15rem;
                    background:linear-gradient(180deg, var(--panel-2), var(--panel));
                    box-shadow: inset 0 1px 0 rgba(255,255,255,.03); }}
      .status {{ display:flex; align-items:center; gap:.55rem; font-size:.72rem;
                  letter-spacing:.14em; color:var(--ink-dim); white-space:nowrap; }}
      .dot {{ width:9px; height:9px; border-radius:50%; background:var(--signal);
               box-shadow:0 0 0 0 rgba(236,247,27,.55);
               animation:pulse 2.2s ease-out infinite; }}
      .standby .dot {{ background:var(--ink-dim); box-shadow:none; animation:none; }}
      @keyframes pulse {{ 0%{{box-shadow:0 0 0 0 rgba(236,247,27,.5);}}
                          70%{{box-shadow:0 0 0 7px rgba(236,247,27,0);}}
                          100%{{box-shadow:0 0 0 0 rgba(236,247,27,0);}} }}
      .mission {{ font-family:'IBM Plex Sans Condensed',sans-serif; font-weight:700;
                   font-size:1.3rem; letter-spacing:.06em; line-height:1;
                   color:var(--ink); text-transform:uppercase; }}
      .mission span {{ color:var(--signal); }}
      .sub {{ font-size:.66rem; letter-spacing:.22em; color:var(--ink-dim);
               text-transform:uppercase; margin-top:.28rem; }}
      .readout {{ font-size:.72rem; letter-spacing:.08em; color:var(--ink-dim);
                   text-align:right; line-height:1.75; white-space:nowrap; }}
      .readout b {{ color:var(--ink); font-weight:500; }}
      .readout .sig {{ color:var(--signal); font-weight:600; }}
      .clock {{ font-size:1.05rem; font-weight:600; letter-spacing:.1em;
                 color:var(--ink); text-align:right; }}
      .clock .utc {{ color:var(--ink-dim); font-size:.62rem; letter-spacing:.2em;
                      display:block; margin-bottom:.15rem; }}
      @media (max-width:720px) {{
        .masthead {{ flex-direction:column; align-items:flex-start; }}
        .readout, .clock {{ text-align:left; }}
      }}
      @media (prefers-reduced-motion: reduce) {{ .dot {{ animation:none; }} }}
    </style>
    <div class="masthead {dot_cls}">
      <div class="status"><span class="dot"></span>{status}</div>
      <div>
        <div class="mission">GOES FIRE <span>TIMELAPSE</span></div>
        <div class="sub">Geostationary Wildfire Monitor</div>
      </div>
      <div class="readout">
        <div>SIG <span class="sig">{sig}</span> &middot; SCAN <b>{scan}</b></div>
        <div>REG <b>{preset}</b></div>
      </div>
      <div class="clock"><span class="utc">utc</span><span id="tel-clock">--:--:--</span></div>
    </div>
    <script>
      (function () {{
        var pad = function (x) {{ return String(x).padStart(2, '0'); }};
        function tick () {{
          var el = document.getElementById('tel-clock');
          if (!el) return;
          var n = new Date();
          el.textContent = pad(n.getUTCHours()) + ':' + pad(n.getUTCMinutes()) + ':' + pad(n.getUTCSeconds());
        }}
        if (window.__telClock) {{ tick(); return; }}
        window.__telClock = true;
        tick();
        window.__telClockInt = window.__telClockInt || setInterval(tick, 1000);
        function resize () {{
          var h = document.body.scrollHeight;
          if (window.frameElement) window.frameElement.style.height = h + 'px';
        }}
        window.addEventListener('resize', resize);
        resize();
      }})();
    </script>
    """
    st.components.v1.html(html, height=92)


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


def merge_gifs_pillow(gif_paths: list[Path], output_path: Path, fps: int) -> None:
    frames: list[Image.Image] = []
    for path in gif_paths:
        img = Image.open(path)
        try:
            while True:
                frames.append(img.copy())
                img.seek(img.tell() + 1)
        except EOFError:
            pass

    if not frames:
        return

    duration = int(1000 / fps)
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        optimize=True,
    )


def generate_timelapse_chunk(
    output_path: Path,
    start_dt: datetime,
    end_dt: datetime,
    goes_data: str,
    scan: str,
    region: ee.Geometry,
    dimensions: int,
    fps: int,
) -> bool:
    start_str = start_dt.strftime("%Y-%m-%dT%H:%M")
    end_str = end_dt.strftime("%Y-%m-%dT%H:%M")

    fc = get_br_estados_fc()
    geemap.goes_fire_timelapse(
        roi=region,
        out_gif=str(output_path),
        start_date=start_str,
        end_date=end_str,
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
    return output_path.exists()


def split_and_generate(
    tmp_dir: str,
    start_dt: datetime,
    end_dt: datetime,
    goes_data: str,
    scan: str,
    region: ee.Geometry,
    dimensions: int,
    fps: int,
    output_path: Path,
    status_text: object,
    progress_bar: object,
    base_progress: float = 25.0,
    progress_range: float = 70.0,
    depth: int = 0,
    max_depth: int = 3,
) -> list[Path]:
    mid_dt = start_dt + (end_dt - start_dt) / 2
    segments: list[Path] = []

    halves = [
        (start_dt, mid_dt, "left"),
        (mid_dt, end_dt, "right"),
    ]

    for i, (h_start, h_end, label) in enumerate(halves):
        chunk_idx = depth * 2 + i
        total_at_depth = 2 ** (depth + 1)
        pct = base_progress + (chunk_idx / total_at_depth) * progress_range
        progress_bar.progress(min(int(pct), 99))
        status_text.markdown(
            f"<div class='tel-status-line'>SEG {chunk_idx + 1}/{total_at_depth} "
            f"&middot; {h_start.strftime('%H:%M')}–{h_end.strftime('%H:%M')}Z "
            f"&middot; <span class='warn'>ACQUIRING</span></div>",
            unsafe_allow_html=True,
        )

        chunk_path = Path(tmp_dir) / f"chunk_{depth}_{label}.gif"
        success = generate_timelapse_chunk(
            chunk_path, h_start, h_end, goes_data, scan, region, dimensions, fps
        )

        if success:
            segments.append(chunk_path)
        elif depth < max_depth:
            sub_segments = split_and_generate(
                tmp_dir,
                h_start,
                h_end,
                goes_data,
                scan,
                region,
                dimensions,
                fps,
                output_path,
                status_text,
                progress_bar,
                base_progress=pct,
                progress_range=progress_range / 2,
                depth=depth + 1,
                max_depth=max_depth,
            )
            segments.extend(sub_segments)

    if depth == 0 and segments:
        status_text.markdown(
            "<div class='tel-status-line'>MERGE &middot; "
            "<span class='warn'>CONCATENATING SEGMENTS</span></div>",
            unsafe_allow_html=True,
        )
        segments.sort(key=lambda p: p.name)
        merge_gifs_pillow(segments, output_path, fps)

    return segments


# ---------------------------------------------------------------------------
# App UI
# ---------------------------------------------------------------------------

get_ee_initialized()

st.session_state.setdefault("last_settings", {})
st.session_state.setdefault("pending_gif_path", None)
st.session_state.setdefault("receiving", False)

render_masthead()

# --- Capture window --------------------------------------------------------

with st.container(border=True):
    st.markdown("<p class='panel-label'>Capture Window</p>", unsafe_allow_html=True)
    col_region, col_time = st.columns([1, 2], gap="medium")

    with col_region:
        st.markdown("<p class='field-label'>Region</p>", unsafe_allow_html=True)
        preset = st.selectbox(
            "Region Preset",
            REGION_PRESET_NAMES,
            index=0,
            label_visibility="collapsed",
            key="preset_widget",
        )
        region = REGION_PRESETS[preset].to_ee()
        bbox = REGION_PRESETS[preset]
        st.markdown(
            f"<div class='tel-bbox'>BBOX <b>{bbox.west},{bbox.south}</b> "
            f"&rarr; <b>{bbox.east},{bbox.north}</b></div>",
            unsafe_allow_html=True,
        )

    with col_time:
        st.markdown("<p class='field-label'>Timeline · UTC</p>", unsafe_allow_html=True)
        col_from, col_to = st.columns(2, gap="medium")

        with col_from:
            default_start = st.session_state.last_settings.get(
                "start_d", date.today() - timedelta(days=1)
            )
            st.markdown(
                "<div class='tel-bbox' style='margin:0'>FROM</div>",
                unsafe_allow_html=True,
            )
            start_d = st.date_input(
                "Start date", default_start, label_visibility="collapsed", key="start_d_widget"
            )
            default_start_t = st.session_state.last_settings.get("start_t", time(0, 0))
            start_t = st.time_input(
                "Start time", default_start_t, label_visibility="collapsed"
            )

        with col_to:
            default_end = st.session_state.last_settings.get("end_d", date.today())
            st.markdown(
                "<div class='tel-bbox' style='margin:0'>TO</div>",
                unsafe_allow_html=True,
            )
            end_d = st.date_input(
                "End date", default_end, label_visibility="collapsed"
            )
            default_end_t = st.session_state.last_settings.get("end_t", time(23, 59))
            end_t = st.time_input(
                "End time", default_end_t, label_visibility="collapsed"
            )

# --- Export settings -------------------------------------------------------

with st.container(border=True):
    st.markdown("<p class='panel-label'>Export · Gif</p>", unsafe_allow_html=True)
    col_dim, col_fps, col_scan = st.columns(3, gap="medium")

    with col_dim:
        dimensions = st.slider("Dimensions (px)", 300, 1200, 600, step=50)

    with col_fps:
        frames_per_second = st.slider("Frames per Second", 1, 12, 6)

    with col_scan:
        st.markdown("<p class='field-label'>Scan</p>", unsafe_allow_html=True)
        scan = st.selectbox(
            "Scan Type",
            ["full_disk", "regional"],
            index=0,
            label_visibility="collapsed",
            key="scan_widget",
        )

    generate = st.button(
        "Generate Timelapse",
        type="primary",
        use_container_width=True,
        on_click=lambda: st.session_state.__setitem__("receiving", True),
    )

# --- Persist widget values for the masthead readout ------------------------

st.session_state["start_d"] = start_d
st.session_state["scan"] = scan
st.session_state["preset"] = preset

# --- Generate --------------------------------------------------------------

if generate:
    start_dt = datetime.combine(start_d, start_t)
    end_dt = datetime.combine(end_d, end_t)
    if start_dt >= end_dt:
        st.session_state["receiving"] = False
        st.error("End time must be after start time.")
    elif start_d < GOES_16_START:
        st.session_state["receiving"] = False
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
        st.session_state.end_date_str = end_date_str

        goes_data = select_goes_satellite(start_d)

        with st.spinner(
            f"Generating timelapse from {start_date_str} to {end_date_str}..."
        ):
            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                status_text.markdown(
                    "<div class='tel-status-line'>INIT &middot; "
                    "<span class='warn'>PROCESSING SATELLITE IMAGERY</span></div>",
                    unsafe_allow_html=True,
                )
                progress_bar.progress(25)

                with TemporaryDirectory() as tmp_dir:
                    output_gif_path = Path(tmp_dir) / "timelapse.gif"

                    split_and_generate(
                        tmp_dir=tmp_dir,
                        start_dt=start_dt,
                        end_dt=end_dt,
                        goes_data=goes_data,
                        scan=scan,
                        region=region,
                        dimensions=dimensions,
                        fps=frames_per_second,
                        output_path=output_gif_path,
                        status_text=status_text,
                        progress_bar=progress_bar,
                    )

                    if not output_gif_path.exists():
                        st.error(
                            "All segments failed. Earth Engine may be "
                            "overloaded — try a shorter time range or "
                            "smaller dimensions."
                        )
                        st.stop()

                    st.session_state["generated_gif_bytes"] = (
                        output_gif_path.read_bytes()
                    )

                st.session_state["receiving"] = False
                progress_bar.progress(100)
                status_text.markdown(
                    "<div class='tel-status-line'>DONE &middot; "
                    "<span class='ok'>FRAME COMPLETE</span></div>",
                    unsafe_allow_html=True,
                )
                st.rerun()

            except Exception as e:
                st.session_state["receiving"] = False
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

# --- Playback --------------------------------------------------------------

with st.container(border=True):
    st.markdown("<p class='panel-label'>Playback</p>", unsafe_allow_html=True)

    if "generated_gif_bytes" in st.session_state:
        st.markdown("<div class='playback-frame'>", unsafe_allow_html=True)
        st.image(st.session_state["generated_gif_bytes"])

        start_lbl = st.session_state.get("start_date_str", "--")
        end_lbl = st.session_state.get("end_date_str", "--")
        region_lbl = st.session_state.get("preset", "--")
        sig_lbl = select_goes_satellite(
            st.session_state.last_settings.get("start_d", date.today())
        )
        st.markdown(
            f"""
            <div class="tel-caption">
              <div>WINDOW <b>{start_lbl}</b> &rarr; <b>{end_lbl}</b></div>
              <div>SIG <b>{sig_lbl}</b></div>
              <div>REG <b>{region_lbl}</b></div>
              <div>FPS <b>{frames_per_second}</b></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        filename = f"goes_fire_{st.session_state.get('start_date_str', 'output')}.gif"
        st.download_button(
            label="Download GIF",
            data=st.session_state["generated_gif_bytes"],
            file_name=filename,
            mime="image/gif",
        )
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            """
            <div class="playback-empty">
              <div class="globe"></div>
              <div class="msg">Standing By</div>
              <div class="hint">Set a capture window above, then generate. Fire
              hot spots render blue &rarr; yellow &rarr; red by temperature.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div class="thermal-legend">
          <div>Fire Temperature Ramp · ABI Hot Spot Detection</div>
          <div class="ramp"></div>
          <div class="keys"><span>cool</span><span>active</span><span>hot</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
