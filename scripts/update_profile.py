from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "profile.config.yml"
README_PATH = ROOT / "README.md"


@dataclass
class Activity:
    repo: str
    message: str
    url: str
    happened_at: datetime


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def request(url: str, token: str | None = None) -> bytes:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "juhwan7-profile-dashboard",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read()


def api_json(url: str, token: str | None = None):
    return json.loads(request(url, token).decode("utf-8"))


def clean_message(message: str) -> str:
    first_line = message.splitlines()[0].strip()
    first_line = re.sub(
        r"^(feat|fix|docs|refactor|chore|style|perf|test|build|ci)(\([^)]*\))?:\s*",
        "",
        first_line,
        flags=re.IGNORECASE,
    )
    return first_line.strip()


def should_ignore(message: str, patterns: list[str]) -> bool:
    lowered = message.lower()
    return any(str(pattern).lower() in lowered for pattern in patterns)


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fetch_repo_activities(
    owner: str,
    repo: str,
    token: str | None,
    since: datetime,
    ignore_patterns: list[str],
) -> list[Activity]:
    since_param = urllib.parse.quote(since.astimezone(timezone.utc).isoformat())
    url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=100&since={since_param}"
    commits = api_json(url, token)
    activities: list[Activity] = []

    for item in commits:
        author_login = (item.get("author") or {}).get("login")
        author_name = ((item.get("commit") or {}).get("author") or {}).get("name", "")
        if author_login and author_login != owner:
            continue
        if not author_login and owner.lower() not in author_name.lower():
            continue

        commit = item.get("commit") or {}
        raw_message = commit.get("message", "")
        message = clean_message(raw_message)
        if not message or should_ignore(message, ignore_patterns):
            continue

        date_value = (commit.get("author") or {}).get("date")
        if not date_value:
            continue

        activities.append(
            Activity(
                repo=repo,
                message=message,
                url=item.get("html_url", f"https://github.com/{owner}/{repo}"),
                happened_at=parse_datetime(date_value),
            )
        )

    return activities


def dedupe_activities(activities: list[Activity]) -> list[Activity]:
    latest_by_key: dict[tuple[str, str], Activity] = {}
    for activity in activities:
        key = (activity.repo, activity.message)
        current = latest_by_key.get(key)
        if current is None or activity.happened_at > current.happened_at:
            latest_by_key[key] = activity
    return list(latest_by_key.values())


def relative_time(value: datetime, tz: ZoneInfo) -> str:
    local = value.astimezone(tz)
    now = datetime.now(tz)
    if local.date() == now.date():
        return f"오늘 {local:%H:%M}"
    if local.date() == (now - timedelta(days=1)).date():
        return f"어제 {local:%H:%M}"
    return f"{local.month}월 {local.day}일"


def github_blob_url(owner: str, repo: str, path: str) -> str:
    encoded = urllib.parse.quote(path, safe="/")
    return f"https://github.com/{owner}/{repo}/blob/main/{encoded}"


def interest_title(title: str, path: str) -> str:
    raw = title.strip().strip("`")
    if "/" in raw or raw.endswith(".md"):
        raw = Path(path).stem
    raw = raw.replace("-", " ")
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def fetch_interests(config: dict) -> list[tuple[str, str]]:
    owner = config["owner"]
    interest_cfg = config["interests"]
    repo = interest_cfg["source_repo"]
    source_file = interest_cfg["source_file"]
    encoded = urllib.parse.quote(source_file, safe="/")
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{encoded}"
    text = request(raw_url).decode("utf-8")

    include_paths = interest_cfg.get("include_paths", [])
    exclude_paths = interest_cfg.get("exclude_paths", [])
    limit = int(interest_cfg.get("limit", 5))

    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    for title, path in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text):
        normalized = path.lstrip("./")
        if not any(normalized.startswith(prefix) for prefix in include_paths):
            continue
        if any(normalized.startswith(prefix) for prefix in exclude_paths):
            continue
        if normalized.endswith("README.md"):
            continue

        display = interest_title(title, normalized)
        if not display or display in seen:
            continue
        seen.add(display)
        results.append((display, github_blob_url(owner, repo, normalized)))
        if len(results) >= limit:
            break

    return results


def select_recent_activities(activities: list[Activity], limit: int, max_per_repo: int) -> list[Activity]:
    selected: list[Activity] = []
    repo_counts: defaultdict[str, int] = defaultdict(int)
    for activity in sorted(activities, key=lambda a: a.happened_at, reverse=True):
        if repo_counts[activity.repo] >= max_per_repo:
            continue
        selected.append(activity)
        repo_counts[activity.repo] += 1
        if len(selected) >= limit:
            break
    return selected


def render(config: dict, activities: list[Activity], interests: list[tuple[str, str]]) -> str:
    owner = config["owner"]
    tz = ZoneInfo(config.get("timezone", "Asia/Seoul"))
    now_cfg = config.get("now", {})
    now_days = int(now_cfg.get("lookback_days", 7))
    now_cutoff = datetime.now(timezone.utc) - timedelta(days=now_days)

    repo_cfg = {item["repo"]: item for item in config["tracked_repositories"]}
    project_rows = []
    for repo, meta in repo_cfg.items():
        repo_activities = [a for a in activities if a.repo == repo]
        recent = [a for a in repo_activities if a.happened_at >= now_cutoff]
        latest = max(repo_activities, key=lambda a: a.happened_at, default=None)
        project_rows.append((repo, meta, len(recent), latest))

    project_rows.sort(
        key=lambda row: (
            row[2],
            row[3].happened_at.timestamp() if row[3] else 0,
        ),
        reverse=True,
    )
    max_projects = int(now_cfg.get("max_projects", 2))
    project_rows = project_rows[:max_projects]

    recent_cfg = config.get("recent_activity", {})
    activity_limit = int(recent_cfg.get("limit", 5))
    max_per_repo = int(recent_cfg.get("max_per_repo", activity_limit))
    latest_activities = select_recent_activities(activities, activity_limit, max_per_repo)

    lines: list[str] = []
    lines.append("# Juhwan")
    lines.append("")
    lines.append("> 요즘 만들고 있는 것과 최근 관심사를 자동으로 정리하는 GitHub 프로필입니다.")
    lines.append("")
    lines.append("## 🔥 지금 하고 있는 것")
    lines.append("")

    for repo, meta, count, latest in project_rows:
        lines.append(f"### [{meta['title']}]({meta['url']})")
        lines.append(meta["description"])
        if latest:
            lines.append(
                f"`최근 {now_days}일 주요 작업 {count}개` · 최근 작업: "
                f"[{latest.message}]({latest.url})"
            )
        else:
            lines.append(f"`최근 {now_days}일 주요 작업 없음`")
        lines.append("")

    lines.append("## 🛠 최근 GitHub 작업")
    lines.append("")
    if latest_activities:
        lines.append("| 시각 | 저장소 | 작업 |")
        lines.append("|---|---|---|")
        for activity in latest_activities:
            repo_url = f"https://github.com/{owner}/{activity.repo}"
            lines.append(
                f"| {relative_time(activity.happened_at, tz)} | "
                f"[{activity.repo}]({repo_url}) | [{activity.message}]({activity.url}) |"
            )
    else:
        lines.append("최근 표시할 주요 작업이 없습니다.")
    lines.append("")

    lines.append("## 👀 최근 관심 주제")
    lines.append("")
    if interests:
        for title, url in interests:
            lines.append(f"- [{title}]({url})")
    else:
        lines.append("- 아직 표시할 관심 주제가 없습니다.")
    lines.append("")

    lines.append("## 📌 주요 프로젝트")
    lines.append("")
    for item in config["tracked_repositories"]:
        lines.append(f"- **[{item['title']}]({item['url']})** — {item['description']}")
    lines.append("")

    if latest_activities:
        latest_source_time = max(a.happened_at for a in latest_activities).astimezone(tz)
        lines.append(f"<sub>최근 활동 데이터 기준: {latest_source_time:%Y-%m-%d %H:%M} KST</sub>")
        lines.append("")
    lines.append("<!-- 이 README는 GitHub Actions가 실제 데이터가 바뀔 때만 자동 갱신합니다. -->")

    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    config = load_config()
    owner = config["owner"]
    token = os.getenv("GITHUB_TOKEN")
    recent_cfg = config.get("recent_activity", {})
    lookback_days = int(recent_cfg.get("lookback_days", 14))
    ignore_patterns = recent_cfg.get("ignore_messages", [])
    since = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    activities: list[Activity] = []
    for item in config["tracked_repositories"]:
        activities.extend(
            fetch_repo_activities(
                owner=owner,
                repo=item["repo"],
                token=token,
                since=since,
                ignore_patterns=ignore_patterns,
            )
        )

    activities = dedupe_activities(activities)
    interests = fetch_interests(config)
    content = render(config, activities, interests)
    README_PATH.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
