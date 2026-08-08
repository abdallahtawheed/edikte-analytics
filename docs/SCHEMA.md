# Schema

## Design principles

- Append-only: `listing_snapshots` never receives an UPDATE. Every detected 
  change produces a new row, keyed to the same `aktenzeichen`.
- `aktenzeichen` is the natural tracking key across a listing's lifecycle, but 
  is never a primary key on its own, since it repeats by design.
- Status is modeled separately from field data (`listing_status_events` vs 
  `listing_snapshots`), because the two are queried differently: "what's the 
  current state of every open auction" is a status query, "what changed on 
  this listing over time" is an event-log query. One table would make both 
  awkward.
- Fields not yet confirmed stable across enough real listings live in the 
  `extra` JSONB column rather than fixed columns. This is deliberate, not a 
  placeholder for laziness: the goal is to avoid locking in a schema before 
  the data's true shape is understood. Fields get promoted to real columns 
  once their shape is confirmed stable across many listings. `extra` is meant 
  to shrink over time, not become the permanent home for most of the data, 
  see DECISIONS.md.

## Tables

**listing_snapshots**: the event log. One row per detected change per 
`aktenzeichen`. `content_hash` allows a cheap check ("did anything change 
since last scrape") before doing a full field comparison. `latitude`/
`longitude` are derived via geocoding, not scraped, and are first-class 
columns rather than JSONB since they're computed, not raw source data.

**listing_status_events**: the validated state machine. `transition_valid` is 
computed and stored at insert time against the known legal transition graph 
(Versteigerung, Verschiebung, Entfall des Termins, Zuschlag ohne/mit/nach 
Überbot, Meistbotsverteilung), so anomalous jumps (e.g. Zuschlag back to 
Versteigerung) are queryable directly rather than requiring replay of the full 
event log.

**listing_parcels**: one row per EZ (Einlagezahl), the actual legally 
purchasable unit. `grundstuecksnr` is an array since one EZ can cover multiple 
physical land parcels (e.g. four separate Grundstücksnr under one EZ in a 
farmland listing). `objektgroesse_m2` of 0 is valid and meaningful (e.g. 
undeveloped land with no structure), not a missing value.

**listing_documents**: one row per file (photo, floor plan, site plan, 
appraisal report). Modeled as a child table rather than fixed columns on 
`listing_snapshots` since the count and type of files varies per listing, 
from zero to several photos plus multiple report types.

**case_links**: legally bundled listings that appear as separate Aktenzeichen 
but relate to the same underlying case (e.g. an apartment and its associated 
parking spaces, auctioned as separate edikts under "Alle Edikte zum Fall").

**listing_flags**: keyword-based defect/condition signals extracted from free 
text (e.g. "Feuchtigkeit," "erloschen," access disputes). An interim, 
low-precision signal pending the RAG-over-Langgutachten extension scoped for 
after v1. Not a substitute for reading the full report; flagged for human 
review via `source_excerpt`.

**listings_current** (view, not a table): latest snapshot and status per 
`aktenzeichen`, the primary read path for Streamlit and most dashboard 
queries. Kept as a plain view rather than materialized, since data volume 
(~88 new/updated entries per week nationally) makes live query cost 
negligible; materializing would only add a staleness risk with no real 
performance benefit at this scale.

## Known gaps, deliberately deferred

- Zuschlag/Meistbotsverteilung-specific fields (Meistbot, minimum overbid, 
  Betreibende/Verpflichtete Partei, Tagsatzungstermin) currently live in 
  `extra` rather than a dedicated table, pending more examples to confirm 
  their shape is stable.
- No structured representation of property condition beyond `listing_flags`, 
  see Known Limitations in the README.