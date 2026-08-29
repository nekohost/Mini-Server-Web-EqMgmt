"""
================================================================================
[파일명]: Staging/utils/__init__.py
[역할]: utils 패키지 초기화 및 공통 백엔드 유틸리티 서브모듈 네임스페이스 정의
[의존성 관계]:
  - 하위 모듈: utils.mailer (send_email, get_graph_access_token)
  - 호출 모듈: app.py, db_migration.py 등 백엔드 전반
[변경 시 영향도]:
  - 패키지 네임스페이스 구조 변경 시 'from utils import ...' 구문을 사용하는 전체 백엔드 파일에 영향
================================================================================
"""

# [1] Python 인터프리터가 utils 디렉터리를 하나의 독립된 패키지(Package Module)로 인식하도록 선언
#     - 이 파일이 존재함으로써 상위 애플리케이션(app.py)에서 'import utils.mailer' 또는 'from utils.mailer import send_email' 형태로 하위 모듈 임포트 가능

# [2] utils 패키지 버전 및 메타 정보 (필요 시 확장 가능한 네임스페이스 영역)
__all__ = ['mailer']
