## 2024-08-13 - N+1 Query in Ticket Resolution
**Learning:** Found a severe N+1 query vulnerability in `apps/api/app/services/ticketing_service.py` where `_find_ticket_by_reply_token` made a `.first()` query for every valid email in a message's `reply-to` block.
**Action:** Always batch related email header lookups using a single `.in_()` clause to reduce DB roundtrips to O(1) for long threads. Additionally, select only the ID (`db.query(Ticket.id)`) instead of fully hydrating the ORM object.
