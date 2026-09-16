"""검토된 포털 카드 규격의 테스트 기대값만 정정합니다. 애플리케이션 소스는 변경하지 않습니다."""
from pathlib import Path  # 절대 경로 기준입니다.
import subprocess  # 현재 기준을 검사합니다.
ROOT = Path(__file__).resolve().parents[5]  # 프로젝트 루트입니다.
target = ROOT / 'tests/test_edge_layout_browser.mjs'  # 수정 대상 하나입니다.
source = target.read_text(encoding='utf-8')  # 현행 파일을 읽습니다.
expected = subprocess.check_output(['git', '-C', str(ROOT), 'show', 'ac88fa082817a1a76c449497b3b9b849afbc48d5:tests/test_edge_layout_browser.mjs']).decode('utf-8')  # 승인된 원본입니다.
assert source == expected.replace('\r\n', '\n'), 'concurrent test modification'  # 다른 작업자 변경을 보존합니다.
changes = [('portal cards add columns without stretching; Standard retains three', 'portal cards follow admin sizing; Standard uses four columns'), ('assert.equal(columns[1920], 5);', 'assert.equal(columns[1920], 6);'), ('assert.equal(columns[2560], 7);', 'assert.equal(columns[2560], 8);'), ('assert.equal((await measure()).columns, 3);', 'assert.equal((await measure()).columns, 4);'), ('assert.equal((await measure()).main.width, 1024);', 'assert.equal((await measure()).main.width, 1280);')]  # 18rem/80rem 계약입니다.
for before, after in changes:  # 실제 승인 규격을 검사하도록 정정합니다.
    assert source.count(before) == 1, before  # 애매한 치환은 중단합니다.
    source = source.replace(before, after, 1)  # 다른 검사는 유지합니다.
temporary = target.with_name(target.name + '.contract-tmp')  # 부분 파일 쓰기를 방지합니다.
with temporary.open('x', encoding='utf-8', newline='\n') as stream: stream.write(source)  # 기존 임시 파일은 덮지 않습니다.
temporary.replace(target)  # 검증된 전체 파일로 원자적 교체합니다.
print('TEST_CONTRACT_ALIGNED', len(changes))  # 실제 치환 개수입니다.
