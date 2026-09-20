#!/bin/sh
set -eu
git init -q
git config user.email eval@example.com
git config user.name eval
cat > store.py <<'PY'
import sqlite3


def connect(path=":memory:"):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, deleted INTEGER DEFAULT 0)")
    db.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, user_id INTEGER, total REAL)")
    return db


def delete_user(db, user_id):
    db.execute("UPDATE users SET deleted = 1 WHERE id = ?", (user_id,))
    db.commit()
PY
cat > test_store.py <<'PY'
from store import connect, delete_user


def test_delete_user_keeps_orders():
    db = connect()
    db.execute("INSERT INTO users (id, name) VALUES (1, 'a')")
    db.execute("INSERT INTO orders (user_id, total) VALUES (1, 9.5)")
    delete_user(db, 1)
    assert db.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 1


if __name__ == "__main__":
    test_delete_user_keeps_orders()
    print("ok")
PY
git add -A
git commit -qm "Soft-delete users"
cat > store.py <<'PY'
import sqlite3


def connect(path=":memory:"):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT, deleted INTEGER DEFAULT 0)")
    db.execute("CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, user_id INTEGER, total REAL)")
    return db


def delete_user(db, user_id):
    db.execute(f"DELETE FROM orders WHERE user_id = {user_id}")
    db.execute(f"DELETE FROM users WHERE id = {user_id}")
    db.commit()
PY
