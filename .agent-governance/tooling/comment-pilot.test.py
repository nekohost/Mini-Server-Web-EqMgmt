"""[역할] 실제 파일럿의 AST에서 필요한 정의만 분리하여 EN 계약을 검증한다.
[의존성 관계] Python 표준 ast/pathlib. 원본 모듈, Flask, DB는 import하지 않는다.
[변경 시 영향도] 식별자 허용 범위나 오류 계약이 바뀌면 주석 감사가 다시 필요하다.
"""
import ast
import json
import sys
from pathlib import Path

if "--stdin" in sys.argv:
    payload = json.load(sys.stdin)
    source = payload["source"]
else:
    root = Path(__file__).resolve().parents[2]
    source = (root / "utils/lineup_node_service.py").read_text(encoding="utf-8")
    payload = {}


def executable_tree(text):
    """주석/docstring을 제외한 AST만 비교하며 원본 코드는 실행하지 않는다."""
    parsed = ast.parse(text)
    for node in ast.walk(parsed):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                node.body.pop(0)
    return ast.dump(parsed, include_attributes=False)


if "before" in payload:
    assert executable_tree(payload["before"]) == executable_tree(source), "executable AST changed"
    print("PILOT-EXECUTABLE-AST: unchanged from Git HEAD")
tree = ast.parse(source)
definitions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in {"LineupNodeError", "_required_int"}]
assert len(definitions) == 2
fixture = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *definitions], type_ignores=[])
namespace = {}
exec(compile(ast.fix_missing_locations(fixture), "<isolated-comment-contract>", "exec"), namespace)
normalize, error_type = namespace["_required_int"], namespace["LineupNodeError"]
accepted = [(1, 1), (987, 987), ("12", 12), (" +12 ", 12), ("1_000", 1000), ("１２", 12), ("0001", 1)]
rejected = [True, False, None, 1.5, 0, -1, "0", "-1", "1.2", "invalid", "", {}, [], b"1"]
for value, expected in accepted:
    assert normalize(value, "테스트") == expected
for value in rejected:
    try:
        normalize(value, "테스트")
    except error_type as error:
        assert error.status_code == 400
        assert str(error) == "테스트 식별자가 올바르지 않습니다."
    else:
        raise AssertionError(f"unexpectedly accepted: {value!r}")
print(f"PILOT-CONTRACT: {len(accepted) + len(rejected)} cases passed; source AST parsed; no application import")
