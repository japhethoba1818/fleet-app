# app.py — SparklingBlu Fleet Management System
# Phase 1: Live Uber API data | Views: admin | drivers | fleet | team

import streamlit as st
import pandas as pd
from datetime import datetime
from engine import get_week_progress
from teams import TEAMS, match_drivers_to_teams
from storage import save_fleet_data, load_fleet_data, is_storage_configured
from uber_client import fetch_live_driver_data, UberAPIError

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SparklingBlu — Driver Performance",
    page_icon="🚛",
    layout="wide"
)

st.markdown("""
<style>
[data-testid="stAppViewContainer"],[data-testid="stMain"],.main{background:#f0f4f8!important;}
[data-testid="stAppViewContainer"] p,[data-testid="stAppViewContainer"] span,
[data-testid="stAppViewContainer"] div,[data-testid="stAppViewContainer"] label,
[data-testid="stMarkdownContainer"] p,[data-testdata="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] li{color:#0f2027!important;}
h1,h2,h3{color:#0f2027!important;}
[data-testid="stMetric"]{background:white!important;border-radius:14px!important;
  padding:18px 22px!important;text-align:center!important;
  box-shadow:0 2px 10px rgba(0,0,0,.10)!important;}
[data-testid="stMetricLabel"]>div{font-size:12px!important;font-weight:800!important;
  color:#203a43!important;text-transform:uppercase!important;letter-spacing:.6px!important;}
[data-testid="stMetricValue"]>div{font-size:32px!important;font-weight:900!important;
  color:#0f2027!important;}
[data-testid="stAlert"] p,[data-testid="stAlert"] span{color:#0f2027!important;}
[data-testid="stTextInput"] input{background:white!important;color:#0f2027!important;
  border:1.5px solid #2c5364!important;border-radius:8px!important;}
[data-testid="stTextInput"] label,[data-testid="stNumberInput"] label,
[data-testid="stSelectbox"] label,[data-testid="stFileUploader"] label{
  color:#0f2027!important;font-weight:600!important;}
[data-testid="stCaptionContainer"] p{color:#555!important;font-size:13px!important;}
[data-testid="stDataFrame"]{background:white!important;border-radius:10px!important;}
[data-testid="stExpander"] summary p{color:#0f2027!important;font-weight:600!important;}
</style>
""", unsafe_allow_html=True)

# ── CONSTANTS ─────────────────────────────────────────────────────────────────
BASE_URL = "https://fleet-app-v25cphks3psbb94zeedjfq.streamlit.app"

# ── HELPERS ───────────────────────────────────────────────────────────────────
def date_only():
    return datetime.now().strftime("%d %b %Y")

def make_link(view, team=None):
    if team:
        return f"{BASE_URL}/?view={view}&team={team.replace(' ', '+')}"
    return f"{BASE_URL}/?view={view}"

def banner_html(text):
    return (
        f'<div style="background:linear-gradient(90deg,#0f2027,#203a43,#2c5364);'
        f'color:white;padding:14px 22px;border-radius:12px;margin-bottom:18px;font-size:14px;">'
        f'{text}</div>'
    )

def insight_html(text):
    return (
        f'<div style="background:white;border-radius:12px;padding:14px 18px;'
        f'box-shadow:0 2px 8px rgba(0,0,0,.07);margin-bottom:10px;'
        f'font-size:15px;color:#0f2027;">{text}</div>'
    )

def link_html(url):
    return (
        f'<div style="background:#0f2027;border-left:5px solid #25D366;'
        f'border-radius:8px;padding:12px 16px;font-family:monospace;'
        f'font-size:13px;word-break:break-all;color:#25D366;'
        f'margin-top:6px;display:block;letter-spacing:0.3px;">{url}</div>'
    )

def sbv_bar_html(line1, line2=""):
    return (
        f'<div style="background:white;border-radius:12px;padding:16px 22px;'
        f'border-left:5px solid #2c5364;margin-bottom:16px;color:#0f2027;">'
        f'{line1}'
        + (f'<br><span style="color:#0f2027;font-size:13px;">{line2}</span>' if line2 else "")
        + '</div>'
    )

# ── PROCESS API DATAFRAME ─────────────────────────────────────────────────────
def process_api_dataframe(raw_df):
    """
    Takes a DataFrame from uber_client.fetch_live_driver_data() and enriches it
    with team assignments and placeholder fields for future scoring.

    Phase 1 columns expected from API:
        Driver, Hours Online, Hours on Trip, Total Trips

    Phase 1 columns added here:
        Team, Score (0), Status ('—'), Coaching ('—')

    Designed so that when engine.py is updated, Score/Status/Coaching can be
    computed properly by passing the df rows through calculate_performance_score()
    and get_coaching_message() — no structural changes needed.
    """
    df = raw_df.copy()

    # Team assignment (reuses existing teams.py logic)
    df = match_drivers_to_teams(df)

    # Phase 1 placeholders — replaced when engine.py is updated
    df["Score"]    = 0
    df["Status"]   = "—"
    df["Coaching"] = "Scoring coming soon."

    return df

# ── ROUTE ─────────────────────────────────────────────────────────────────────
params     = st.query_params
view       = params.get("view", "admin")
team_param = params.get("team", None)
week_info  = get_week_progress()


# ════════════════════════════════════════════════════════
# ADMIN VIEW
# ════════════════════════════════════════════════════════
if view == "admin":
    st.markdown("# 🚛 SparklingBlu — Admin Panel")
    st.caption("Fetch live Uber data → review → publish links")

    if not is_storage_configured():
        st.warning("⚙️ One-time GitHub Gist setup needed. See Setup Guide below.")

    st.markdown(banner_html(
        f'Today: <strong style="color:white;">{week_info["day_name"]}, {date_only()}</strong>'
        f' &nbsp;|&nbsp; Week: <strong style="color:white;">'
        f'{round(week_info["progress"] * 100, 1)}%</strong> complete'
        f' &nbsp;|&nbsp; <strong style="color:white;">'
        f'{week_info["days_left"]} day(s)</strong> left'
        f' &nbsp;|&nbsp; Shift: <strong style="color:white;">5:00am – 7:30pm</strong>'
    ), unsafe_allow_html=True)

    # ── Date range selector ───────────────────────────────
    st.markdown("### 📅 Select Reporting Period")
    col_d1, col_d2, col_wl = st.columns(3)
    with col_d1:
        start_date = st.date_input("Start date", value=datetime.now().date())
    with col_d2:
        end_date = st.date_input("End date", value=datetime.now().date())
    with col_wl:
        week_label = st.text_input("Week label", value=date_only())

    if start_date > end_date:
        st.error("Start date must be before or equal to end date.")
        st.stop()

    # ── Fetch live data ───────────────────────────────────
    st.markdown("### 🔄 Live Data")

    fetch_col, status_col = st.columns([2, 3])
    with fetch_col:
        fetch_btn = st.button(
            "🔄 Fetch Live Driver Data",
            type="primary",
            use_container_width=True
        )

    if fetch_btn:
        with st.spinner("Connecting to Uber API…"):
            try:
                raw_df = fetch_live_driver_data(
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                )
                st.session_state["api_df"]     = raw_df
                st.session_state["api_fetched"] = True
                st.session_state["api_error"]   = None
            except UberAPIError as e:
                st.session_state["api_error"]   = str(e)
                st.session_state["api_fetched"] = False
            except Exception as e:
                st.session_state["api_error"]   = f"Unexpected error: {e}"
                st.session_state["api_fetched"] = False

    # Show persistent error if fetch failed
    if st.session_state.get("api_error"):
        st.error(f"❌ API Error: {st.session_state['api_error']}")
        with st.expander("🛠️ Troubleshooting"):
            st.markdown("""
- Check that `UBER_CLIENT_ID` and `UBER_CLIENT_SECRET` are set in Streamlit Secrets
- Confirm your Uber app is approved for `solutions.suppliers.metrics.read`
- Check that your org has active drivers in the selected date range
- Review Uber Developer Dashboard for any app status issues
            """)
        st.stop()

    # No data fetched yet
    if not st.session_state.get("api_fetched"):
        st.info("Select a date range and click **Fetch Live Driver Data** to load driver metrics.")
        st.stop()

    # ── Data loaded — process and display ────────────────
    raw_df = st.session_state["api_df"]
    df     = process_api_dataframe(raw_df)

    st.success(f"✅ Loaded **{len(df)} drivers** from Uber API")

    # ── Fleet overview metrics ────────────────────────────
    st.subheader("Fleet Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Drivers",    len(df))

    avg_hours = round(df["Hours Online"].astype(float).mean(), 1) if "Hours Online" in df.columns else "—"
    avg_trips = round(df["Total Trips"].astype(float).mean(), 1) if "Total Trips"  in df.columns else "—"
    total_trips = int(df["Total Trips"].astype(float).sum())      if "Total Trips"  in df.columns else "—"

    c2.metric("Avg Hours Online", f"{avg_hours}h")
    c3.metric("Avg Trips",        avg_trips)
    c4.metric("Total Trips",      total_trips)

    st.divider()

    # ── Team breakdown ────────────────────────────────────
    st.subheader("Team Breakdown")
    team_cols = st.columns(len(TEAMS))
    for i, (team_name, info) in enumerate(TEAMS.items()):
        t_df = df[df["Team"] == team_name]
        team_cols[i].metric(
            team_name,
            f"{len(t_df)} drivers",
            f"Leader: {info['leader']}"
        )

    st.divider()

    # ── Preview table ─────────────────────────────────────
    with st.expander("📋 Preview Full Driver Table", expanded=True):
        show_cols = ["Driver", "Team", "Hours Online", "Hours on Trip", "Total Trips"]
        show_cols = [c for c in show_cols if c in df.columns]
        preview   = df[show_cols].copy()
        st.dataframe(
            preview.sort_values("Hours Online", ascending=False)
                   .reset_index(drop=True),
            use_container_width=True,
            hide_index=True
        )

    st.divider()

    # ── Save & publish ────────────────────────────────────
    encode_cols = ["Driver", "Team", "Hours Online", "Hours on Trip",
                   "Total Trips", "Score", "Status", "Coaching"]
    encode_cols = [c for c in encode_cols if c in df.columns]

    payload = {
        "fleet":       df[encode_cols].to_dict(orient="records"),
        "week_info":   week_info,
        "week_label":  week_label,
        "updated_at":  date_only(),
        "start_date":  start_date.isoformat(),
        "end_date":    end_date.isoformat(),
        "total_drivers": len(df),
    }

    st.subheader("Publish & Share Links")

    if is_storage_configured():
        if st.button("📤 Publish Data & Update All Links", type="primary",
                     use_container_width=True):
            with st.spinner("Saving to GitHub Gist…"):
                ok = save_fleet_data(payload)
            if ok:
                st.success("✅ Data published! All links now show the latest data.")
                # Clear fetched state so admin can fetch fresh next time
                st.session_state["api_fetched"] = False
                st.session_state["api_df"]      = None
            else:
                st.error("Failed. Check GITHUB_TOKEN and GIST_ID in Streamlit Secrets.")
    else:
        st.info("Complete the one-time setup below to enable auto-updating links.")

    st.divider()

    # ── Display links ─────────────────────────────────────
    st.markdown("#### Your Permanent Links")
    st.caption("These never change. Drivers bookmark once — they always see the latest data.")

    l1, l2 = st.columns(2)
    with l1:
        st.markdown("**📱 Drivers Link** — share in your whole driver group")
        st.markdown(link_html(make_link("drivers")), unsafe_allow_html=True)
    with l2:
        st.markdown("**📊 Management Link** — share with management")
        st.markdown(link_html(make_link("fleet")), unsafe_allow_html=True)

    st.markdown("**👥 Team Links** — share each in the team's WhatsApp group")
    t_cols = st.columns(len(TEAMS))
    for i, (team_name, info) in enumerate(TEAMS.items()):
        with t_cols[i]:
            st.markdown(f"**{team_name}**")
            st.caption(f"Leader: {info['leader']}")
            st.markdown(link_html(make_link("team", team_name)), unsafe_allow_html=True)

    st.divider()

    with st.expander("⚙️ One-Time Setup Guide (5 minutes)"):
        st.markdown("""
**Step 1 — Get a GitHub Token**
1. Go to 👉 https://github.com/settings/tokens
2. Click **Generate new token (classic)**
3. Name: `fleet-app` | Tick: `gist` only | Click **Generate token**
4. Copy the token immediately

**Step 2 — Create a Gist**
1. Go to 👉 https://gist.github.com
2. Filename: `fleet_data.json` | Content: `{}` | Click **Create secret gist**
3. Copy the ID from the URL (the long string after your username)

**Step 3 — Add to Streamlit Secrets**
1. Go to https://share.streamlit.io → your app → Settings → Secrets
2. Paste:
```toml
GITHUB_TOKEN        = "ghp_yourTokenHere"
GIST_ID             = "yourGistIdHere"
UBER_CLIENT_ID      = "5syO_-GOEpq7Ia_TChV9-0X57VtoRlbK"
UBER_CLIENT_SECRET  = "your_client_secret_here"
```
3. Click Save
        """)


# ════════════════════════════════════════════════════════
# DRIVERS VIEW
# ════════════════════════════════════════════════════════
elif view == "drivers":
    data = load_fleet_data()
    st.markdown("# 🚛 SparklingBlu — Your Weekly Stats")

    if not data:
        st.warning("Stats not available yet. Ask your fleet manager to publish this week's data.")
        st.stop()

    df      = pd.DataFrame(data["fleet"])
    wi      = data.get("week_info", week_info)
    updated = data.get("updated_at", "")

    st.markdown(
        f"*{wi.get('day_name', '—')} check-in  |  "
        f"{wi.get('days_left', '—')} day(s) left  |  Updated: {updated}*"
    )
    st.divider()

    search = st.text_input("Type your name:", placeholder="e.g. John Msosa")
    if not search:
        st.info("Start typing your name above to see your stats.")
        st.stop()

    matches = df[df["Driver"].str.lower().str.contains(search.strip().lower(), na=False)]
    if matches.empty:
        st.warning("No driver found. Try a different spelling.")
        st.stop()
    if len(matches) > 1:
        choice  = st.selectbox("Multiple matches — select your name:", matches["Driver"].tolist())
        matches = matches[matches["Driver"] == choice]

    row = matches.iloc[0]

    st.markdown(f"""
    <div style="background:white;border-radius:16px;padding:28px 32px;
                box-shadow:0 4px 20px rgba(0,0,0,.10);margin-bottom:18px;">
        <h2 style="margin:0 0 4px 0;color:#0f2027;">👤 {row['Driver']}</h2>
        <p style="color:#555;margin:0 0 20px 0;font-size:15px;">
            Team: {row.get('Team', '—')}
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Your Stats This Period")
    k1, k2, k3 = st.columns(3)
    k1.metric("⏱️ Hours Online",   f"{row.get('Hours Online',  '—')}h")
    k2.metric("🚗 Hours on Trip",  f"{row.get('Hours on Trip', '—')}h")
    k3.metric("📦 Total Trips",     str(row.get("Total Trips",  "—")))

    st.divider()
    st.caption(f"SparklingBlu Fleet Team 🚛  |  Updated: {updated}")


# ════════════════════════════════════════════════════════
# FLEET / MANAGEMENT VIEW
# ════════════════════════════════════════════════════════
elif view == "fleet":
    data = load_fleet_data()
    st.markdown("# 📊 SparklingBlu — Fleet Performance")

    if not data:
        st.warning("No data available. Ask the fleet manager to publish this week's stats.")
        st.stop()

    df      = pd.DataFrame(data["fleet"])
    wi      = data.get("week_info", week_info)
    updated = data.get("updated_at", "")

    st.markdown(
        f"*Management Overview  |  {wi.get('day_name', '—')}  |  "
        f"{wi.get('days_left', '—')} day(s) left  |  Updated: {updated}*"
    )
    st.divider()

    # ── Fleet overview metrics ────────────────────────────
    total       = len(df)
    avg_hours   = round(df["Hours Online"].astype(float).mean(), 1) if "Hours Online" in df.columns else "—"
    avg_trips   = round(df["Total Trips"].astype(float).mean(),  1) if "Total Trips"  in df.columns else "—"
    total_trips = int(df["Total Trips"].astype(float).sum())        if "Total Trips"  in df.columns else "—"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Drivers",    total)
    c2.metric("Avg Hours Online", f"{avg_hours}h")
    c3.metric("Avg Trips",        avg_trips)
    c4.metric("Total Trips",      total_trips)

    st.divider()

    # ── Key Insights ──────────────────────────────────────
    st.markdown("### Key Insights")
    i1, i2 = st.columns(2)

    with i1:
        if "Hours Online" in df.columns:
            top_driver = df.loc[df["Hours Online"].astype(float).idxmax(), "Driver"]
            top_hours  = df["Hours Online"].astype(float).max()
            st.markdown(
                insight_html(f"🏆 <strong>Most Hours Online:</strong> {top_driver} — {top_hours}h"),
                unsafe_allow_html=True
            )
            low_hrs = (df["Hours Online"].astype(float) < 10).sum()
            st.markdown(
                insight_html(f"⏱️ <strong>{low_hrs} driver(s)</strong> with fewer than 10h online"),
                unsafe_allow_html=True
            )
    with i2:
        if "Total Trips" in df.columns:
            top_trips_driver = df.loc[df["Total Trips"].astype(float).idxmax(), "Driver"]
            top_trips_val    = int(df["Total Trips"].astype(float).max())
            st.markdown(
                insight_html(f"📦 <strong>Most Trips:</strong> {top_trips_driver} — {top_trips_val} trips"),
                unsafe_allow_html=True
            )
            low_trps = (df["Total Trips"].astype(float) < 5).sum()
            st.markdown(
                insight_html(f"🚗 <strong>{low_trps} driver(s)</strong> with fewer than 5 trips"),
                unsafe_allow_html=True
            )

    st.divider()

    # ── Team compliance ───────────────────────────────────
    st.markdown("### Team Breakdown")
    t_cols = st.columns(len(TEAMS))
    for i, (tn, info) in enumerate(TEAMS.items()):
        t_df      = df[df["Team"] == tn]
        t_n       = len(t_df)
        t_avg_hrs = round(t_df["Hours Online"].astype(float).mean(), 1) if t_n and "Hours Online" in t_df.columns else "—"
        t_cols[i].metric(tn, f"{t_n} drivers", f"Avg {t_avg_hrs}h online")

    st.divider()

    # ── Driver search table ───────────────────────────────
    st.markdown("### Driver Search")
    search  = st.text_input("Search by name or team:", placeholder="e.g. John or Team LB")
    display = df.copy()
    if search:
        mask = (
            display["Driver"].str.lower().str.contains(search.lower(), na=False) |
            display["Team"].str.lower().str.contains(search.lower(), na=False)
        )
        display = display[mask]

    show_cols = ["Driver", "Team", "Hours Online", "Hours on Trip", "Total Trips"]
    show_cols = [c for c in show_cols if c in display.columns]
    st.dataframe(
        display[show_cols].sort_values("Hours Online", ascending=False).reset_index(drop=True),
        use_container_width=True,
        hide_index=True
    )


# ════════════════════════════════════════════════════════
# TEAM VIEW
# ════════════════════════════════════════════════════════
elif view == "team":
    data = load_fleet_data()

    if not data:
        st.warning("No data available. Ask the fleet manager to publish this week's stats.")
        st.stop()

    df      = pd.DataFrame(data["fleet"])
    wi      = data.get("week_info", week_info)
    updated = data.get("updated_at", "")

    selected_team = (
        team_param if team_param and team_param in TEAMS
        else st.selectbox("Select your team:", list(TEAMS.keys()))
    )

    leader  = TEAMS[selected_team]["leader"]
    team_df = df[df["Team"] == selected_team].copy()

    st.markdown(f"# 👥 {selected_team} — Weekly Performance")
    st.markdown(
        f"*Leader: {leader}  |  {wi.get('day_name', '—')}  |  "
        f"{wi.get('days_left', '—')} day(s) left  |  Updated: {updated}*"
    )
    st.divider()

    if team_df.empty:
        st.warning("No drivers found for this team in the current data.")
        st.stop()

    t_total   = len(team_df)
    t_avg_hrs = round(team_df["Hours Online"].astype(float).mean(), 1) if "Hours Online" in team_df.columns else "—"
    t_avg_trp = round(team_df["Total Trips"].astype(float).mean(),  1) if "Total Trips"  in team_df.columns else "—"
    t_best    = (team_df.loc[team_df["Hours Online"].astype(float).idxmax(), "Driver"]
                 if "Hours Online" in team_df.columns else "—")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Team Size",        t_total)
    m2.metric("Avg Hours Online", f"{t_avg_hrs}h")
    m3.metric("Avg Trips",        t_avg_trp)
    m4.metric("Most Hours",       t_best)

    st.divider()

    show_cols = ["Driver", "Hours Online", "Hours on Trip", "Total Trips"]
    show_cols = [c for c in show_cols if c in team_df.columns]
    st.dataframe(
        team_df[show_cols].sort_values("Hours Online", ascending=False).reset_index(drop=True),
        use_container_width=True,
        hide_index=True
    )
    st.caption(f"SparklingBlu Fleet  |  Updated: {updated}")

else:
    st.error("Invalid link. Please ask your fleet manager for the correct link.")