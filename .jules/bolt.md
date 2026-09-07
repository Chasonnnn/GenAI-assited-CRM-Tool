## 2024-10-27 - N+1 Query in Meta Form Mapping Preview
**Learning:** Found an N+1 query vulnerability when rendering previews for meta form mappings in `meta_form_mapping_service.py` where a database query for `MetaAd` details was executed for every missing ad name within a preview loop.
**Action:** Replace single `.first()` ORM lookups inside Python `for` loops with an initial pre-fetch using the `.in_()` operator to construct an O(1) in-memory dictionary lookup. Always verify `ad_ids_to_fetch` is not empty before executing the `.in_()` query to avoid SQL syntax errors.
