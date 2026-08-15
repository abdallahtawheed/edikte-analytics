import streamlit as st
import pandas as pd
from sqlalchemy import text
from scraper.persist import engine

import sys
sys.path.insert(0, "src")
import pydeck as pdk



from parser.parse import parse_de_number
from scraper.state_machine import classify_status
from parser.flags import FLAG_CATEGORIES

@st.cache_data(ttl=300)
def load_objects():
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                oc.snapshot_id, oc.aktenzeichen, oc.source_url, oc.status_title, oc.kategorie,
                oc.ort, oc.plz, oc.dienststelle, oc.scraped_at, oc.bekannt_gemacht_am,
                oc.latitude, oc.longitude, oc.objektgroesse_m2, oc.blnr,
                oc.schaetzwert, oc.geringstes_gebot, oc.meistbot,
                oc.extra->>'Liegenschaftsadresse' as adresse,
                (SELECT count(*) FROM listing_flags f WHERE f.snapshot_id = oc.snapshot_id) as flag_count
            FROM objects_current oc
        """))
        df = pd.DataFrame(result.fetchall(), columns=result.keys())

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["objektgroesse_m2"] = pd.to_numeric(df["objektgroesse_m2"], errors="coerce")
    df["is_bundled"] = df["blnr"].fillna("").str.contains(",")
    df["schaetzwert"] = pd.to_numeric(df["schaetzwert"], errors="coerce")
    df["geringstes_gebot"] = pd.to_numeric(df["geringstes_gebot"], errors="coerce")
    df["meistbot"] = pd.to_numeric(df["meistbot"], errors="coerce")
    df["status"] = df["status_title"].apply(classify_status)

    return df