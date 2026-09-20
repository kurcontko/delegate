---
type: regex
target: { source: file, path: store.py }
pattern: 'db\.execute\(f"DELETE FROM orders WHERE user_id = \{user_id\}"\)\n    db\.execute\(f"DELETE FROM users WHERE id = \{user_id\}"\)\n    db\.commit\(\)\n$'
---
