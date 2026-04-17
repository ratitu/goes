# GOES Fire Timelapse App

Single-file Streamlit app generating fire timelapse GIFs from GOES satellite data via Google Earth Engine and geemap.

## Running

```bash
streamlit run streamlit_app.py
```

Devcontainer auto-starts on port 8501 with `--server.enableCORS false --server.enableXsrfProtection false`.

## Dependencies

- `streamlit>=1.30.0`
- `earthengine-api>=0.1.390`
- `geemap>=0.30.0`

## Earth Engine Setup

Secrets required in `.streamlit/secrets.toml`:
```toml
[ee]
client_email = "..."
private_key = "..."
```

Project name: `ee-passeionamatamapas`

The app uses `ee.ServiceAccountCredentials()` directly (not `geemap.ee_initialize()` which is unsuitable for Streamlit). Initialization is cached via `@st.cache_resource`.

## Satellite Data

- GOES-16: Dec 18, 2017 to Apr 7, 2025
- GOES-19: Apr 8, 2025 onwards

App auto-selects the correct satellite based on start date.

## Known Issues

- `st.rerun()` before GIF file write completes can cause display issues
