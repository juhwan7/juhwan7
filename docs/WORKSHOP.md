# JUHWAN / Systems in Motion

프로젝트의 실제 구조를 여섯 개의 미니어처 장치로 옮긴 GitHub 프로필입니다. 모든 장면은 코드로 그린 시각적 은유이며, 실시간 데이터 화면이나 실제 프로젝트 영상이라고 표시하지 않습니다.

## 여섯 개의 장치

| 번호 | 프로젝트 | 장치에 담은 구조 |
|---|---|---|
| 01 | Stock AutoResearch | 관측 → 사건 발견 → 후속 추적 |
| 02 | Korea Market Behavior Lab | 사실·추정·반례를 분리하는 검증 게이트 |
| 03 | Market Memo | 근거와 다음 확인사항을 남기는 기억 선반 |
| 04 | STARSHIP | 브라우저에서 계산하는 발사 경험 |
| 05 | Rotation Talk | 두 선택과 상대 재배정 |
| 06 | VOID HARVEST | 플레이어·적의 경쟁 자원과 변이 |

## 어떻게 그렸나

`scripts/render_lab.py`는 3차원 좌표를 사선 투시 평면에 투영하고, 박스·원통·레일·접시·그림자를 Pillow로 렌더링합니다. 1200×780, 80프레임, 프레임당 100ms, 총 8초의 GIF를 테마별로 만듭니다. 대표 장면은 무한 반복합니다. 모션은 날짜와 무관한 주기 함수로 재현됩니다.

```sh
python -m pip install -r requirements-profile.txt
python scripts/render_lab.py
python scripts/render_lab.py --force
```

첫 명령은 누락된 에셋만 생성합니다. 디자인을 변경했을 때만 `--force`를 사용합니다. 기본 자동화에서는 기존 GIF를 다시 만들지 않습니다. 전체 이미지 목록은 약 2MB이며 GIF는 테마별 1MB 미만입니다.

정적 테마 이미지는 `picture` 요소, 움직임은 GIF를 사용합니다. SVG는 정적 일일 표식에만 사용하며 README 안에서 JavaScript나 SVG 애니메이션을 실행하지 않습니다. 움직임을 피하고 싶은 경우 `assets/workshop-light.png` 또는 `assets/workshop-dark.png`를 볼 수 있습니다. GIF 자체는 사용자의 감소된 모션 설정을 자동으로 따르지 않습니다.

## 자동 갱신과 보존

기존 `scripts/update_profile.py` 진입점을 유지하고 `scripts/workshop_profile.py`로 수집·렌더링 책임을 분리했습니다.

- 한국 시간 날짜에 따라 여섯 개의 대표 프로젝트를 순환합니다. 같은 날짜에는 선택과 강조색이 같습니다.
- 기존 예약 유지: UTC 15:08(한국 시간 00:08)과 UTC 매 3시간 17분. 예약 실행은 지연되거나 누락될 수 있습니다.
- 공개 여부를 확인한 프로젝트만 조회합니다. 프로젝트당 최근 100개 커밋을 보고 새 상세 조회는 최대 4개로 제한합니다.
- 반복 관측·상태 갱신과 데이터/기억 전용 변경을 최근 변경 목록에서 제외합니다. 봇이 만든 실제 코드 수정은 제외하지 않습니다.
- 최근 변경은 최대 5개, 프로젝트별 최대 1개입니다. 코드·문서는 실제 변경 파일 경로로 구분합니다. 기능 개선 성공 여부를 커밋 메시지에서 추론하지 않습니다.
- 저장소별 장애를 격리하고 마지막 공개 스냅샷을 사용합니다. 조회 실패를 화면에 표시합니다. 404나 비공개 전환에서는 이전 내용을 재게시하지 않습니다.
- 데이터·설정·한국 시간 날짜의 지문이 같으면 파일과 생성 시각을 바꾸지 않습니다. 실패가 반복돼도 동일한 오류로 커밋을 반복 생성하지 않습니다.
- README의 `workshop:generated:start/end` 바깥은 자동 생성에서 보존됩니다. 첫 전환 때만 이전의 전면 생성 README를 교체했습니다.
- 콘텐츠 쓰기 권한은 기존 워크플로와 같습니다. 새 Secret, AI API, Pages 사이트를 추가하지 않았습니다.
- 실행을 직렬화하고 push 전에 rebase합니다. 충돌은 실패로 남기며 사람의 변경을 강제 덮어쓰지 않습니다.

```sh
python scripts/update_profile.py
python scripts/update_profile.py --offline
python scripts/update_profile.py --offline --date 2026-10-02
python -m unittest discover -s tests -v
```

오프라인 날짜 옵션은 미리보기용입니다. 실제 예약 실행은 실행 시각을 Asia/Seoul로 변환합니다. 캐시에 표시하는 시각은 해당 자료를 반영한 시각이며 방문 시점의 실시간 값이 아닙니다.

## 프로젝트 단계와 확인 범위

프로젝트 소개는 `profile.config.yml`에서 관리하는 검토된 문구입니다. 코드·문서의 단계가 바뀌면 근거와 함께 설정을 수정합니다. 커밋 빈도로 단계를 자동 변경하지 않습니다.

2026-10-01 검토 기준:

| 프로젝트 | 확인 자료 | 표현의 한계 |
|---|---|---|
| Stock AutoResearch | README, 이슈 패스트패스 코드, 공개 홈, 최근 작업 기록 | 수집·데이터 정상 여부를 보장하지 않음 |
| KMB | README, `quant.py`의 근거 검증, 공개 홈, 워크플로 | 특정 계좌의 실제 보유·의도 식별을 주장하지 않음 |
| Market Memo | README, 사이트 준비 코드, 공개 MkDocs 화면 | 자료의 모든 개별 주장을 재검증한 것은 아님 |
| STARSHIP | README, 자체 WebGL fallback 코드, 성공한 배포·Browser Smoke 기록 | 확인용 클라우드 브라우저는 WebGL 지원이 없어 실제 3D 재생 미검증 |
| Rotation Talk | README, 매칭 코드, Studio 개발 빌드 Releases | Roblox 게시·새 강당 화면·다중 접속 완료로 표현하지 않음 |
| Evo 3D Game | README, 게임 코드, 상태 JSON, 공개 진입 화면 | 실제 런타임과 현재 AI 실행 여부를 보장하지 않음 |

대표 프로젝트 외 저장소를 수정하거나 게임 개발 자동화를 재개하지 않았습니다. 기존 `lab-orbit.svg`는 새 README에서 참조하지 않으며 이전 디자인의 기록으로 남겼습니다.

## 검증

자동 테스트는 일일 선택, 동일 입력에서 무쓰기, 수동 문구 보존, 부분 실패, 반복 실패, 비공개/404 전환, 요청 한도, 의미 있는 변경 보존, Markdown escaping, 이미지 경로와 GIF 프레임·재생시간·변화를 확인합니다. GitHub의 실제 표시 검증과 자동화 실행 결과는 `docs/VERIFICATION.md`에 기록합니다.
