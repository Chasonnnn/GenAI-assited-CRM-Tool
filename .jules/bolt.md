
## 2024-03-26 - Performance Pattern: Deep Cloning State Objects
**Learning:** Using `JSON.parse(JSON.stringify(value))` for deep cloning complex React state objects (e.g., pipeline drafts) is a performance anti-pattern. It forces unnecessary serialization/deserialization string memory allocations, blocking the main thread during typing and complex state updates.
**Action:** Always use the native `structuredClone(value)` instead. It avoids allocating intermediate serialized string memory and provides better fidelity by correctly handling Sets, Maps, Dates, and circular references.
