# 검증 기록

2026-10-01 — Systems in Motion 프로필 리디자인.

- 로컬 자동 테스트 14개 통과: 일일 전환, 동일 입력 무쓰기, 부분 장애, 비공개 제외, 404 캐시 제거, 요청 한도, 수동 문구 보존, 이미지 경로 등.
- 대표 GIF: 라이트/다크 각각 80프레임, 8초 반복, 서로 다른 프레임 확인, 1MB 미만.
- 두 테마의 대표 PNG를 직접 확인. 프로젝트 띠 이미지의 발사탑이 상단에서 잘리던 문제를 수정.
- 공개 링크: 시장 홈, KMB, Market Memo, STARSHIP 진입 화면, Evo 진입 화면, Rotation Talk의 최신 Studio 개발 빌드 확인.
- STARSHIP/Evo의 실제 3D 동작은 클라우드 브라우저의 WebGL 미지원으로 검증하지 못함. 프로필의 GIF 표시는 이 제한과 무관함.
- GitHub 공개 프로필에 새 README 표시 확인. 대표 GIF·일일 SVG·프로젝트 이미지 6개, 총 8개가 모두 로딩 완료(naturalWidth 1200)였으며 텍스트·체험 링크가 실제 DOM에 표시됨.
- 새 워크플로 [Systems in Motion 실행 #36861901706](https://github.com/juhwan7/juhwan7/actions/runs/36861901706) 성공. 설치·누락 에셋 확인·14개 테스트·공개 자료 수집·갱신 판단 단계 모두 성공.
- 실제 자동 수집 로그: `No content change; no files written.` 이어서 `No content change to publish.` 출력. 동일 자료에서 새 커밋을 생성하지 않았으며 README와 GIF가 유지됨.
- 공개 프로필의 실제 라이트 테마 화면: [검증 스크린샷](profile-preview.jpg).
- 다크 에셋은 로컬 이미지로 직접 확인했지만 GitHub 테마 전환 UI에서의 실제 표시 전환은 미검증. 실제 휴대폰 폭/기기 화면도 미검증이며 이미지 폭 100%와 별도 Markdown 텍스트로 대응함. 브라우저 재생 제한·모바일·다크 전환의 확인 범위를 완료로 과장하지 않음.

## 주요 변경 파일

- `README.md`, `profile.config.yml`: 새 구성, 실제 프로젝트 단계, 체험 링크, 테마별 이미지.
- `scripts/update_profile.py`, `scripts/workshop_profile.py`: 기존 진입점 유지, 수집·캐시·일일 선택·생성 분리.
- `scripts/render_lab.py`, `assets/workshop-*`, `assets/specimen-*`, `assets/spotlight-*`: 재현 가능한 장면과 두 테마.
- `.github/workflows/update-profile.yml`, `requirements-profile.txt`, `tests/test_profile.py`: 자동 갱신과 검증.
- `data/profile-state.json`, `.gitignore`, `docs/WORKSHOP.md`, 이 문서와 실제 화면: 스냅샷·제작 설명·검증 기록.
