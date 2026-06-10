# uber_client.py — Uber OAuth2 + Supplier Performance Data API
# Handles: token fetch, org discovery, metrics query, DataFrame conversion

import time
import requests
import pandas as pd
import streamlit as st

# ── CONSTANTS ─────────────────────────────────────────────────────────────────
TOKEN_URL    = "https://auth.uber.com/oauth/v2/token"
ORGS_URL     = "https://api.uber.com/v1/vehicle-suppliers/orgs"
METRICS_URL  = "https://api.uber.com/v1/vehicle-suppliers/analytics-data/query"
SCOPE        =  "solutions.suppliers.metrics.read vehicle_suppliers.organizations.read"

# Token cache — persists for the Streamlit session
# Uber tokens with 30-day TTL: we refresh 60s before expiry to be safe
_TOKEN_CACHE = {"access_token": None, "expires_at": 0}


class UberAPIError(Exception):
    """Raised for any Uber API failure — caught in app.py for user-friendly display."""
    pass


# ── STEP 1 & 2: AUTHENTICATION ────────────────────────────────────────────────
def _get_access_token() -> str:
    """
    Returns a valid OAuth2 access token using Client Credentials flow.
    Caches the token in memory for the session lifetime.
    Reads credentials from Streamlit Secrets (never hardcoded).
    """
    now = time.time()

    # Return cached token if still valid (with 60s buffer)
    if _TOKEN_CACHE["access_token"] and now < _TOKEN_CACHE["expires_at"] - 60:
        return _TOKEN_CACHE["access_token"]

    # Read from Streamlit Secrets
    try:
        client_id     = st.secrets["UBER_CLIENT_ID"]
        client_secret = st.secrets["UBER_CLIENT_SECRET"]
    except KeyError as e:
        raise UberAPIError(
            f"Missing secret: {e}. "
            "Add UBER_CLIENT_ID and UBER_CLIENT_SECRET to Streamlit Secrets."
        )

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type":    "client_credentials",
            "client_id":     client_id,
            "client_secret": client_secret,
            "scope":         SCOPE,
        },
        timeout=15,
    )

    if resp.status_code != 200:
        raise UberAPIError(
            f"Token request failed [{resp.status_code}]: {resp.text}"
        )

    token_data = resp.json()
    access_token = token_data.get("access_token")

    if not access_token:
        raise UberAPIError(f"No access_token in response: {token_data}")

    # Cache with expiry (Uber returns expires_in in seconds)
    expires_in = token_data.get("expires_in", 2592000)  # default 30 days
    _TOKEN_CACHE["access_token"] = access_token
    _TOKEN_CACHE["expires_at"]   = now + expires_in

    return access_token


# ── STEP 3: GET ORGANISATION IDs ──────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _get_org_ids() -> list[str]:
    """
    Fetches all organisation IDs accessible to this application.
    Cached for 1 hour — org list rarely changes.
    Returns a list of org_id strings.
    """
    token = _get_access_token()

    resp = requests.get(
        ORGS_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )

    if resp.status_code != 200:
        raise UberAPIError(
            f"Failed to fetch orgs [{resp.status_code}]: {resp.text}"
        )

    data = resp.json()

    # Response shape: {"orgs": [{"org_id": "...", "name": "..."}, ...]}
    orgs = data.get("orgs", [])
    if not orgs:
        raise UberAPIError(
            "No organisations returned. Check your app has fleet access in "
            "the Uber Developer Dashboard."
        )

    return [o["org_id"] for o in orgs]


# ── STEP 4 & 5: QUERY METRICS + BUILD DATAFRAME ───────────────────────────────
def _query_metrics(org_id: str, start_date: str, end_date: str) -> list[dict]:
    """
    Calls /v1/vehicle-suppliers/analytics-data/query for one org.
    Returns a list of raw driver metric dicts.

    start_date / end_date format: "YYYY-MM-DD"
    """
    token = _get_access_token()

    payload = {
        "org_id":     org_id,
        "start_date": start_date,
        "end_date":   end_date,
        "metrics": [
            "hours_online",
            "hours_on_trip",
            "total_trips",
        ],
        # granularity SUMMARY = one row per driver for the whole period
        "granularity": "SUMMARY",
    }

    resp = requests.post(
        METRICS_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
        json=payload,
        timeout=30,
    )

    if resp.status_code != 200:
        raise UberAPIError(
            f"Metrics query failed for org {org_id} [{resp.status_code}]: {resp.text}"
        )

    data = resp.json()

    # ── IMPORTANT: adjust the key names below to match Uber's actual response ──
    # Run the app once and check the st.expander("Raw API response") output
    # in admin view to see the exact shape, then update these keys if needed.
    #
    # Expected shape (adjust if different):
    # {
    #   "data": [
    #     {
    #       "driver_uuid": "...",
    #       "driver_name": "John Smith",   ← or "name", "driver_first_name" etc
    #       "hours_online": 42.5,
    #       "hours_on_trip": 30.1,
    #       "total_trips": 87
    #     },
    #     ...
    #   ]
    # }
    return data.get("data", [])


def _records_to_dataframe(records: list[dict]) -> pd.DataFrame:
    """
    Converts raw API records to a normalised DataFrame.

    Column mapping from API → app:
        driver_name   → Driver
        hours_online  → Hours Online
        hours_on_trip → Hours on Trip
        total_trips   → Total Trips

    Add extra mappings here when new metrics (earnings, AR, CR) are added.
    All values are cast to their correct types here — downstream code can
    assume clean data.
    """
    if not records:
        raise UberAPIError(
            "API returned 0 driver records for this date range. "
            "Try a wider date range or check that drivers were active."
        )

    rows = []
    for r in records:
        # Try common name field variants — update once you've seen real response
        name = (
            r.get("driver_name")
            or r.get("name")
            or f"{r.get('driver_first_name', '')} {r.get('driver_last_name', '')}".strip()
            or r.get("driver_uuid", "Unknown")
        )

        rows.append({
            "Driver":       str(name).strip(),
            "Hours Online": round(float(r.get("hours_online",  0)), 2),
            "Hours on Trip":round(float(r.get("hours_on_trip", 0)), 2),
            "Total Trips":  int(float(r.get("total_trips",     0))),
        })

    df = pd.DataFrame(rows)

    # Remove blank/unknown drivers
    df = df[df["Driver"].str.len() > 0].reset_index(drop=True)

    return df


# ── STEP 6: PUBLIC ENTRY POINT ────────────────────────────────────────────────
def fetch_live_driver_data(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Main function called by app.py.
    Fetches data for ALL orgs and returns a single combined DataFrame.

    Args:
        start_date: "YYYY-MM-DD"
        end_date:   "YYYY-MM-DD"

    Returns:
        pd.DataFrame with columns:
            Driver, Hours Online, Hours on Trip, Total Trips

    Raises:
        UberAPIError on any failure (caught in app.py)
    """
    org_ids = _get_org_ids()

    all_records = []
    for org_id in org_ids:
        records = _query_metrics(org_id, start_date, end_date)
        all_records.extend(records)

    df = _records_to_dataframe(all_records)

    # Deduplicate if a driver appears in multiple orgs
    df = (
        df.groupby("Driver", as_index=False)
          .agg({
              "Hours Online":  "sum",
              "Hours on Trip": "sum",
              "Total Trips":   "sum",
          })
    )

    return df