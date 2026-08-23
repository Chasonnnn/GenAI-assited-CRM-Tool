
## 2024-05-19 - Limit Scope of Optmizations
**Learning:** Even when multiple similar performance bottlenecks (like N+1 queries) are identified across different services, batching them into a single pull request violates the "ONE small performance improvement" boundary constraint.
**Action:** Always constrain changes to a single specific function or file optimization per PR to adhere to strict scope limitations, ignoring other identified issues until a separate task is created for them.
