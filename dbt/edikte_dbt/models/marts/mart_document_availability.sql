-- NOTE: joins by aktenzeichen, so multi-object cases (see BLNr open item in
-- DECISIONS.md) will show combined document counts across all objects under
-- that case, not per-object. Acceptable approximation for now.

WITH doc_counts AS (
    SELECT
        aktenzeichen,
        COUNTIF(doc_type = 'Foto(s)') AS photo_count,
        COUNTIF(doc_type = 'Grundriss(e)') AS floorplan_count,
        COUNTIF(doc_type = 'Lageplan') AS siteplan_count,
        COUNTIF(doc_type = 'Langgutachten') AS full_report_count,
        COUNTIF(doc_type = 'Kurzgutachten') AS short_report_count,
        COUNT(*) AS total_documents
    FROM {{ ref('stg_listing_documents') }}
    GROUP BY aktenzeichen
)

SELECT
    s.aktenzeichen,
    s.source_url,
    s.status_title,
    s.kategorie,
    s.ort,
    COALESCE(d.photo_count, 0) AS photo_count,
    COALESCE(d.floorplan_count, 0) AS floorplan_count,
    COALESCE(d.siteplan_count, 0) AS siteplan_count,
    COALESCE(d.full_report_count, 0) AS full_report_count,
    COALESCE(d.short_report_count, 0) AS short_report_count,
    COALESCE(d.total_documents, 0) AS total_documents,

    -- Three distinct, non-overlapping photo-visibility states, since the
    -- standalone Foto(s) field and embedded Langgutachten photos are
    -- genuinely different in accessibility: standalone photos are visible
    -- immediately, report-only photos require opening and reading a PDF.
    CASE
        WHEN COALESCE(d.photo_count, 0) > 0
            THEN 'standalone_photos'
        WHEN COALESCE(d.photo_count, 0) = 0 AND COALESCE(d.full_report_count, 0) > 0
            THEN 'report_only'
        ELSE 'no_photos_found'
    END AS photo_availability

FROM {{ ref('mart_current_objects') }} s
LEFT JOIN doc_counts d ON d.aktenzeichen = s.aktenzeichen