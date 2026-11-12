"""Isolated SQLite regression for audit actor display and name searching.

Uses synthetic accounts and audit rows only. Does not import Flask or access production data.
"""
import ast
from pathlib import Path
import sqlite3
import unittest

ACTOR_SQL = (
    "CASE WHEN NULLIF(TRIM(u.Name), '') IS NOT NULL THEN u.Name "
    "WHEN NULLIF(TRIM(a.ActorLoginId), '') IS NOT NULL THEN a.ActorLoginId "
    "ELSE 'System' END"
)

class AuditActorTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            "CREATE TABLE users (UserId INTEGER PRIMARY KEY, LoginId TEXT UNIQUE, Name TEXT);"
            "CREATE TABLE audit_logs (AuditId INTEGER PRIMARY KEY, ActorId INTEGER, "
            "ActorLoginId TEXT, Action TEXT);"
        )
        users = [
            (1, "named", "김정상"), (2, "empty", ""), (3, "space", "   "),
            (4, "null", None), (5, "padded", "  김공백  "), (6, "system_login", ""),
        ]
        self.conn.executemany("INSERT INTO users VALUES(?,?,?)", users)
        entries = [
            (1, 1, "named", "UPDATE"), (2, 2, "empty", "LOGIN"),
            (3, 3, "space", "LOGIN"), (4, 4, "null", "LOGIN"),
            (5, 5, "padded", "UPDATE"), (6, 99, "deleted_login", "DELETE"),
            (7, None, None, "SYSTEM_TASK"), (8, None, "", "SYSTEM_TASK"),
            (9, None, "   ", "SYSTEM_TASK"),
            (10, 6, "system_login", "LOGIN"), (11, None, "unknown_attempt", "LOGIN_FAILED"),
        ]
        self.conn.executemany("INSERT INTO audit_logs VALUES(?,?,?,?)", entries)

    def tearDown(self):
        self.conn.close()

    def query(self, where="", args=()):
        sql = (
            f"SELECT a.AuditId, {ACTOR_SQL} AS ActorName, a.ActorLoginId "
            "FROM audit_logs a LEFT JOIN users u ON a.ActorLoginId=u.LoginId "
            + where + " ORDER BY a.AuditId"
        )
        return [dict(r) for r in self.conn.execute(sql, args)]

    def test_display_with_names_and_actual_logins(self):
        displays = {r["AuditId"]: r["ActorName"] for r in self.query()}
        self.assertEqual(displays, {
            1: "김정상", 2: "empty", 3: "space", 4: "null",
            5: "  김공백  ", 6: "deleted_login", 7: "System",
            8: "System", 9: "System", 10: "system_login",
            11: "unknown_attempt",
        })

    def test_name_exact_search_matches_display_not_empty_column(self):
        records = self.query(f"WHERE {ACTOR_SQL} = ?", ("empty",))
        self.assertEqual([r["AuditId"] for r in records], [2])
        records = self.query(f"WHERE {ACTOR_SQL} = ?", ("System",))
        self.assertEqual([r["AuditId"] for r in records], [7, 8, 9])
        records = self.query(f"WHERE {ACTOR_SQL} = ?", ("김정상",))
        self.assertEqual([r["AuditId"] for r in records], [1])

    def test_name_like_search_respects_fallback_and_orphaned(self):
        records = self.query(f"WHERE {ACTOR_SQL} LIKE ?", ("%login%",))
        self.assertEqual([r["AuditId"] for r in records], [6, 10])
        records = self.query(f"WHERE {ACTOR_SQL} LIKE ?", ("%김%",))
        self.assertEqual([r["AuditId"] for r in records], [1, 5])

    def test_app_source_uses_one_expression_for_output_and_search(self):
        root = next(folder for folder in Path(__file__).resolve().parents if (folder / 'app.py').is_file())
        source = (root / 'app.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        constant = next(node for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'AUDIT_ACTOR_NAME_SQL' for t in node.targets))
        self.assertEqual(ast.literal_eval(constant.value), ACTOR_SQL)
        self.assertIn("'ActorName': AUDIT_ACTOR_NAME_SQL", source)
        self.assertIn('{AUDIT_ACTOR_NAME_SQL} AS ActorName', source)

    def test_original_bug_present_in_baseline(self):
        original = self.conn.execute(
            "SELECT COALESCE(u.Name, a.ActorLoginId, 'System') "
            "FROM audit_logs a LEFT JOIN users u ON a.ActorLoginId=u.LoginId "
            "WHERE a.AuditId=2"
        ).fetchone()[0]
        self.assertEqual(original, "")
        self.assertNotEqual(original, self.query("WHERE a.AuditId=2")[0]["ActorName"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
