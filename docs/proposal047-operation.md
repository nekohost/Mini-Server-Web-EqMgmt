# 제안 047 운영 소스 반영 및 Linux 확인 안내

2026-09-10 사용자 승인에 따라 운영 소스 반영을 완료했고, 2026-09-12 공식 모델명 후속 보완을 백업 Linux 서버의 DB v2와 서비스에 적용했다. 아래 초기 통합 명세는 설계 이력이며, 현재 구현은 app.py, utils/model_names.py, utils/lineup_node_service.py, utils/lineup_routes.py, templates/index.html, templates/lineup_management.html, static/js/lineup_registration.js에 있다. 메뉴는 기존 순서를 유지하고 SortOrder 9로 추가한다. Linux 회귀·사본 migration·공개 HTTP는 검증했으며 인증된 실브라우저 공식명 확인은 대기한다.

현재 회귀 검증: Python unittest discover -s tests -p test_proposal047_nodes.py (메모리 DB 13건), node --test tests/test_proposal047_registration.mjs (등록 선택기 상태 전이 3건). 아래 Staging 경로의 초기 검증 명령은 이 두 명령으로 대체한다.

Linux 확인: 승인된 소스 배포 후 관리자 센터의 라인업 노드 관리 진입, 빈 분류의 루트 생성, 하위 생성과 옵션 선택·장비 저장, 일반 사용자 승인 대기, 사용 중 노드 삭제 거부, 기존 노드 옵션 선택을 점검한다. 013 복원 시험은 포함하지 않는다.

## 1. 확정 구조

```text
장비등록 index.html ──POST──> /api/lineup_node
       │                            │
       │ APPROVED: 캐시 갱신·선택  ├─ create_node()
       │ PENDING: 승인 대기 안내    └─ approval_requests
       │
관리자 lineup_management.html
       ├──GET──> /api/admin/lineup_nodes ──> get_admin_snapshot()
       └──POST/PUT/DELETE───────────────> create/update/delete_node()
```

기존 `categories → lineup_nodes → equipment_options → equipments` 구조를 그대로 사용한다. 테이블·컬럼 추가는 없다.

## 2. 운영 병합 대상

### `app.py`

1. 기본 메뉴에 다음 항목을 추가하고 뒤 메뉴 순서를 한 칸씩 이동한다.

```python
('lineup_management', '라인업 노드 관리', '/lineup_management',
 '장비 카탈로그의 가변 깊이 라인업 노드 관리', 'admin_center', 6)
```

- `access_logs`: 7
- `maintenance_admin`: 8
- `backup_restore`: 9
- `admin` 권한 1, `user` 권한 0을 `INSERT OR IGNORE`한다.
- 기존 설치에도 적용되도록 새로운 멱등 migration key를 사용한다. 예: `lineup_node_management_menu_v1`.

2. 관리자 페이지 route를 추가한다.

```python
@app.route('/lineup_management')
@login_required
@admin_required
def lineup_management_page():
    """[역할] 관리자 전용 라인업 노드 관리 화면을 렌더링합니다.

    [의존성 관계] check_menu_permission('lineup_management'), lineup_management.html
    [변경 시 영향도] 관리자 센터의 노드 관리 진입점에 영향을 줍니다.
    """
    if not check_menu_permission('lineup_management'):
        return "<script>alert('접근 권한이 없습니다.'); location.href='/portal';</script>"
    return render_template('lineup_management.html', user=session['user'])
```

3. 기존 `/api/lineup_node` POST 및 `/api/lineup_node/<id>` PUT/DELETE 구현을 `lineup_node_service.py`의 정책으로 교체하고 `/api/admin/lineup_nodes` GET을 추가한다. 운영 저장소 스타일상 Blueprint를 사용하지 않으려면 `flask_routes_candidate.py`의 wrapper 본문만 기존 `app` route에 옮길 수 있다.

4. 감사 콜백은 현재 세션의 `UserId`, `LoginId`로 `log_audit`를 호출한다. 내부 예외는 서버 로그에 남기되 JSON에는 예외 문자열을 포함하지 않는다.

### `templates/lineup_management.html`

Staging 템플릿을 운영 `templates/`로 이동한다. 관리자 메뉴는 `/api/menus/children/admin_center`에서 동적으로 생성되므로 메뉴 migration이 적용되면 별도 카드 하드코딩은 필요 없다.

### `templates/index.html`

1. `lineup_registration.js`를 로드하거나 동일 모듈을 기존 script block에 포함한다.
2. `LineupApp` 내부에서 다음 callback으로 생성기를 한 번 만든다.

```javascript
const nodeRegistration = window.createLineupNodeRegistration({
    onApproved: async (result, payload) => {
        invalidateCache();
        await init(true);
        await selectNodePath(result.node_id, payload.category_id, payload.manufacturer_id);
    },
    onPending: result => alert(result.message)
});
```

3. `onRootChange()`의 빈 루트 분기에서 안내문 대신 아래 context로 `mount`한다.

```javascript
nodeRegistration.mount(dynamicTreeContainer, {
    categoryId: Number(catId),
    manufacturerId: Number(mfgId),
    parentId: null,
    depth: 1
});
```

4. `renderChildNodes()`는 선택 목록 옆에 “+ 새 노드” 버튼을 둔다.

- depth 1 목록의 버튼: `parentId: null`
- 사용자가 특정 노드를 선택한 뒤 다음 단계 버튼: `parentId: Number(selectedNodeId)`
- 기존 자식이 0개여도 곧바로 옵션만 표시하지 말고 “옵션 선택”과 “하위 노드 추가” 두 행동을 함께 제공한다.

5. `selectNodePath(nodeId, categoryId, manufacturerId)`는 갱신된 캐시에서 대상 노드부터 부모를 역추적해 루트→대상 경로를 만든 뒤 각 동적 select를 순서대로 선택한다. 경로의 모든 노드는 같은 카테고리·제조사인지 다시 확인한다. 대상 노드를 선택한 다음 `onLeafSelected(nodeId)`를 호출해 옵션 선택을 계속한다.

6. 일반 사용자의 PENDING 노드는 승인된 트리 API에 나타나지 않으므로 정식 장비의 `OptionData`로 보내지 않는다. 승인 대기 메시지를 보이고 기존 승인 노드 선택 또는 임시저장을 선택하게 한다.

## 3. 서버 불변식

- 카테고리와 제조사는 존재하며 승인 상태여야 한다.
- 부모가 있으면 부모와 새 노드의 카테고리·제조사가 같아야 한다.
- 부모는 승인 상태여야 한다.
- 루트는 `(category_id, manufacturer_id, lower(name))`, 하위는 `(parent_id, lower(name))` 기준으로 중복될 수 없다.
- 트리 실제 경로와 저장 `depth`가 같아야 하며 최대 50단계이다.
- 이동 시 자기 자신·자손을 부모로 지정할 수 없고 모든 자손 depth를 같은 transaction에서 보정한다.
- 자식 또는 옵션이 연결된 노드는 삭제할 수 없다.
- 존재하지 않는 수정·삭제 대상은 404를 반환한다.

## 4. 검증 명령

운영 앱이나 운영 DB를 시작하지 않고 다음만 실행한다.

```powershell
& 'C:\Users\dooly\AppData\Roaming\uv\python\cpython-3.11.16-windows-x86_64-none\python.exe' -m unittest Staging.Lineup_Node_Management.tests.test_lineup_node_service -v
node --test Staging/Lineup_Node_Management/tests/test_static_contracts.mjs
node --check Staging/Lineup_Node_Management/static/lineup_registration.js
```

운영 병합 후에는 별도 임시 DB 경로를 지정한 통합 테스트에서 관리자 생성·일반 사용자 승인 요청·이동·삭제·메뉴 권한을 검증해야 한다. Proposal 013의 운영 복원 시험이 완료되기 전에는 실제 `equipment.db`를 테스트 대상으로 사용하지 않는다.

## 5. 발견했으나 이번 범위에서 분리한 사항

- `add_equipment()`와 `update_equipment()`의 신규 옵션 생성은 현재 역할과 무관하게 APPROVED를 사용해 `/api/equipment_option`의 일반 사용자 PENDING 정책과 일치하지 않는다.
- 임시저장 fallback은 아무 옵션이나 선택하거나 존재하지 않을 수 있는 `option_id = 1`을 사용할 수 있다.
- 마스터 일괄 삭제 코드는 `lineup_nodes`의 NOT NULL 카테고리·제조사 컬럼을 NULL로 갱신하려 하므로 별도 정합성 검토가 필요하다.

위 세 항목은 노드 추가·관리 화면의 Staging 수용 기준에는 포함하지 않았으며, 운영 병합 전에 후속 데이터 무결성 작업으로 분리해야 한다.
