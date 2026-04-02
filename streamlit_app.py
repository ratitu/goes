import streamlit as st

st.title("🎈 My new Streamlit app")
st.write(
    "Let's start building! For help and inspiration, head over to [docs.streamlit.io](https://docs.streamlit.io/)."
)

#import streamlit as st
import ee
import geemap
from datetime import date, datetime, time, timedelta
import tempfile
import os

st.set_page_config(layout="wide")
st.title("GOES Fire Timelapse App")

# Carrega o dicionário completo da chave
credentials_info = st.secrets["earth_engine_key"]

# Inicializa com as credenciais da Service Account
credentials = ee.ServiceAccountCredentials(
    credentials_info["client_email"], 
    key_data=credentials_info["private_key"]
)
ee.Initialize(credentials, project="ee-passeionamatamapas")

# Initialize Earth Engine
# geemap.ee_initialize() is not suitable for Streamlit, use ee.Initialize()
#try:
#    ee.Initialize(project="ee-passeionamatamapas")
#except Exception as e:
#    ee.Authenticate()
#    ee.Initialize(project="ee-passeionamatamapas")

# Define the region for South America
region = ee.Geometry.BBox(-85.0, -56.0, -34.0, 13.0)

# --- Date and Time Selection ---
st.subheader("1. Select Time Range")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**Start Period**")
    start_d = st.date_input("Start date", date.today() - timedelta(days=1))
    start_t = st.time_input("Start time", time(0, 0)) # Defaults to midnight

with col2:
    st.markdown("**End Period**")
    end_d = st.date_input("End date", date.today())
    end_t = st.time_input("End time", time(23, 59)) # Defaults to end of day

# Combine date and time into the format geemap expects: 'YYYY-MM-DDTHH:mm'
start_date_str = datetime.combine(start_d, start_t).strftime('%Y-%m-%dT%H:%M')
end_date_str = datetime.combine(end_d, end_t).strftime('%Y-%m-%dT%H:%M')

# --- Generate Timelapse ---
if st.button('Generate Timelapse GIF'):
    if datetime.combine(start_d, start_t) >= datetime.combine(end_d, end_t):
        st.error("Error: End time must be after start time.")
    else:
        with st.spinner(f'Generating timelapse from {start_date_str} to {end_date_str}...'):
            with tempfile.NamedTemporaryFile(suffix='.gif', delete=False) as tmp_gif_file:
                output_gif_path = tmp_gif_file.name

            try:
                timelapse_result = geemap.goes_fire_timelapse(
                    roi=region,
                    out_gif=output_gif_path,
                    start_date=start_date_str,
                    end_date=end_date_str,
                    data='GOES-19',
                    scan='full_disk',
                    dimensions=600,
                    framesPerSecond=6,
                    date_format='YYYY-MM-dd HH:mm',
                    add_progress_bar=False,
                    mp4=False
                )

                st.session_state['generated_gif_path'] = output_gif_path
                st.success('Timelapse generated!')
                st.rerun() # Updated from experimental_rerun()

            except Exception as e:
                st.error(f"Error generating timelapse: {e}")
                if os.path.exists(output_gif_path):
                    os.remove(output_gif_path)

# --- Display Result ---
if 'generated_gif_path' in st.session_state and os.path.exists(st.session_state['generated_gif_path']):
    st.divider()
    st.subheader('Generated Timelapse GIF')
    st.image(st.session_state['generated_gif_path'], use_container_width=False)

    with open(st.session_state['generated_gif_path'], 'rb') as f:
        st.download_button(
            label="Download GIF",
            data=f,
            file_name=f"goes_fire_{start_date_str}.gif",
            mime="image/gif"
        )
