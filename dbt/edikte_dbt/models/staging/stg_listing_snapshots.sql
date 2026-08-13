SELECT
    snapshot_id,
    aktenzeichen,
    source_url,
    CAST(scraped_at AS TIMESTAMP) AS scraped_at,
    dienststelle,
    ort,
    plz,
    kategorie,
    status_title,
    schaetzwert,
    geringstes_gebot,
    meistbot,
    CAST(bekannt_gemacht_am AS DATE) AS bekannt_gemacht_am
FROM {{ source('raw', 'raw_listing_snapshots') }}