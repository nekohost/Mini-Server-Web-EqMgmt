"""Apply one catalog decision to server-recorded targets inside the caller's writer transaction."""
from utils.roadmap_validation import InputError


MASTERS = {
    'ADD_CATEGORY': ('categories', 'CategoryId', 'category_id'),
    'ADD_MANUFACTURER': ('manufacturers', 'ManufacturerId', 'manufacturer_id'),
}
NODE_TYPES = ('Lineup_Node', 'ADD_LINEUP_NODE')
OPTION_TYPES = ('Equipment_Option', 'ADD_EQUIPMENT_OPTION')


def _one(rows):
    if len(rows) != 1:
        raise InputError('대기 중인 신청 대상 한 건을 확인할 수 없습니다.', 409)
    return rows[0][0]


def _linked_rows(db, links, owner, column, master_id):
    for link in links:
        row = db.execute(f"""
            SELECT e.id, n.id AS node_id, o.id AS option_id, n.status AS node_status,
                   o.status AS option_status, c.IsApproved AS category_ready, m.IsApproved AS maker_ready
            FROM equipments e JOIN equipment_options o ON o.id=e.option_id
            JOIN lineup_nodes n ON n.id=o.lineup_node_id
            JOIN categories c ON c.CategoryId=n.category_id JOIN manufacturers m ON m.ManufacturerId=n.manufacturer_id
            WHERE e.id=? AND n.id=? AND o.id=? AND e.user_id=? AND e.is_draft=1 AND n.{column}=?
              AND n.parent_id IS NULL AND n.name='기본 모델' AND o.option_name='기본 사양'
              AND n.requested_by=? AND o.requested_by=?
        """, (link['equipment_id'], link['node_id'], link['option_id'], owner, master_id, owner, owner)).fetchone()
        if row:
            yield row


def _activate(db, links, owner, column, master_id):
    for row in _linked_rows(db, links, owner, column, master_id):
        if row['category_ready'] and row['maker_ready']:
            db.execute("UPDATE lineup_nodes SET status='APPROVED' WHERE id=? AND status='PENDING'", (row['node_id'],))
            db.execute("UPDATE equipment_options SET status='APPROVED' WHERE id=? AND status='PENDING'", (row['option_id'],))
            db.execute('UPDATE equipments SET is_draft=0,is_public=0 WHERE id=? AND user_id=? AND is_draft=1',
                       (row['id'], owner))


def _master(db, kind, info, owner, approve, replacement):
    table, key, column = MASTERS[kind]
    target = info.get(column, info.get('master_id'))
    where = f'{key}=?' if target is not None else 'Name=?'
    master_id = _one(db.execute(f'SELECT {key} FROM {table} WHERE {where} AND IsApproved=0 LIMIT 2',
                                (target if target is not None else info['name'],)).fetchall())
    links = info.get('linked_equipment', [])
    if approve:
        db.execute(f'UPDATE {table} SET IsApproved=1 WHERE {key}=? AND IsApproved=0', (master_id,))
        _activate(db, links, owner, column, master_id)
        return
    if replacement:
        new_id = _one(db.execute(f'SELECT {key} FROM {table} WHERE Name=? AND IsApproved=1 LIMIT 2',
                                 (replacement,)).fetchall())
        by_node = {}
        for row in _linked_rows(db, links, owner, column, master_id):
            if row['node_status'] == row['option_status'] == 'PENDING':
                by_node.setdefault(row['node_id'], set()).add(row['id'])
        for node, allowed in by_node.items():
            # Moving a shared node also changes its descendants and every attached equipment.
            actual = {r[0] for r in db.execute('SELECT e.id FROM equipments e JOIN equipment_options o ON o.id=e.option_id WHERE o.lineup_node_id=?', (node,))}
            extra = db.execute("SELECT 1 FROM lineup_nodes WHERE parent_id=? UNION ALL SELECT 1 FROM equipment_options WHERE lineup_node_id=? AND (requested_by IS NOT ? OR option_name!='기본 사양' OR status!='PENDING') LIMIT 1", (node, node, owner)).fetchone()
            if actual != allowed or extra:
                raise InputError('다른 장비나 하위 항목이 연결되어 대체할 수 없습니다.', 409)
            db.execute(f"UPDATE lineup_nodes SET {column}=? WHERE id=? AND requested_by=? AND status='PENDING'", (new_id, node, owner))
        _activate(db, links, owner, column, new_id)
    if db.execute(f'SELECT 1 FROM lineup_nodes WHERE {column}=? LIMIT 1', (master_id,)).fetchone():
        raise InputError('다른 연결이 남아 있습니다. 참조를 정리한 뒤 반려해 주세요.', 409)
    # The pre-migration equipment table has text references without a foreign key.
    legacy_column = 'Category' if kind == 'ADD_CATEGORY' else 'Manufacturer'
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='equipment'").fetchone():
        if db.execute(f'SELECT 1 FROM equipment WHERE {legacy_column}=(SELECT Name FROM {table} WHERE {key}=?) LIMIT 1', (master_id,)).fetchone():
            raise InputError('이전 형식의 장비가 이 분류를 참조합니다.', 409)
    db.execute(f'DELETE FROM {table} WHERE {key}=? AND IsApproved=0', (master_id,))


def decide(db, request_row, info, approve, replacement):
    kind, owner = request_row['RequestType'], request_row['RequesterId']
    if kind in MASTERS:
        return _master(db, kind, info, owner, approve, replacement)
    if kind in NODE_TYPES:
        table, id_field, label = 'lineup_nodes', 'node_id', 'name'
        parent_keys = ('parent_id', 'category_id', 'manufacturer_id')
        references = ('SELECT 1 FROM lineup_nodes WHERE parent_id=? LIMIT 1',
                      'SELECT 1 FROM equipment_options WHERE lineup_node_id=? LIMIT 1')
    elif kind in OPTION_TYPES:
        table, id_field, label = 'equipment_options', 'option_id', 'option_name'
        parent_keys = ('lineup_node_id',)
        references = ('SELECT 1 FROM equipments WHERE option_id=? LIMIT 1',)
    else:
        raise InputError('지원하지 않는 결재 유형입니다.', 409)
    where, values = ["status='PENDING'", 'requested_by=?'], [owner]
    if info.get(id_field) is not None:
        where.append('id=?')
        values.append(info[id_field])
    else:
        where.append(label + '=?')
        values.append(info.get(label, info.get('name')))
        for field in parent_keys:
            if field in info:
                where.append(field + ' IS ?')
                values.append(info[field])
    item = _one(db.execute(f'SELECT id FROM {table} WHERE ' + ' AND '.join(where) + ' LIMIT 2', values).fetchall())
    if approve:
        db.execute(f"UPDATE {table} SET status='APPROVED' WHERE id=? AND requested_by=? AND status='PENDING'", (item, owner))
    else:
        if any(db.execute(query, (item,)).fetchone() for query in references):
            raise InputError('연결된 장비·옵션·하위 노드를 먼저 확인해 주세요.', 409)
        db.execute(f"DELETE FROM {table} WHERE id=? AND requested_by=? AND status='PENDING'", (item, owner))
