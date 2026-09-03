---
id: engineering.schema-evolution
version: 1
parent: engineering.data-model
source_rules: [RULE-4.1.1, RULE-4.2.1, RULE-4.2.2, RULE-4.2.3.1, RULE-4.2.3.2, RULE-4.2.3.3]
source_validations: []
source_entrypoints: []
human_rule_sections: ["4-1-1", "4-2-1", "4-2-2", "4-2-3-1", "4-2-3-2", "4-2-3-3"]
source_section_digest: E8DA3A7F081BF36EF5BC9D5727625108A05D7A941BD884B02BAB996FD4BBA5C3
always_load: false
may_relax_parent: false
---

# 컬럼 확장과 의존성 체인

DB 조회는 `sqlite3.Row` 기반으로 유지하여 컬럼 추가 시 Python 코드의 파괴적 변경을 최소화한다.

장비 컬럼을 추가할 때에는 다음 위치를 한 작업 단위로 점검하고 사용자에게 영향 범위를 알린다.

1. `app.py`의 `init_db()` 내 `CREATE TABLE`
2. `app.py`의 `add_equipment()` 내 `INSERT INTO`와 `data.get()`
3. `templates/index.html`의 입력 `<input>`
4. JavaScript `payload` 객체
5. `fetchEquipment()`의 카드 렌더링 `${item.새컬럼명}`

현재 구조가 달라졌다면 이름을 기계적으로 가정하지 말고 동등한 실제 위치를 검색한다. 일부 위치만 수정한 상태를 완료로 보고하지 않는다.


