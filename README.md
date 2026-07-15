# EvidenceRoot

한국어 온라인 정보 검증(팩트체크 보조) Streamlit 앱. 문장/링크/이미지를 입력하면 세부 주장으로 분해하고,
공식 자료·뉴스·팩트체크 자료를 검색해 중복/재인용을 제거한 뒤, 독립 근거를 기준으로 지지/반박/판단 불가를 계산한다.

## 실행 방법

```bash
# 1) 가상환경 활성화 (이미 .venv 생성됨)
.venv\Scripts\activate

# 2) 의존성이 없다면 설치
pip install -r requirements.txt

# 3) 앱 실행
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속.

## API 키 설정

앱 실행 후 사이드바에서 **API 설정**으로 이동해 화면에서 직접 키를 입력·저장·삭제한다. `.env` 파일을 직접 만들
필요는 없다 (원하면 `.env.example`을 복사해 `.env`로 사용해도 된다).

- **필수**: Gemini API Key, Gemini 모델명, Naver Client ID/Secret
- **선택**: Google Fact Check API Key

저장된 키는 로컬에서는 OS Keyring(불가 시 `data/encrypted_secrets.json` Fernet 암호화 파일)에 저장되어
재실행 후에도 유지된다. 공개 배포 환경에서는 `APP_ADMIN_PASSWORD`를 설정해야 API 설정 화면의 저장/삭제가 열린다.

## 구현된 기능

- 문장 / 링크 / 이미지(OCR) 3가지 입력 방식
- Gemini 기반 세부 주장(최대 3개) 분해, 유형·검증가능성 분류
- 주장별 동적 검색어 생성(사건명 하드코딩 없음) + 공식기관 후보 추정
- Naver 뉴스/웹/블로그, Google Fact Check 병렬 검색 (설정된 것만 사용, 하나 실패해도 계속)
- trafilatura → BeautifulSoup → JSON-LD → OG → snippet 순 본문 수집 폴백
- TF-IDF/RapidFuzz 1차 + Gemini 2차 관련성 필터링
- canonical URL 정규화 + n-gram TF-IDF/RapidFuzz 기반 중복·재인용 군집화, 원출처 관계 추정(NetworkX)
- Gemini 기반 지지/반박/일부/근거부족/무관 판정 + 인용문이 실제 본문에 존재하는지 코드로 검증(폐기 로직 포함)
- 근거 품질 가중치(`config/scoring.yaml`) 기반 8단계 판정(confirmed~unverifiable)
- 종합 요약 + 후속 질문 정확히 3개
- 출처 관계 Plotly 그래프(실패 시 표로 대체)
- API 키 없이도 앱이 죽지 않고 "API 설정 필요" 안내로 처리

## 테스트

```bash
.venv\Scripts\python.exe -m pytest -q
```

23개 테스트 통과 확인됨 (키 저장/평문 미노출, Provider 캐시 무효화, 주장 분해, 관련성 필터, 중복 군집화,
인용문 검증, intent 주장 근거부족 처리, Provider 장애 회복력, 후속질문 3개 고정 등).

## 현재 실제 확인된 것 / 남은 한계

- 코드·Provider·UI는 전부 완성되어 있고, `streamlit run app.py`로 정상 기동(예외 없음, 화면 전환 정상)을
  `streamlit.testing.v1.AppTest`와 실제 서버 기동(HTTP 200)으로 확인했다.
- 실제 API 키가 하나도 없는 상태로 테스트했기 때문에, Gemini/Naver/FactCheck의
  **실제 외부 API 호출 성공 여부는 아직 검증하지 못했다.** API 설정 화면에서 키를 입력하고 "연결 테스트"
  버튼을 눌러 직접 확인해야 한다. Provider 코드 자체(요청 형식, 에러 분류, 재시도)는 각 API 공식 문서 기준으로
  작성했다.
- Streamlit Cloud 배포/Supabase 저장소는 코드 경로(`config.py`의 우선순위 로직)만 구현했고, 실제 Cloud 배포
  환경에서의 동작은 검증하지 않았다.
- 이미지 입력은 Gemini OCR만 사용하며, 역이미지 검색 기능은 제공하지 않는다.
