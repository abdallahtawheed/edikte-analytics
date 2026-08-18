# streamlit_app.py, repo root
import sys
sys.path.insert(0, "src")
import pydeck as pdk
import streamlit as st
import pandas as pd
from sqlalchemy import text
from scraper.persist import engine
from parser.parse import parse_de_number
from scraper.state_machine import classify_status
from parser.flags import FLAG_CATEGORIES


st.set_page_config(page_title="edikte-analytics", layout="wide")

import streamlit.components.v1 as components

components.html("""
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-077L619PDR"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-NP2WS69SYR');
</script>
""", height=0)

st.title("Austrian Judicial Auction Listings")



from streamlit_utils import load_objects


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


st.sidebar.subheader("Geringstes Gebot (EUR)")
col1, col2 = st.sidebar.columns(2)
price_min = col1.number_input("Min", min_value=0.0, value=0.0, step=1000.0)
price_max = col2.number_input("Max", min_value=0.0, value=float(df["geringstes_gebot"].max() or 0), step=1000.0)
filtered = filtered[
    filtered["geringstes_gebot"].isna() | filtered["geringstes_gebot"].between(price_min, price_max)
]

st.sidebar.subheader("Size (m²)")
col3, col4 = st.sidebar.columns(2)
size_min = col3.number_input("Min m²", min_value=0.0, value=0.0, step=5.0)
size_max = col4.number_input("Max m²", min_value=0.0, value=float(df["objektgroesse_m2"].max() or 0), step=5.0)
filtered = filtered[
    filtered["objektgroesse_m2"].isna() | filtered["objektgroesse_m2"].between(size_min, size_max)
]
st.sidebar.markdown(f"**{len(filtered)}** of {len(df)} objects shown")


# table
st.subheader("Listings")
event = st.dataframe(
    filtered[[
        "aktenzeichen", "status", "kategorie", "ort", "adresse",
        "blnr", "is_bundled", "objektgroesse_m2",
        "schaetzwert", "geringstes_gebot", "meistbot",
        "bekannt_gemacht_am", "scraped_at", "dienststelle", "source_url"
    ]],
    column_config={
        "blnr": st.column_config.TextColumn("BLNr"),
        "is_bundled": st.column_config.CheckboxColumn("Multiple units?"),
        "objektgroesse_m2": st.column_config.NumberColumn("Size (m²)", format="%.1f"),
        "schaetzwert": st.column_config.NumberColumn("Schätzwert", format="€%.2f"),
        "geringstes_gebot": st.column_config.NumberColumn("Geringstes Gebot", format="€%.2f"),
        "meistbot": st.column_config.NumberColumn("Meistbot", format="€%.2f"),
        "bekannt_gemacht_am": st.column_config.DateColumn("Published"),
        "scraped_at": st.column_config.DatetimeColumn("Last scraped"),
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
        + map_data["geringstes_gebot"].fillna(0).astype(str) + " EUR")

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


if selected_row is not None:
    with engine.connect() as conn:
        photos = conn.execute(
            text("""
                SELECT storage_path FROM listing_documents
                WHERE aktenzeichen = :ak AND doc_type = 'Foto(s)'
            """),
            {"ak": selected_row["aktenzeichen"]},
        ).fetchall()

    if photos:
        st.subheader("Photos")
        cols = st.columns(min(len(photos), 4))
        for i, photo in enumerate(photos):
            with cols[i % 4]:
                st.image(photo.storage_path, use_container_width=True)


# --- Detail view ---
st.subheader("Object detail")

default_index = 0
if selected_row is not None:
    aktenzeichen_list = list(filtered["aktenzeichen"].unique())
    if selected_row["aktenzeichen"] in aktenzeichen_list:
        default_index = aktenzeichen_list.index(selected_row["aktenzeichen"])

selected_aktenzeichen = st.selectbox(
    "Select an Aktenzeichen for history",
    filtered["aktenzeichen"].unique(),
    index=default_index,
)
if selected_aktenzeichen:
    with engine.connect() as conn:
        history = conn.execute(
            text("""
                SELECT scraped_at, status_title, schaetzwert, geringstes_gebot, meistbot, source_url
                FROM listing_snapshots
                WHERE aktenzeichen = :ak AND source_url IS NOT NULL
                ORDER BY scraped_at DESC
            """),
            {"ak": selected_aktenzeichen},
        )
        hist_df = pd.DataFrame(history.fetchall(), columns=history.keys())
    st.write(f"Full history for **{selected_aktenzeichen}** ({len(hist_df)} snapshot(s) across all its objects):")
    st.dataframe(hist_df, use_container_width=True)


if selected_row is not None:
    with engine.connect() as conn:
        flag_rows = conn.execute(
            text("""
                SELECT category, flag_type, matched_keyword, source_excerpt
                FROM listing_flags
                WHERE snapshot_id = :sid
                ORDER BY category, flag_type
            """),
            {"sid": int(selected_row["snapshot_id"])},
        ).fetchall()

    if flag_rows:
        st.warning(f"{len(flag_rows)} potential issue(s) flagged on this listing:")
        current_category = None
        for f in flag_rows:
            if f.category != current_category:
                current_category = f.category
                label = FLAG_CATEGORIES.get(f.category, {}).get("label", f.category)
                st.markdown(f"**{label}**")
            st.write(f"- {f.flag_type}: \"{f.matched_keyword}\" — ...{f.source_excerpt}...")