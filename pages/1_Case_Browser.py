# pages/1_Case_Browser.py
import sys
sys.path.insert(0, "src")  # adjust based on actual relative path from pages/ to src/
import streamlit as st
import pandas as pd
from sqlalchemy import text
from scraper.persist import engine

from streamlit_utils import load_objects

filtered = load_objects()

st.title("Case Browser")

cases = filtered.groupby("aktenzeichen").agg(
    object_count=("source_url", "count"),
    ort=("ort", "first"),
    kategorie=("kategorie", "first"),
).reset_index().sort_values("object_count", ascending=False)

selected_case = st.selectbox(
    "Select a case (Aktenzeichen)",
    cases["aktenzeichen"],
    format_func=lambda ak: f"{ak} ({cases[cases['aktenzeichen']==ak]['object_count'].values[0]} object(s))"
)

if selected_case:
    case_objects = filtered[filtered["aktenzeichen"] == selected_case]
    st.write(f"**{len(case_objects)} object(s) under {selected_case}:**")
    for _, obj in case_objects.iterrows():
        label = f"BLNr {obj['blnr'] or '—'} — {obj['status_title']}"
        with st.expander(label):
            st.write(f"**Address:** {obj['adresse']}")
            st.write(f"**Size:** {obj['objektgroesse_m2']} m²")
            st.markdown(f"[Open source page]({obj['source_url']})")