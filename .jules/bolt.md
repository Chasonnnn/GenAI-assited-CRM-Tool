
## 2024-05-02 - Optimize multiple counts to GROUP BY in SQLAlchemy
**Learning:** When calculating both total counts and grouped statistics (e.g., getting counts of successes, failures, and the total count), executing separate `.count()` queries results in redundant database round-trips.
**Action:** Execute a single query grouping by the relevant status field (`GROUP BY field`) to get all counts, and calculate the overall total in Python by summing the values of the grouped result dictionary (`sum(counts_dict.values())`).
