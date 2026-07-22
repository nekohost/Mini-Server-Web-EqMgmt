# 📱 Mini-Server-Web-EqMgmt (장비 및 자산 통합 관리 시스템)

이 프로젝트는 개인 보유 장비(노트북, 보조배터리, 모니터, 이어폰 등)를 등록하고 관리하기 위해 Windows PC에서 개발하여 GitHub를 거쳐 Linux Lite 미니서버에 배포되는 웹 애플리케이션입니다.

---

## 🎯 프로젝트 배경 및 목적
1. **학습 목적:** Python을 처음 배우는 사용자가 Flask 백엔드와 RESTful API의 기본 구조를 공부하기 위한 프로젝트입니다.
2. **개발 환경:** Windows PC (개발/Git Push) ➡️ GitHub ➡️ Linux Lite 미니서버 (배포/Git Pull).
3. **사용자 특성:** 개발 초보자이므로 모든 코드에는 상세한 설명 주석이 포함되어야 하며, 변경 발생 시 의존성 여파를 명확히 안내해야 합니다.

---

## 🛠 기술 스택 & 네트워크 정보
- **Language & Backend:** Python 3 + Flask (가벼운 REST API 서버)
- **Database:** SQLite3 (`equipment.db` 파일 형태 - 미니서버 리소스 사용 최소화)
- **Database GUI (PC용):** DBeaver (SSMS 스타일의 DB 관리 환경 제공)
- **Frontend:** HTML5 + Vanilla JavaScript + Tailwind CSS (CDN)
- **미니서버 IP:** `192.168.0.166` (포트: `5000`)
- **실제 접속 URL (모바일/PC 공통):** `http://192.168.0.166:5000`

---

## 📐 핵심 요구사항 및 화면 최적화 원칙
1. **장비 데이터 구조:** 
   - 기본 필드: 고유ID(`id`), 장비별명(`name`), 카테고리(`category`), 제조사(`manufacturer`), 모델명(`model_name`), 구입일(`purchase_date`), 시리얼넘버(`serial_number`), 메모(`memo`).
   - CRUD(생성, 조회, 수정, 삭제) 기능 완벽 제공.
2. **실시간 반응형 및 모바일/폴더블 최적화:**
   - 접은 스마트폰/폴더블(세로): 1열 카드 레이아웃 (`grid-cols-1`)
   - 펼친 폴더블/태블릿: 2열 카드 레이아웃 (`sm:grid-cols-2`)
   - PC 및 대형 화면: 3~4열 카드 레이아웃 (`lg:grid-cols-3 xl:grid-cols-4`)
   - 기기 리소스 최적화를 위해 무거운 JS 라이브러리를 사용하지 않고 초경량 Tailwind CSS 활용.

---

## 🚨 소프트웨어 설계 및 의존성 지침 (AI Assistant 필수 준수 수칙)

AI(Gemini)가 이 프로젝트의 코드를 수정하거나 기능을 추가할 때는 아래 원칙을 **엄격히 준수**해야 합니다.

### 1. 컬럼(필드) 확장성 보장
DB 테이블에 새로운 컬럼(예: 가격 `price`, 보증기간 `warranty_date` 등)이 추가되더라도 기존 코드가 파괴되지 않아야 합니다. 백엔드의 DB 조회 로직은 `sqlite3.Row` 기반으로 작성되어 컬럼 추가 시 파이썬 코드 수정을 최소화합니다.

### 2. 컬럼 추가 시 동시 수정 체크리스트 (의존성 체인)
새로운 컬럼을 추가할 경우, 반드시 아래 **3가지 지점**을 동시에 수정해야 하며 사용자에게 이를 안내해야 합니다:
1. `app.py` -> `init_db()` : `CREATE TABLE` 구문에 새 컬럼 정의 추가
2. `app.py` -> `add_equipment()` : `INSERT INTO` 구문 및 `data.get()`에 새 컬럼 추가
3. `templates/index.html` : 
   - `<form>` 태그 내 입력받을 `<input>` 추가
   - JS `payload` 객체에 새 필드 추가
   - `fetchEquipment()` 내부의 HTML 카드 렌더링 부분에 `${item.새컬럼명}` 출력 추가

### 3. 코드 주석 보존 수칙
모든 함수와 API 라우트 상단에는 아래 항목이 명시된 주석을 유지해야 합니다:
- `[역할]`: 해당 함수의 기능
- `[의존성 관계]`: 의존하는 함수/파일 및 이 함수에 의존하는 프론트엔드 요소
- `[변경 시 영향도]`: 이 코드를 수정할 때 함께 영향을 받는 다른 위치 안내

---

## 🚀 실행 및 배포 방법

### 1. Windows PC (로컬 테스트 환경)
```bash
pip install flask
python app.py
# 접속: http://localhost:5000