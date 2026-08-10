# Schema

## Design principles

- Append-only: `listing_snapshots` never receives an UPDATE (except the 
  derived `latitude`/`longitude` fields, a deliberate exception, see below). 
  Every detected change produces a new row.
- `source_url` is the true per-object uniqueness key, and the key used for 
  change detection. `aktenzeichen` is the case/proceeding identifier, and 
  deliberately NOT unique per object: a single Aktenzeichen can legally cover 
  many distinct purchasable objects (e.g. an apartment plus several parking 
  spaces, each with its own detail page, own valuation, and own BLNr). This 
  was discovered through real data, not assumed upfront: change-detection 
  originally keyed on aktenzeichen alone, which caused every object under a 
  multi-object case to be treated as a change of every other object. See 
  ADR-007.
- Status is modeled separately from field data (`listing_status_events` vs 
  `listing_snapshots`), because the two are queried differently: "what's the 
  current state of every open auction" is a status query, "what changed on 
  this listing over time" is an event-log query. One table would make both 
  awkward. Status is tracked at the aktenzeichen (case) level, since the 
  lifecycle status applies to the whole proceeding.
- Fields not yet confirmed stable across enough real listings live in the 
  `extra` JSONB column rather than fixed columns. This is deliberate, not a 
  placeholder for laziness: the goal is to avoid locking in a schema before 
  the data's true shape is understood. Fields get promoted to real columns 
  once their shape is confirmed stable across many listings. `extra` is meant 
  to shrink over time, not become the permanent home for most of the data, 
  see DECISIONS.md.

## Tables

**listing_snapshots**: the event log. One row per detected change per 
`source_url` (i.e. per real object-page). `content_hash` allows a cheap check 
("did anything change since last scrape") before doing a full field 
comparison; it's computed over the extracted content (status, fields, 
documents, correction flag), not the raw HTML, since the raw page includes a 
server-generated print timestamp that changes on every request regardless of 
real content. `latitude`/`longitude` are derived via geocoding, not scraped, 
and are updated in place on the existing row rather than versioned, a 
deliberate exception to the append-only rule since they're an enrichment of 
existing data, not new information observed from the source.

**listing_status_events**: the validated state machine, tracked at the 
aktenzeichen (case) level. `transition_valid` is computed and stored at 
insert time against the known legal transition graph (Versteigerung, 
Verschiebung, Entfall des Termins, Zuschlag ohne/mit/nach Überbot, 
Meistbotsverteilung), so anomalous jumps are queryable directly rather than 
requiring replay of the full event log.

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
appraisal report). Modeled as a child table since the count and type of files 
varies per listing, from zero to several photos plus multiple report types; 
some listings have 10+ photos, each needing its own row.

**case_links**: legally bundled listings that appear as separate Aktenzeichen 
but relate to the same underlying case, distinct from the far more common 
same-Aktenzeichen multi-object pattern handled by `listing_parcels`.

**listing_flags**: keyword-based defect/condition signals extracted from free 
text. Not yet populated; pending the keyword-scanning implementation.

**listings_current** (view, not a table): latest snapshot and status per 
`aktenzeichen`. Important limitation, discovered via real data: for 
multi-object Aktenzeichens, this view collapses to ONE row per case, not one 
per object, since it groups by aktenzeichen. It is correct for case-level 
status ("is this proceeding still open") but NOT sufficient for object-level 
browsing, mapping, or analysis (e.g. showing every individual parking space 
on a map). Object-level "current" queries should hit `listing_snapshots` 
directly, filtered to the latest `scraped_at` per `source_url`. A dedicated 
`objects_current` view keyed on `source_url` is a planned addition, not yet 
built.

## Known gaps, deliberately deferred

- Zuschlag/Meistbotsverteilung-specific fields beyond Meistbot (minimum 
  overbid, Betreibende/Verpflichtete Partei, Tagsatzungstermin) currently 
  live in `extra` rather than a dedicated table, pending more examples to 
  confirm their shape is stable.
- No structured representation of property condition beyond `listing_flags`, 
  see Known Limitations in the README.
- No `objects_current` view yet (see above); object-level "current state" 
  queries currently require manual filtering.
- Whether multiple BLNr-objects under one Aktenzeichen can be won by separate 
  bidders at auction, or must be bid on as one bundled unit, is unverified. 
  Observed real Zuschlag listings show the same Meistbot (final price) 
  repeated across multiple BLNr-objects in at least one case, consistent with 
  either a bundled sale or a site display quirk; not resolved from data 
  alone.