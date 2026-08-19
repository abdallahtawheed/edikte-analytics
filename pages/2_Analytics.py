# pages/2_Analytics.py
import streamlit as st
import streamlit.components.v1 as components

st.subheader("Analytics Dashboard")
st.set_page_config(layout="wide")
LOOKER_EMBED_URL = "https://datastudio.google.com/embed/reporting/224edf4a-e616-44c9-a186-d3e40e9b69d4/page/2VW6F"
components.iframe(LOOKER_EMBED_URL, height=700, scrolling=True)

