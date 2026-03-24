## 2025-03-24 - structuredClone vs JSON.parse/stringify
**Learning:** Use `structuredClone` instead of `JSON.parse(JSON.stringify())` for deep cloning state objects. It avoids intermediate serialized string memory allocation and correctly handles complex objects like Sets, Maps, and Dates.
**Action:** Always prefer `structuredClone` for deep copying in JavaScript/TypeScript unless there is a specific need for serialization.
