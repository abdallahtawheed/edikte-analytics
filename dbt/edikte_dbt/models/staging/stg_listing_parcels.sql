SELECT
    parcel_id,
    aktenzeichen,
    snapshot_id,
    ez,
    blnr,
    vadium,
    objektgroesse_m2,
    grundstuecksgroesse_m2
FROM {{ source('raw', 'raw_listing_parcels') }}