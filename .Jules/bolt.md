
## $(date +%Y-%m-%d) - Vectorize N+1 stage ref resolutions
**Learning:** In heavily used configuration parsers like `_canonicalize_conditions` and `_canonicalize_actions`, doing database lookups iteratively for ID translation scales poorly when bulk setups involve many references.
**Action:** When translating IDs in loops, always traverse the object twice: once to gather the keys for a bulk fetch (`resolve_stages_bulk`), and again to mutate the object using the fetched lookup map in memory.
