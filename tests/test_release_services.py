"""Linux-only isolated fixtures: never open the service's equipment.db."""
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from utils.equipment_audit_migration import DDL, migrate_equipment_audit_log
from utils.lineup_node_service import add_full_model_names, save_option, delete_option, LineupNodeError


@unittest.skipIf(os.name == 'nt', 'Project policy: runtime/database fixtures execute on Linux only')
class AuditMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='eqmgmt-audit-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'fixture.db'
        self.backups = self.root / 'migration-backups'
        self.c = sqlite3.connect(self.db)
        self.addCleanup(self.c.close)
        self.c.execute('CREATE TABLE equipments (id INTEGER PRIMARY KEY)')
        self.c.execute(DDL.rstrip().removesuffix(')') + ', FOREIGN KEY(equipment_id) REFERENCES equipments(id))')
        self.c.execute('INSERT INTO equipments VALUES (10)')
        self.c.execute("INSERT INTO equipments_audit_log VALUES (1,10,'CREATE',NULL,'{\"이름\":\"장비\"}',1,'2026-09-11 09:52:11.123')")
        self.c.execute("INSERT INTO equipments_audit_log VALUES (2,20,'DELETE','{\"옵션\":1}',NULL,NULL,'2026-09-11 09:52:12.456')")
        self.c.execute("UPDATE sqlite_sequence SET seq=100 WHERE name='equipments_audit_log'")
        self.c.execute('CREATE INDEX custom_audit_action ON equipments_audit_log(action_type)')
        self.c.commit()

    def rows(self):
        return self.c.execute('SELECT * FROM equipments_audit_log ORDER BY id').fetchall()

    def test_preserves_rows_sequence_indexes_backup_and_is_idempotent(self):
        before = self.rows()
        result = migrate_equipment_audit_log(self.db, self.backups)
        self.assertTrue(result['applied'])
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.c.execute('PRAGMA foreign_key_check').fetchall(), [])
        self.assertEqual(self.c.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        backup_path = Path(result['backup_path'])
        with sqlite3.connect(backup_path) as copy:
            self.assertEqual(copy.execute('SELECT * FROM equipments_audit_log ORDER BY id').fetchall(), before)
            self.assertEqual(len(copy.execute('PRAGMA foreign_key_check').fetchall()), 1)
        evidence = json.loads(backup_path.with_suffix('.json').read_text(encoding='utf-8'))
        self.assertEqual(evidence['audit_summary']['count'], 2)
        self.assertEqual(evidence['audit_summary']['nulls']['changed_by'], 1)
        self.assertEqual(len(evidence['backup_sha256']), 64)
        self.assertEqual(backup_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.backups.stat().st_mode & 0o777, 0o700)
        self.assertIsNotNone(self.c.execute("SELECT 1 FROM sqlite_master WHERE name='custom_audit_action'").fetchone())
        self.c.execute("INSERT INTO equipments_audit_log(equipment_id,action_type) VALUES(999,'DELETE')")
        self.assertEqual(self.c.execute('SELECT MAX(id) FROM equipments_audit_log').fetchone()[0], 101)
        self.c.commit()
        self.assertFalse(migrate_equipment_audit_log(self.db, self.backups)['applied'])
        self.assertEqual(len(list(self.backups.glob('*.db'))), 1)

    def test_unknown_column_is_rejected_without_touching_history(self):
        self.c.execute('ALTER TABLE equipments_audit_log ADD COLUMN custom TEXT')
        self.c.commit()
        before = self.rows()
        with self.assertRaisesRegex(ValueError, 'unexpected audit schema'):
            migrate_equipment_audit_log(self.db, self.backups)
        self.assertEqual(self.rows(), before)

    def test_other_orphan_is_not_whitelisted(self):
        self.c.executescript('CREATE TABLE bad (id INTEGER REFERENCES equipments(id)); INSERT INTO bad VALUES(100);')
        with self.assertRaisesRegex(ValueError, 'unrelated foreign key'):
            migrate_equipment_audit_log(self.db, self.backups)
        self.assertEqual(len(self.c.execute('PRAGMA foreign_key_check').fetchall()), 2)

    def test_copy_failure_rolls_back_after_preserving_backup(self):
        from utils import equipment_audit_migration as migration
        original = migration._fingerprint
        def fingerprint(connection, table):
            if table.endswith('_new'):
                raise ValueError('injected copy failure')
            return original(connection, table)
        before = self.rows()
        with patch.object(migration, '_fingerprint', side_effect=fingerprint):
            with self.assertRaisesRegex(ValueError, 'injected'):
                migrate_equipment_audit_log(self.db, self.backups)
        self.assertEqual(self.rows(), before)
        self.assertEqual(len(self.c.execute('PRAGMA foreign_key_list(equipments_audit_log)').fetchall()), 1)
        self.assertEqual(len(list(self.backups.glob('*.db'))), 1)

    def test_empty_history(self):
        self.c.execute('DELETE FROM equipments_audit_log'); self.c.commit()
        self.assertEqual(migrate_equipment_audit_log(self.db, self.backups)['audit_count'], 0)

    def test_large_history_and_fk_on_off_delete(self):
        self.c.executemany("INSERT INTO equipments_audit_log(equipment_id,action_type,old_value) VALUES(?,'DELETE',?)",
                           ((i + 1000, json.dumps({'n': i})) for i in range(1000)))
        self.c.commit()
        before = self.rows()
        migrate_equipment_audit_log(self.db, self.backups)
        self.assertEqual(self.rows(), before)
        for setting in ('OFF', 'ON'):
            self.c.execute('PRAGMA foreign_keys=' + setting)
            self.c.execute('INSERT OR IGNORE INTO equipments VALUES(10)')
            self.c.execute("INSERT INTO equipments_audit_log(equipment_id,action_type) VALUES(10,'DELETE')")
            self.c.execute('DELETE FROM equipments WHERE id=10'); self.c.commit()
            self.assertEqual(self.c.execute('PRAGMA foreign_key_check').fetchall(), [])


@unittest.skipIf(os.name == 'nt', 'Project policy: runtime/database fixtures execute on Linux only')
class CatalogReleaseTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(':memory:')
        self.addCleanup(self.c.close)
        self.c.executescript("""
            CREATE TABLE lineup_nodes(id INTEGER PRIMARY KEY, parent_id INTEGER, category_id INTEGER, manufacturer_id INTEGER,
                name TEXT, depth INTEGER, status TEXT, requested_by INTEGER, created_at TEXT);
            CREATE TABLE equipment_options(id INTEGER PRIMARY KEY, lineup_node_id INTEGER, option_name TEXT,
                specs_json TEXT, status TEXT, requested_by INTEGER, created_at TEXT);
            CREATE TABLE equipments(id INTEGER PRIMARY KEY, option_id INTEGER, is_draft INTEGER);
            CREATE TABLE approval_requests(RequestId INTEGER PRIMARY KEY, RequesterId INTEGER, RequestType TEXT,
                RequestDataJSON TEXT, Status TEXT, CreatedAt TEXT, UpdatedAt TEXT);
            INSERT INTO lineup_nodes VALUES(1,NULL,1,1,'Root',99,'APPROVED',1,''),(2,1,1,1,'Branch',99,'APPROVED',1,''),
                (3,2,1,1,'Leaf',99,'APPROVED',1,''),(4,99,1,1,'Orphan',1,'APPROVED',1,'');
        """)
        self.admin = {'UserId': 1, 'Role': 'admin'}
        self.user = {'UserId': 2, 'Role': 'user'}

    def item(self, node, leaf):
        return {'EquipmentId': 22, 'OptionId': 9, 'LineupNodeId': node, 'ModelName': leaf}

    def test_full_paths_preserve_leaf_and_ids_with_one_query(self):
        statements = []
        self.c.set_trace_callback(statements.append)
        items = [self.item(3, 'Leaf'), self.item(2, 'Branch'), self.item(3, 'Leaf')]
        add_full_model_names(self.c, items)
        self.assertEqual([i['FullModelName'] for i in items], ['Root / Branch / Leaf', 'Root / Branch', 'Root / Branch / Leaf'])
        self.assertEqual(items[0]['ModelName'], 'Leaf'); self.assertEqual(items[0]['OptionId'], 9)
        self.assertEqual(len(statements), 1)

    def test_cycle_missing_cross_category_and_depth_fallback(self):
        self.c.execute('UPDATE lineup_nodes SET parent_id=3 WHERE id=2')
        self.assertEqual(add_full_model_names(self.c, [self.item(3, 'Leaf')])[0]['FullModelName'], 'Leaf')
        self.assertEqual(add_full_model_names(self.c, [self.item(4, 'Orphan'), self.item(None, None)])[1]['FullModelName'], '-')
        self.c.execute('UPDATE lineup_nodes SET parent_id=1, category_id=2 WHERE id=2')
        items = add_full_model_names(self.c, [self.item(1, 'Root'), self.item(2, 'Branch')])
        self.assertEqual(items[1]['FullModelName'], 'Branch')
        self.c.executemany("INSERT INTO lineup_nodes VALUES(?,?,1,1,?,1,'APPROVED',1,'')", ((i, i-1 if i>10 else None, str(i)) for i in range(10, 61)))
        self.assertEqual(add_full_model_names(self.c, [self.item(60, '60')])[0]['FullModelName'], '60')
        self.assertEqual(len(add_full_model_names(self.c, [self.item(59, '59')])[0]['FullModelName'].split(' / ')), 50)

    def test_option_crud_duplicate_validation_and_no_move(self):
        opt = save_option(self.c, {'lineup_node_id': 3, 'option_name': '16GB', 'specs': {'RAM': '16GB'}}, self.admin)
        oid = opt['option_id']
        with self.assertRaises(LineupNodeError):
            save_option(self.c, {'lineup_node_id': 3, 'option_name': '16gb'}, self.admin)
        with self.assertRaises(LineupNodeError):
            save_option(self.c, {'lineup_node_id': 1, 'option_name': '16GB'}, self.admin, oid)
        updated = save_option(self.c, {'option_name': '32GB', 'specs': {'RAM': '32GB'}}, self.admin, oid)
        self.assertEqual(updated['before']['option_name'], '16GB')
        self.assertEqual(delete_option(self.c, oid)['option_name'], '32GB')
        with self.assertRaises(LineupNodeError): delete_option(self.c, oid)

    def test_active_and_draft_references_block_option_delete(self):
        oid = save_option(self.c, {'lineup_node_id': 3, 'option_name': 'x'}, self.admin)['option_id']
        for draft in (0, 1, None):
            self.c.execute('INSERT INTO equipments VALUES(1,?,?)', (oid, draft))
            with self.assertRaises(LineupNodeError): delete_option(self.c, oid)
            self.c.execute('DELETE FROM equipments')
        self.assertIsNotNone(self.c.execute('SELECT id FROM equipment_options WHERE id=?', (oid,)).fetchone())
        delete_option(self.c, oid)

    def test_pending_option_has_approval_and_cannot_bypass_it(self):
        oid = save_option(self.c, {'lineup_node_id': 3, 'option_name': 'pending'}, self.user)['option_id']
        self.assertEqual(self.c.execute('SELECT RequestType FROM approval_requests').fetchone()[0], 'Equipment_Option')
        with self.assertRaises(LineupNodeError): delete_option(self.c, oid)
        with self.assertRaises(LineupNodeError): save_option(self.c, {'option_name': 'bypass'}, self.admin, oid)

    def test_bad_names_specs_and_nodes_are_rejected(self):
        for payload in ([], {'lineup_node_id': 99, 'option_name': 'x'}, {'lineup_node_id': 3, 'option_name': ''},
                        {'lineup_node_id': 3, 'option_name': 'x', 'specs': []},
                        {'lineup_node_id': 3, 'option_name': 'x', 'specs': {'bad': float('nan')}}):
            with self.assertRaises(LineupNodeError): save_option(self.c, payload, self.admin)


if __name__ == '__main__':
    unittest.main()
