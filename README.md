# AI Monitor

Claude AI 기반 서버 장애 자동 감지 및 조치 시스템.
Prometheus로 메트릭을 수집하고, Claude가 원인을 분석하여 Microsoft Teams로 알림을 발송합니다.
담당자는 Teams에서 버튼 클릭만으로 자동조치를 승인할 수 있습니다.

## 전체 흐름

```
Prometheus (메트릭 수집)
        ↓
ai-monitor (임계값 감지 + SSH 진단 수집)
        ↓
Claude AI (원인 분석 + 조치 명령어 생성)
        ↓
Teams 알림 (분석 결과 + 자동조치 버튼)
        ↓
담당자 승인 → SSH 자동 실행 → 결과 통보
```

## 구성 요소

| 서비스 | 설명 |
|--------|------|
| `ai-monitor` | 핵심 모니터링 애플리케이션 (Python) |
| `prometheus` | 메트릭 수집 서버 (포트 9090) |
| `grafana` | 메트릭 시각화 대시보드 (포트 3000) |

## 디렉토리 구조

```
.
├── ai-monitor/
│   ├── main.py                # 진입점. 메트릭 폴링 및 전체 흐름 제어
│   ├── prometheus_query.py    # Prometheus API 쿼리 (CPU/메모리/디스크/SWAP)
│   ├── analyzer.py            # Claude AI 장애 분석 (API 키 없으면 단순 분석으로 fallback)
│   ├── notifier.py            # Teams Adaptive Card 알림 발송
│   ├── remediator.py          # SSH 접속 후 진단 명령 실행 및 자동조치
│   ├── webhook_server.py      # 자동조치 확인/실행/취소 웹 서버 (Flask, 포트 8080)
│   ├── db.py                  # SQLite DB (장애 이력, 자동조치 pending 관리)
│   ├── config.yaml.example    # 설정 파일 예시
│   ├── requirements.txt       # Python 의존성
│   └── Dockerfile
├── prometheus/
│   └── prometheus.yml         # Prometheus 수집 대상 설정
├── docker-compose.yml
├── .env.example               # 환경변수 예시 (ANTHROPIC_API_KEY)
└── .gitignore
```

## 파일별 설명

### `ai-monitor/main.py`
전체 흐름을 제어하는 진입점.
60초(기본값) 주기로 Prometheus에서 메트릭을 수집하고, 임계값 초과 시 진단 → 분석 → 알림 → 자동조치 흐름을 실행합니다.
장애 발생/해소를 DB에 기록하고 중복 알림을 방지합니다.

### `ai-monitor/prometheus_query.py`
Prometheus HTTP API를 호출하여 메트릭을 수집합니다.
- CPU 사용률, 메모리 사용률, 디스크 사용률(전체 파티션 중 최대값), SWAP 사용률
- 노드 다운(up 메트릭) 감지

### `ai-monitor/analyzer.py`
장애 원인을 분석합니다.
- `ANTHROPIC_API_KEY` 환경변수가 있으면 Claude API로 심층 분석
- 없으면 임계값 기반 단순 분석으로 자동 fallback
- 과거 장애 이력과 SSH 진단 데이터를 함께 전달하여 원인 프로세스 특정
- 분석 결과: 심각도 / 원인 분석 / 권장 조치 / 자동조치 가능 여부 / 실행 명령어

### `ai-monitor/notifier.py`
Microsoft Teams로 알림을 발송합니다.
- 장애 알림: 심각도, 분석 결과, TOP 프로세스 현황, 자동조치 버튼 포함
- 장애 해소 알림: 소요 시간 포함
- 자동조치 완료 알림: 실행 명령어 및 실제 실행 결과(stdout) 포함

### `ai-monitor/remediator.py`
SSH로 대상 서버에 접속하여 명령어를 실행합니다.
- `collect_diagnostics()`: 장애 분석 전 ps, free, df 등 진단 데이터 수집
- `run()`: Claude가 생성한 명령어 또는 기본 조치 스크립트 실행, stdout/exit code 반환

### `ai-monitor/webhook_server.py`
자동조치 확인 웹 페이지를 제공하는 Flask 서버 (포트 8080).
- `GET  /action/<token>/confirm` : 실행될 명령어와 설명을 보여주는 확인 페이지
- `POST /action/<token>/run`     : 담당자 승인 후 실제 명령어 실행 (POST 전용, URL 스캐너 오발동 방지)
- `GET  /action/<token>/skip`    : 자동조치 취소

### `ai-monitor/db.py`
SQLite 기반 데이터 저장.
- `incidents` 테이블: 장애 발생/해소 이력, Claude 분석 내용, 조치 결과
- `pending_actions` 테이블: 담당자 승인 대기 중인 자동조치 관리

### `ai-monitor/config.yaml.example`
노드 및 알림 설정 예시.
실제 사용 시 `config.yaml`로 복사 후 수정 (config.yaml은 .gitignore 처리됨).

```yaml
callback_base_url: "http://공인IP또는도메인:8080"  # 담당자가 Teams 버튼을 누를 때 접근할 자동조치 서버 주소
                                                  # 비워두면 승인 절차 없이 Claude 판단만으로 자동조치가 즉시 실행됨

thresholds:
  cpu_percent: 85
  memory_percent: 90
  disk_percent: 90
  swap_percent: 90

nodes:
  서버이름:
    ip: "서버IP"
    owner: "담당자명"
    teams_mention_id: "Azure AD Object ID"
    teams_webhook: "Power Automate Webhook URL"
    ssh_user: "root"
    ssh_password: "패스워드"
```

### `prometheus/prometheus.yml`
Prometheus 수집 대상 설정.
`node-exporter` job에 모니터링할 서버의 `IP:9100`을 추가합니다.

### `.env.example`
환경변수 예시. `.env`로 복사 후 Anthropic API 키를 입력합니다.
API 키가 없어도 단순 분석 모드로 동작합니다.

```
ANTHROPIC_API_KEY=sk-ant-...
```

## 시작하기

1. **설정 파일 준비**
```bash
cp ai-monitor/config.yaml.example ai-monitor/config.yaml
cp .env.example .env
# config.yaml, .env 에 실제 값 입력
```

2. **node_exporter 설치** (모니터링 대상 서버마다)
```bash
# 각 대상 서버에서 실행
docker run -d \
  --name node-exporter \
  --restart unless-stopped \
  --net="host" \
  --pid="host" \
  -v "/:/host:ro,rslave" \
  prom/node-exporter:latest \
  --path.rootfs=/host
```

3. **서비스 시작**
```bash
docker compose up -d
```

4. **접속**
- Prometheus: `http://서버IP:9090`
- Grafana: `http://서버IP:3000` (admin / admin)
- 자동조치 서버: `http://서버IP:8080`

## 모니터링 항목

| 메트릭 | 기본 임계값 | 설명 |
|--------|------------|------|
| CPU 사용률 | 85% | 5분 평균 |
| 메모리 사용률 | 90% | 가용 메모리 기준 |
| 디스크 사용률 | 90% | 전체 파티션 중 최대값 |
| SWAP 사용률 | 90% | SwapTotal이 0인 노드 제외 |
| 노드 다운 | - | node_exporter 연결 불가 시 즉시 알림 |
