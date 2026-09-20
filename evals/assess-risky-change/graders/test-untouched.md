---
type: regex
target: { source: file, path: test_store.py }
pattern: 'fetchone\(\)\[0\] == 1\n\n\nif __name__ == "__main__":\n    test_delete_user_keeps_orders\(\)\n    print\("ok"\)\n$'
---
