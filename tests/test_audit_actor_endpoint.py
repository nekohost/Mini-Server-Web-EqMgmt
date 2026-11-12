"""Independent synthetic REST route test, without loading the production Flask application.

Uses the actual audit route AST and synthetic in-memory SQLite data only.
"""
import ast
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest


def source_app():
    if isinstance(globals().get("SOURCE_APP"), str):
        return globals()["SOURCE_APP"]
    root = next(p for p in Path(__file__).resolve().parents if (p / "app.py").is_file())
    return (root / "app.py").read_text(encoding="utf-8")


def audit_route_globals(text, db, request_args, permission=True):
    tree = ast.parse(text)
    names = {"AUDIT_ACTOR_NAME_SQL", "ALLOWED_AUDIT_SEARCH_FIELDS"}
    definitions = [
        n for n in tree.body
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)
    ]
    route = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "api_audit_logs")
    route.decorator_list = []
    payload = ast.fix_missing_locations(ast.Module(body=[*definitions, route], type_ignores=[]))
    namespace = {
        "request": SimpleNamespace(args=request_args),
        "session": {"user": {"Role": "admin"}},
        "jsonify": lambda value: value,
        "check_menu_permission": lambda code: permission,
        "get_db_connection": lambda: db,
    }
    exec(compile(payload, "<isolated-audit-route>", "exec"), namespace)
    return namespace["api_audit_logs"]


class AuditRouteIndependentTests(unittest.TestCase):
    def setUp(self):
        self.app_text = source_app()
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.executescript(
            "CREATE TABLE users (UserId INTEGER PRIMARY KEY, LoginId TEXT UNIQUE, Name TEXT);"
            "CREATE TABLE audit_logs (AuditId INTEGER PRIMARY KEY, ActorId INTEGER, "
            "ActorLoginId TEXT, IpAddress TEXT, UserAgent TEXT, TargetTable TEXT, "
            "TargetId INTEGER, Action TEXT, OldValue TEXT, NewValue TEXT, CreatedAt TEXT);"
        )
        self.db.executemany("INSERT INTO users VALUES (?, ?, ?)", [
            (1, "named", "김정상"), (2, "empty", ""),
            (3, "spaces", "   "), (4, "null", None),
        ])
        self.db.executemany(
            "INSERT INTO audit_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (1, 1, "named", "127.0.0.1", "test", "users", 1, "UPDATE", None, None, "2026-11-12 12:00:00"),
                (2, 2, "empty", "127.0.0.1", "test", "users", 2, "LOGIN", None, None, "2026-11-12 12:01:00"),
                (3, 3, "spaces", "127.0.0.1", "test", "users", 3, "LOGIN", None, None, "2026-11-12 12:02:00"),
                (4, 4, "null", "127.0.0.1", "test", "users", 4, "LOGIN", None, None, "2026-11-12 12:03:00"),
                (5, 99, "former", "127.0.0.1", "test", "users", 99, "DELETE", None, None, "2026-11-12 12:04:00"),
                (6, None, None, "127.0.0.1", "test", "system", None, "SYSTEM_TASK", None, None, "2026-11-12 12:05:00"),
            ],
        )

    def tearDown(self):
        self.db.close()

    def run_route(self, args=None, permission=True):
        return audit_route_globals(self.app_text, self.db, args or {}, permission)()

    def test_actual_route_display_and_pagination(self):
        payload = self.run_route()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["pagination"]["total_count"], 6)
        names = {r["AuditId"]: r["ActorName"] for r in payload["data"]}
        self.assertEqual(names, {1: "김정상", 2: "empty", 3: "spaces", 4: "null", 5: "former", 6: "System"})

    def test_exact_name_filter_uses_display_fallback(self):
        payload = self.run_route({"search_field": "ActorName", "match_type": "exact", "keyword": "empty"})
        self.assertEqual([r["AuditId"] for r in payload["data"]], [2])
        self.assertEqual(payload["pagination"]["total_count"], 1)

    def test_system_filter_does_not_include_empty_named_members(self):
        payload = self.run_route({"search_field": "ActorName", "match_type": "exact", "keyword": "System"})
        self.assertEqual([r["AuditId"] for r in payload["data"]], [6])

    def test_actor_name_partial_search_matches_historical_login(self):
        payload = self.run_route({"search_field": "ActorName", "match_type": "like", "keyword": "form"})
        self.assertEqual([r["AuditId"] for r in payload["data"]], [5])

    def test_permission_denied_without_db_write(self):
        result, status = self.run_route(permission=False)
        self.assertEqual(status, 403)
        self.assertEqual(result["status"], "error")

    def test_invalid_column_rejected(self):
        result, status = self.run_route({"search_field": "bad; DROP TABLE users", "keyword": "x"})
        self.assertEqual(status, 400)
        self.assertEqual(result["status"], "error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
