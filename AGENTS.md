# GOES Fire Timelapse App

Single-file Streamlit app generating fire timelapse GIFs from GOES-19 satellite data via Google Earth Engine and geemap.

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

The app uses `ee.ServiceAccountCredentials()` directly (not `geemap.ee_initialize()` which is unsuitable for Streamlit).

## Known Issues

- `start_date_str` is not persisted in session state, so the download filename may be wrong on rerun
- `st.rerun()` before GIF file write completes can cause display issues
