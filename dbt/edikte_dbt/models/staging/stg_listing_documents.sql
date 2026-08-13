SELECT
    document_id,
    aktenzeichen,
    doc_type,
    storage_path
FROM {{ source('raw', 'raw_listing_documents') }}