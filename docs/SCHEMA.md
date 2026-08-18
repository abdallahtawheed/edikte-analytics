# Schema

## Design principles

- **Append-only**: `listing_snapshots` never receives an UPDATE. Every
  detected change produces a new row. There is no exception to this rule —
  geocoded coordinates are handled entirely outside this table (see below).
- **`source_url` is the true per-object uniqueness key**, and the key used
  for change detection. `aktenzeichen` is the case/proceeding identifier, and
  deliberately NOT unique per object: a single Aktenzeichen can legally cover
  many distinct purchasable objects (e.g. an apartment plus several parking
  spaces, each with its own detail page, own valuation, and own BLNr). This
  was discovered through real data, not assumed upfront: change-detection
  originally keyed on aktenzeichen alone, which caused every object under a
  multi-object case to be treated as a change of every other object. See
  ADR-007.
- **Geocoded coordinates live in their own table** (`listing_coordinates`),
  keyed on `source_url`, rather than as columns on `listing_snapshots`. This
  sidesteps the append-only question entirely: coordinates are a derived
  enrichment of an object, not a new fact observed from the source page, so
  they're modeled as their own upserted table rather than as fields that
  would otherwise need an exception carved out of the event log.
- **Status is modeled separately from field data** (`listing_status_events`
  vs `listing_snapshots`), because the two are queried differently: "what's
  the current state of every open auction" is a status query, "what changed
  on this listing over time" is an event-log query. One table would make
  both awkward. Status transitions are tracked per OBJECT (`source_url`),
  not per case — see the `listing_status_events` entry below and ADR-013.
- **Fields not yet confirmed stable** across enough real listings live in the
  `extra` JSONB column rather than fixed columns. This is deliberate, not a
  placeholder for laziness: the goal is to avoid locking in a schema before
  the data's true shape is understood. Fields get promoted to real columns
  once their shape is confirmed stable across many listings. `extra` is
  meant to shrink over time, not become the permanent home for most of the
  data, see DECISIONS.md.

## Tables

**listing_snapshots**: the event log. One row per detected change per
`source_url` (i.e. per real object-page). `content_hash` allows a cheap
check ("did anything change since last scrape") before doing a full field
comparison; it's computed over the extracted content (status, fields,
documents, correction flag), not the raw HTML, since the raw page includes a
server-generated print timestamp that changes on every request regardless of
real content.

**listing_status_events**: the validated state machine, tracked per OBJECT
via `source_url` (see ADR-013). Originally keyed only by `aktenzeichen`,
which caused multi-object cases to have their independent status histories
conflated into one misleading shared stream, since `previous_status` lookups
weren't scoped to the specific object — one object's recorded transition
could show a sibling object's prior state as its "previous" status.
`aktenzeichen` is retained on each row for case-level queries, but
`previous_status` and `transition_valid` are computed per `source_url`.
`transition_valid` is computed and stored at insert time against the known
legal transition graph (Versteigerung, Verschiebung, Entfall des Termins,
Zuschlag ohne/mit/nach Überbot, Meistbotsverteilung), so anomalous jumps are
queryable directly rather than requiring replay of the full event log.
Status history recorded before ADR-013 (`source_url` is NULL on those rows)
retains the old case-level-conflated sequencing and is not retroactively
correctable, since which object a historical event truly belonged to isn't
recoverable after the fact.

**listing_parcels**: one row per object-snapshot. `ez` (Einlagezahl)
identifies the land registry entry for the whole building/property; it is
shared by every object within that building, and is NOT the per-object key.
`blnr` is the real per-object identifier, confirmed via real Versteigerung
listings to carry its own independently-set Schätzwert, Vadium, and
Geringstes Gebot even when EZ is shared across many objects (e.g. an
apartment building's individual units and parking spaces). `snapshot_id`
(foreign key) ties each parcel row to the exact page/scrape it was extracted
from, since one aktenzeichen's parcels span many distinct snapshots.
`grundstuecksnr` is an array since one EZ can cover multiple physical land
parcels. `objektgroesse_m2` of 0 is valid and meaningful (e.g. undeveloped
land with no structure), not a missing value.

**listing_documents**: one row per file (photo, floor plan, site plan,
appraisal report). Modeled as a child table since the count and type of
files varies per listing, from zero to several photos plus multiple report
types; some listings have 10+ photos, each needing its own row.

**case_links**: legally bundled listings that appear as separate
Aktenzeichen but relate to the same underlying case, distinct from the far
more common same-Aktenzeichen multi-object pattern handled by
`listing_parcels`.

**listing_flags**: keyword-based defect/condition signals extracted from
free text, organized by `category` (structural damage, construction/
legality, legal/financial, boundary/access, environmental, buyer
restrictions — see ADR-011).

**listing_coordinates**: one row per object (`source_url`, primary key).
`latitude`/`longitude` are derived via geocoding, not scraped, and are
upserted directly rather than versioned — a geocoding rerun updates the
existing row for that `source_url`, since it's an enrichment of an already-
known object rather than new information observed from the source.

**listings_current** (view, not a table): latest snapshot and status per
`aktenzeichen`. Important limitation, discovered via real data: for
multi-object Aktenzeichens, this view collapses to ONE row per case, not one
per object, since it groups by aktenzeichen. It is correct for case-level
status ("is this proceeding still open") but NOT sufficient for object-level
browsing, mapping, or analysis (e.g. showing every individual parking space
on a map). For object-level "current" queries, use `objects_current` below.

**objects_current** (view, not a table): latest snapshot and state per
OBJECT (`source_url`), the primary read path for Streamlit and per-object
analysis. Deliberately does NOT join `listing_status_events` for status
display, since that table's status can lag or mismatch a specific object
during multi-object cases; object-level status is instead derived from each
row's own `status_title`, classified via `classify_status()` in the
application layer (see ADR-010). Joins in `listing_coordinates` (latitude,
longitude) and `listing_parcels` (`objektgroesse_m2`,
`grundstuecksgroesse_m2`, `blnr`) — the parcel join is on
`p.snapshot_id = s.snapshot_id`, so parcel fields only populate correctly
when a parcel row exists for that exact snapshot; if parcels and snapshots
ever drift out of sync for an object, its size/BLNr fields will show NULL
here even though the object itself is present.

## Known gaps, deliberately deferred

- Zuschlag/Meistbotsverteilung-specific fields beyond Meistbot (minimum
  overbid, Betreibende/Verpflichtete Partei, Tagsatzungstermin) currently
  live in `extra` rather than a dedicated table, pending more examples to
  confirm their shape is stable.
- No structured representation of property condition beyond `listing_flags`,
  see Known Limitations in the README.
- Whether bundled-BLNr sales ever carry differentiated per-unit pricing:
  resolved, no — the source site publishes one shared price per bundle, no
  schema change can recover a per-unit price that was never captured on the
  source page. See the BLNr open item in DECISIONS.md for the full
  investigation.
- Schriftliche Anbote listing pages use a distinct field structure not yet
  handled by any extraction path; structured fields (ort, plz, kategorie,
  schaetzwert, geringstes_gebot) are currently NULL for these listings
  despite the raw data being present on the page.