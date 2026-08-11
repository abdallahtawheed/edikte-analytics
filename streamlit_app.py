# streamlit_app.py, repo root
import sys
sys.path.insert(0, "src")
import pydeck as pdk
import streamlit as st
import pandas as pd
from sqlalchemy import text
from scraper.persist import engine
from parser.parse import parse_de_number


st.set_page_config(page_title="edikte-analytics", layout="wide")
st.title("Austrian Judicial Auction Listings")


@st.cache_data(ttl=300)
def load_objects():
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                aktenzeichen, source_url, status, status_title, kategorie,
                ort, plz, dienststelle, scraped_at, latitude, longitude,
                extra->>'Schätzwert' as schaetzwert_raw,
                extra->>'Geringstes Gebot' as gebot_raw,
                extra->>'Meistbot' as meistbot_raw,
                extra->>'Liegenschaftsadresse' as adresse
            FROM objects_current
        """))
        df = pd.DataFrame(result.fetchall(), columns=result.keys())

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")

    df["schaetzwert"] = df["schaetzwert_raw"].apply(lambda v: parse_de_number(v) if isinstance(v, str) else None)
    df["gebot"] = df["gebot_raw"].apply(lambda v: parse_de_number(v) if isinstance(v, str) else None)
    df["meistbot"] = df["meistbot_raw"].apply(lambda v: parse_de_number(v) if isinstance(v, str) else None)

    return df

df = load_objects()

# --- Sidebar filters ---
st.sidebar.header("Filters")

categories = sorted(df["kategorie"].dropna().unique())
selected_categories = st.sidebar.multiselect("Category", categories)

statuses = sorted(df["status"].dropna().unique())
selected_statuses = st.sidebar.multiselect("Status", statuses, default=["Versteigerung"])

search_ort = st.sidebar.text_input("Ort contains")

filtered = df.copy()
if selected_categories:
    filtered = filtered[filtered["kategorie"].isin(selected_categories)]
if selected_statuses:
    filtered = filtered[filtered["status"].isin(selected_statuses)]
if search_ort:
    filtered = filtered[filtered["ort"].str.contains(search_ort, case=False, na=False)]


st.sidebar.subheader("Price range (Geringstes Gebot)")
valid_gebot = df["gebot"].dropna()
if not valid_gebot.empty:
    price_min, price_max = st.sidebar.slider(
        "EUR",
        min_value=float(valid_gebot.min()),
        max_value=float(valid_gebot.max()),
        value=(float(valid_gebot.min()), float(valid_gebot.max())),
    )
    filtered = filtered[
        filtered["gebot"].isna() | filtered["gebot"].between(price_min, price_max)
    ]

st.sidebar.markdown(f"**{len(filtered)}** of {len(df)} objects shown")


# table
st.subheader("Listings")
event = st.dataframe(
    filtered[[
        "aktenzeichen", "status", "kategorie", "ort", "adresse",
        "schaetzwert", "gebot", "meistbot", "dienststelle", "source_url"
    ]],
    column_config={
        "schaetzwert": st.column_config.NumberColumn("Schätzwert", format="€%.2f"),
        "gebot": st.column_config.NumberColumn("Geringstes Gebot", format="€%.2f"),
        "meistbot": st.column_config.NumberColumn("Meistbot", format="€%.2f"),
        "source_url": st.column_config.LinkColumn("Link", display_text="Open"),
    },
    use_container_width=True,
    on_select="rerun",
    selection_mode="single-row",
)

selected_row = None
if event.selection and event.selection["rows"]:
    selected_idx = event.selection["rows"][0]
    selected_row = filtered.iloc[selected_idx]

# --- Map ---

st.subheader("Map")
map_data = filtered.dropna(subset=["latitude", "longitude"]).copy()

if not map_data.empty:
    map_data["tooltip_text"] = (
        map_data["status_title"].fillna("") + " — "
        + map_data["ort"].fillna("") + "\n"
        + map_data["gebot_raw"].fillna("no price listed")
    )

    layers = [
        pdk.Layer(
            "ScatterplotLayer",
            data=map_data,
            get_position=["longitude", "latitude"],
            get_radius=500,
            radius_min_pixels=4,
            radius_max_pixels=10,
            get_fill_color=[220, 40, 20, 200],
            pickable=True,
            auto_highlight=True,
        )
    ]

    if selected_row is not None and pd.notna(selected_row["latitude"]):
        highlight_df = pd.DataFrame([selected_row])
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=highlight_df,
                get_position=["longitude", "latitude"],
                get_radius=1200,
                radius_min_pixels=6,
                radius_max_pixels=14,
                get_fill_color=[30, 120, 255, 220],
                pickable=False,
            )
        )
        view_state = pdk.ViewState(latitude=selected_row["latitude"], longitude=selected_row["longitude"], zoom=12)
    else:
        view_state = pdk.ViewState(latitude=map_data["latitude"].mean(), longitude=map_data["longitude"].mean(), zoom=6)

    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view_state, tooltip={"text": "{tooltip_text}"}, map_style="light"))
else:
    st.info("No geocoded objects match the current filters.")


# --- Detail view ---
st.subheader("Object detail")
selected_aktenzeichen = st.selectbox("Select an Aktenzeichen for history", filtered["aktenzeichen"].unique())

if selected_aktenzeichen:
    with engine.connect() as conn:
        history = conn.execute(
            text("""
                SELECT scraped_at, status_title, extra->>'Schätzwert' as schaetzwert,
                    extra->>'Geringstes Gebot' as gebot, source_url
                FROM listing_snapshots
                WHERE aktenzeichen = :ak AND source_url IS NOT NULL
                ORDER BY scraped_at DESC
            """),
            {"ak": selected_aktenzeichen},
        )
        hist_df = pd.DataFrame(history.fetchall(), columns=history.keys())
    st.write(f"Full history for **{selected_aktenzeichen}** ({len(hist_df)} snapshot(s) across all its objects):")
    st.dataframe(hist_df, use_container_width=True)