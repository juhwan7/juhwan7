from __future__ import annotations

import html
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "profile.config.yml"
README_PATH = ROOT / "README.md"
ASSET_DIR = ROOT / "assets"
ORBIT_PATH = ASSET_DIR / "lab-orbit.svg"


@dataclass
class Activity:
    repo: str
    message: str
    url: str
    happened_at: datetime


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def request_json(url: str, token: str | None = None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "juhwan7-living-profile",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def clean_message(message: str) -> str:
    line = message.splitlines()[0].strip()
    line = re.sub(
        r"^(feat|fix|docs|refactor|chore|style|perf|test|build|ci)(\([^)]*\))?:\s*",
        "",
        line,
        flags=re.IGNORECASE,
    )
    return line.strip()


def fetch_repo_activity(owner: str, repo: str, since: datetime, token: str | None) -> list[Activity]:
    since_param = urllib.parse.quote(since.astimezone(timezone.utc).isoformat())
    result: list[Activity] = []
    page = 1
    while page <= 20:
        url = (
            f"https://api.github.com/repos/{owner}/{repo}/commits"
            f"?per_page=100&page={page}&since={since_param}"
        )
        items = request_json(url, token)
        if not items:
            break

        for item in items:
            commit = item.get("commit") or {}
            raw_message = commit.get("message", "")
            message = clean_message(raw_message)
            date_value = (
                (commit.get("committer") or {}).get("date")
                or (commit.get("author") or {}).get("date")
            )
            if not message or not date_value:
                continue
            result.append(
                Activity(
                    repo=repo,
                    message=message,
                    url=item.get("html_url", f"https://github.com/{owner}/{repo}"),
                    happened_at=parse_datetime(date_value),
                )
            )

        if len(items) < 100:
            break
        page += 1
    return result


def relative_time(value: datetime, tz: ZoneInfo, now: datetime) -> str:
    local = value.astimezone(tz)
    delta = now - local
    if delta < timedelta(hours=1):
        minutes = max(1, int(delta.total_seconds() // 60))
        return f"{minutes}분 전"
    if delta < timedelta(days=1):
        return f"{int(delta.total_seconds() // 3600)}시간 전"
    if delta < timedelta(days=7):
        return f"{delta.days}일 전"
    return f"{local:%m-%d}"


def stage_for(latest: datetime | None, now_utc: datetime) -> tuple[str, str]:
    if latest is None:
        return "SLEEP", "최근 활동 없음"
    age = now_utc - latest
    if age <= timedelta(days=1):
        return "HOT", "24시간 내 변화"
    if age <= timedelta(days=3):
        return "EVOLVING", "3일 내 변화"
    if age <= timedelta(days=7):
        return "ACTIVE", "7일 내 변화"
    return "HIBERNATE", "다음 변이 대기"


def project_stats(config: dict, activities: list[Activity], now_utc: datetime) -> list[dict]:
    by_repo: dict[str, list[Activity]] = {}
    for activity in activities:
        by_repo.setdefault(activity.repo, []).append(activity)

    stats: list[dict] = []
    for project in config["projects"]:
        items = sorted(by_repo.get(project["repo"], []), key=lambda a: a.happened_at, reverse=True)
        latest = items[0].happened_at if items else None
        count_24h = sum(a.happened_at >= now_utc - timedelta(days=1) for a in items)
        count_7d = sum(a.happened_at >= now_utc - timedelta(days=7) for a in items)
        stage, stage_note = stage_for(latest, now_utc)
        stats.append(
            {
                **project,
                "latest": latest,
                "count_24h": count_24h,
                "count_7d": count_7d,
                "stage": stage,
                "stage_note": stage_note,
            }
        )
    return stats


def safe_text(value: str) -> str:
    return html.escape(str(value), quote=True)


def render_orbit(
    owner: str,
    stats: list[dict],
    featured_repo: str,
    evolution_day: int,
    accent: str,
    accent2: str,
    generated_at: datetime,
) -> str:
    width, height = 1200, 470
    center_x, center_y = 600, 235
    positions = [
        (165, 112),
        (600, 78),
        (1035, 112),
        (1035, 358),
        (600, 392),
        (165, 358),
    ]

    nodes: list[str] = []
    for index, project in enumerate(stats):
        x, y = positions[index % len(positions)]
        featured = project["repo"] == featured_repo
        radius = 30 + min(int(project["count_7d"]), 12) * 1.2 + (9 if featured else 0)
        stroke = accent if featured else "#aab0bc"
        fill = "#fff7ed" if featured else "#ffffff"
        dash = "" if featured else ' stroke-dasharray="5 7"'
        title = safe_text(project["title"])
        lane = safe_text(project.get("lane", "LAB"))
        count = int(project["count_7d"])
        nodes.append(
            f'<line x1="{center_x}" y1="{center_y}" x2="{x}" y2="{y}" '
            f'stroke="#d7dbe3" stroke-width="2" stroke-dasharray="4 8" class="drift"/>'
        )
        if featured:
            nodes.append(
                f'<circle cx="{x}" cy="{y}" r="{radius + 10:.1f}" fill="none" '
                f'stroke="{accent2}" stroke-width="2" opacity=".35" class="pulse"/>'
            )
        nodes.extend(
            [
                f'<circle cx="{x}" cy="{y}" r="{radius:.1f}" fill="{fill}" stroke="{stroke}" '
                f'stroke-width="{4 if featured else 2}"{dash}/>',
                f'<text x="{x}" y="{y - 5}" text-anchor="middle" class="nodeTitle">{title}</text>',
                f'<text x="{x}" y="{y + 17}" text-anchor="middle" class="nodeMeta">{lane} · {count} mutations/7d</text>',
            ]
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#fafaf7"/>
      <stop offset="100%" stop-color="#f0f3f7"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="7" stdDeviation="9" flood-color="#111827" flood-opacity=".10"/>
    </filter>
    <style>
      .title {{ font: 700 29px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: #111827; letter-spacing: 1px; }}
      .meta {{ font: 500 15px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: #667085; }}
      .nodeTitle {{ font: 700 13px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; fill: #111827; }}
      .nodeMeta {{ font: 500 10px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; fill: #667085; }}
      .pulse {{ transform-box: fill-box; transform-origin: center; animation: pulse 2.8s ease-in-out infinite; }}
      .drift {{ animation: dash 12s linear infinite; }}
      @keyframes pulse {{ 0%,100% {{ opacity:.18; transform:scale(.92); }} 50% {{ opacity:.58; transform:scale(1.08); }} }}
      @keyframes dash {{ to {{ stroke-dashoffset:-120; }} }}
      @media (prefers-reduced-motion: reduce) {{ .pulse,.drift {{ animation:none; }} }}
    </style>
  </defs>
  <rect x="0" y="0" width="{width}" height="{height}" rx="28" fill="url(#bg)"/>
  <circle cx="{center_x}" cy="{center_y}" r="115" fill="#ffffff" stroke="{accent}" stroke-width="5" filter="url(#shadow)"/>
  <circle cx="{center_x}" cy="{center_y}" r="128" fill="none" stroke="{accent2}" stroke-width="2" opacity=".28" class="pulse"/>
  <text x="{center_x}" y="{center_y - 18}" text-anchor="middle" class="title">JUHWAN / LIVING LAB</text>
  <text x="{center_x}" y="{center_y + 12}" text-anchor="middle" class="meta">EVOLUTION DAY {evolution_day:03d}</text>
  <text x="{center_x}" y="{center_y + 39}" text-anchor="middle" class="meta">observe → build → falsify → recover → evolve</text>
  {''.join(nodes)}
  <text x="35" y="440" class="meta">generated {generated_at:%Y-%m-%d %H:%M} KST · github.com/{owner}</text>
</svg>
'''


def render_readme(
    config: dict,
    stats: list[dict],
    activities: list[Activity],
    now: datetime,
    evolution_day: int,
    featured: dict,
    question: str,
    accent: str,
) -> str:
    owner = config["owner"]
    date_key = now.strftime("%Y%m%d")
    commits_24h = sum(p["count_24h"] for p in stats)
    commits_7d = sum(p["count_7d"] for p in stats)
    active_7d = sum(p["count_7d"] > 0 for p in stats)
    freshest = max((p for p in stats if p["latest"]), key=lambda p: p["latest"], default=None)

    recent = sorted(activities, key=lambda a: a.happened_at, reverse=True)
    selected: list[Activity] = []
    per_repo: dict[str, int] = {}
    limit = int(config.get("refresh", {}).get("recent_limit", 8))
    max_per_repo = int(config.get("refresh", {}).get("recent_max_per_repo", 2))
    for item in recent:
        if per_repo.get(item.repo, 0) >= max_per_repo:
            continue
        selected.append(item)
        per_repo[item.repo] = per_repo.get(item.repo, 0) + 1
        if len(selected) >= limit:
            break

    titles = {p["repo"]: p["title"] for p in stats}
    lines: list[str] = [
        '<div align="center">',
        "",
        f'<img src="https://raw.githubusercontent.com/{owner}/{owner}/main/assets/lab-orbit.svg?v={date_key}" alt="Juhwan Living Lab project constellation" width="100%">',
        "",
        f"### EVOLUTION DAY {evolution_day:03d} — 이 프로필은 완성본이 아니라 계속 변하는 실험실입니다.",
        "",
        f'<img src="https://img.shields.io/badge/24h%20mutations-{commits_24h}-{accent.lstrip("#")}?style=flat-square" alt="24h mutations"> '
        f'<img src="https://img.shields.io/badge/7d%20mutations-{commits_7d}-111827?style=flat-square" alt="7d mutations"> '
        f'<img src="https://img.shields.io/badge/active%20organisms-{active_7d}%2F{len(stats)}-475467?style=flat-square" alt="active projects">',
        "",
        "시장 행동을 관찰하고, AI가 서로의 판단을 반증하게 만들고, 실패를 기록해 다음 시스템이 같은 실수를 반복하지 않게 만듭니다.",
        "",
        "</div>",
        "",
        "---",
        "",
        "## 오늘의 변이",
        "",
        f"**오늘 전면에 나오는 프로젝트: [{featured['title']}](https://github.com/{owner}/{featured['repo']})**  ",
        f"{featured['description']}",
    ]
    if featured.get("live_url"):
        lines.append(f"→ [지금 보기]({featured['live_url']})")
    lines.extend(
        [
            "",
            f"> 오늘의 질문: **{question}**",
            "",
            "매일 KST 날짜가 바뀌면 전면 프로젝트·강조 색·프로젝트 궤도의 초점이 한 번 바뀝니다. 실제 프로젝트 활동은 별도로 주기적으로 반영됩니다.",
            "",
            "## LAB PULSE",
            "",
            "| 24시간 변이 | 7일 변이 | 7일 내 살아있는 프로젝트 | 가장 최근에 움직인 프로젝트 |",
            "|---:|---:|---:|---|",
            f"| **{commits_24h}** | **{commits_7d}** | **{active_7d}/{len(stats)}** | **{freshest['title'] if freshest else '—'}** |",
            "",
            "## PROJECT ORGANISMS",
            "",
            "| 프로젝트 | 생존 상태 | 최근 7일 | 역할 |",
            "|---|---|---:|---|",
        ]
    )

    for project in stats:
        repo_url = f"https://github.com/{owner}/{project['repo']}"
        title = project["title"]
        if project.get("live_url"):
            title_cell = f"[{title}]({project['live_url']}) · [repo]({repo_url})"
        else:
            title_cell = f"[{title}]({repo_url})"
        stage = project["stage"]
        latest = relative_time(project["latest"], ZoneInfo(config["timezone"]), now) if project["latest"] else "—"
        lines.append(
            f"| {title_cell}<br><sub>{project['description']}</sub> | **{stage}**<br><sub>{latest}</sub> | "
            f"**{project['count_7d']}** | {project.get('lane', 'LAB')} |"
        )

    lines.extend(["", "## LATEST MUTATIONS", ""])
    if selected:
        lines.extend(["| 시각 | 프로젝트 | 실제 변경 |", "|---|---|---|"])
        tz = ZoneInfo(config["timezone"])
        for item in selected:
            title = titles.get(item.repo, item.repo)
            lines.append(
                f"| {relative_time(item.happened_at, tz, now)} | [{title}](https://github.com/{owner}/{item.repo}) | "
                f"[{item.message.replace('|', '¦')}]({item.url}) |"
            )
    else:
        lines.append("최근 표시할 커밋이 없습니다.")

    lines.extend(
        [
            "",
            "## PROJECT DNA",
            "",
            "~~~text",
            "OBSERVE  →  HYPOTHESIS  →  BUILD  →  FALSIFY  →  RECOVER  →  ARCHIVE",
            "   ↑                                                           ↓",
            "   └────────────────────── next mutation ──────────────────────┘",
            "~~~",
            "",
            "프로젝트를 한 번 만들고 끝내는 대신, 관찰 → 가설 → 구현 → 반증 → 복구 → 실패/결정 기록의 루프를 남깁니다. "
            "그래서 저장소는 코드 보관함보다 다음 AI와 다음 실험이 이어받는 장기 기억에 가깝습니다.",
            "",
            "<details>",
            "<summary><b>TOOLS / MATERIALS</b></summary>",
            "",
            "Python · Java · Spring Boot · JavaScript · Three.js · Roblox/Luau · GitHub Actions · Docker · Raspberry Pi · AWS",
            "",
            "</details>",
            "",
            "---",
            "",
            f"<sub>Living Profile · {now:%Y-%m-%d %H:%M} KST 생성 · 활동 변화는 약 3시간 간격, Daily Mutation은 하루 1회 전환</sub>",
            "",
            "<!-- generated by scripts/update_profile.py; edit profile.config.yml rather than generated sections -->",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    config = load_config()
    owner = config["owner"]
    tz = ZoneInfo(config.get("timezone", "Asia/Seoul"))
    now = datetime.now(tz)
    now_utc = now.astimezone(timezone.utc)
    token = os.getenv("GITHUB_TOKEN")

    lookback_days = int(config.get("refresh", {}).get("lookback_days", 14))
    since = now_utc - timedelta(days=lookback_days)

    activities: list[Activity] = []
    for project in config["projects"]:
        activities.extend(fetch_repo_activity(owner, project["repo"], since, token))

    stats = project_stats(config, activities, now_utc)
    seed_value = config["seed_date"]
    seed = seed_value if isinstance(seed_value, date) else date.fromisoformat(str(seed_value))
    evolution_day = max(1, (now.date() - seed).days + 1)
    featured = stats[(evolution_day - 1) % len(stats)]
    questions = config["daily_questions"]
    question = questions[(evolution_day - 1) % len(questions)]
    palettes = config["daily_palettes"]
    palette = palettes[(evolution_day - 1) % len(palettes)]
    accent, accent2 = palette["accent"], palette["accent2"]

    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    ORBIT_PATH.write_text(
        render_orbit(owner, stats, featured["repo"], evolution_day, accent, accent2, now),
        encoding="utf-8",
    )
    README_PATH.write_text(
        render_readme(config, stats, activities, now, evolution_day, featured, question, accent),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
