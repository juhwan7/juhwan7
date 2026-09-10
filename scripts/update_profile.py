from __future__ import annotations

import html
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


@dataclass
class DocumentUpdate:
    title: str
    path: str
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


def site_document_url(base_url: str, path: str) -> str:
    normalized = path.lstrip("./")
    if normalized.endswith("README.md"):
        normalized = normalized[: -len("README.md")]
    elif normalized.endswith(".md"):
        normalized = normalized[:-3] + "/"
    encoded = urllib.parse.quote(normalized, safe="/")
    return base_url.rstrip("/") + "/" + encoded.lstrip("/")


def interest_title(title: str, path: str) -> str:
    raw = title.strip().strip("`")
    if "/" in raw or raw.endswith(".md"):
        raw = Path(path).stem
    raw = raw.replace("-", " ")
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw


def fetch_source_links(config: dict) -> list[tuple[str, str]]:
    owner = config["owner"]
    interest_cfg = config["interests"]
    repo = interest_cfg["source_repo"]
    source_file = interest_cfg["source_file"]
    encoded = urllib.parse.quote(source_file, safe="/")
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{encoded}"
    text = request(raw_url).decode("utf-8")

    include_paths = interest_cfg.get("include_paths", [])
    exclude_paths = interest_cfg.get("exclude_paths", [])

    results: list[tuple[str, str]] = []
    seen_paths: set[str] = set()
    for title, path in re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text):
        normalized = path.lstrip("./")
        if not any(normalized.startswith(prefix) for prefix in include_paths):
            continue
        if any(normalized.startswith(prefix) for prefix in exclude_paths):
            continue
        if normalized.endswith("README.md"):
            continue
        if normalized in seen_paths:
            continue
        seen_paths.add(normalized)
        results.append((interest_title(title, normalized), normalized))

    return results


def source_document_url(config: dict, path: str) -> str:
    owner = config["owner"]
    cfg = config["interests"]
    repo = cfg["source_repo"]
    site_url = cfg.get("site_url")
    if site_url:
        return site_document_url(site_url, path)
    return github_blob_url(owner, repo, path)


def fetch_interests(config: dict) -> list[tuple[str, str]]:
    limit = int(config["interests"].get("limit", 5))
    results: list[tuple[str, str]] = []
    seen_titles: set[str] = set()

    for display, normalized in fetch_source_links(config):
        if not display or display in seen_titles:
            continue
        seen_titles.add(display)
        results.append((display, source_document_url(config, normalized)))
        if len(results) >= limit:
            break
    return results


def fetch_recent_documents(config: dict, token: str | None) -> list[DocumentUpdate]:
    owner = config["owner"]
    cfg = config["interests"]
    repo = cfg["source_repo"]
    limit = int(cfg.get("recent_documents_limit", cfg.get("limit", 5)))
    updates: list[DocumentUpdate] = []

    for title, path in fetch_source_links(config):
        encoded_path = urllib.parse.quote(path, safe="")
        api_url = f"https://api.github.com/repos/{owner}/{repo}/commits?path={encoded_path}&per_page=1"
        commits = api_json(api_url, token)
        if not commits:
            continue
        commit = commits[0]
        commit_data = commit.get("commit") or {}
        date_value = (
            (commit_data.get("committer") or {}).get("date")
            or (commit_data.get("author") or {}).get("date")
        )
        if not date_value:
            continue
        updates.append(
            DocumentUpdate(
                title=title,
                path=path,
                url=source_document_url(config, path),
                happened_at=parse_datetime(date_value),
            )
        )

    updates.sort(key=lambda item: item.happened_at, reverse=True)
    return updates[:limit]


def select_recent_activities(
    activities: list[Activity], limit: int, max_per_repo: int
) -> list[Activity]:
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


def markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def project_cards(
    config: dict, activities: list[Activity], now_days: int
) -> list[str]:
    owner = config["owner"]
    rows: list[str] = ["<table>", "<tr>"]

    for item in config["tracked_repositories"][:2]:
        repo = item["repo"]
        repo_activities = [a for a in activities if a.repo == repo]
        cutoff = datetime.now(timezone.utc) - timedelta(days=now_days)
        recent = [a for a in repo_activities if a.happened_at >= cutoff]
        latest = max(repo_activities, key=lambda a: a.happened_at, default=None)

        title = html.escape(str(item["title"]))
        description = html.escape(str(item["description"]))
        repo_url = html.escape(str(item.get("url", f"https://github.com/{owner}/{repo}")), quote=True)
        live_url = item.get("live_url")
        live_label = html.escape(str(item.get("live_label", "Live")))

        links = []
        if live_url:
            links.append(
                f'<a href="{html.escape(str(live_url), quote=True)}"><b>{live_label} ↗</b></a>'
            )
        links.append(f'<a href="{repo_url}">GitHub</a>')

        latest_line = f"최근 {now_days}일 주요 작업 {len(recent)}개"
        if latest:
            latest_line += (
                " · 최근: "
                f'<a href="{html.escape(latest.url, quote=True)}">'
                f"{html.escape(latest.message)}</a>"
            )

        rows.extend(
            [
                '<td width="50%" valign="top">',
                f"<h3>{title}</h3>",
                f"<p>{description}</p>",
                f"<p>{' · '.join(links)}</p>",
                f"<sub>{latest_line}</sub>",
                "</td>",
            ]
        )

    rows.extend(["</tr>", "</table>"])
    return rows


def render(
    config: dict,
    activities: list[Activity],
    interests: list[tuple[str, str]],
    recent_documents: list[DocumentUpdate],
) -> str:
    owner = config["owner"]
    tz = ZoneInfo(config.get("timezone", "Asia/Seoul"))
    profile_cfg = config.get("profile", {})
    tagline = profile_cfg.get(
        "tagline", "시장을 읽고, 기록하고, 필요한 도구를 직접 만듭니다."
    )
    subtitle = profile_cfg.get(
        "subtitle", "주식시장 리서치 · 데이터 대시보드 · 자동화 · 바이브코딩"
    )

    now_cfg = config.get("now", {})
    now_days = int(now_cfg.get("lookback_days", 7))

    recent_cfg = config.get("recent_activity", {})
    activity_limit = int(recent_cfg.get("limit", 6))
    max_per_repo = int(recent_cfg.get("max_per_repo", activity_limit))
    latest_activities = select_recent_activities(activities, activity_limit, max_per_repo)

    market_memo = next(
        (item for item in config["tracked_repositories"] if item["repo"] == "market-memo"),
        {},
    )
    market_memo_live = market_memo.get(
        "live_url", "https://juhwan7.github.io/market-memo/"
    )

    lines: list[str] = []
    lines.extend(
        [
            '<div align="center">',
            "",
            "# Juhwan",
            "",
            f"### {tagline}",
            "",
            f"{subtitle}",
            "",
            f'<a href="{market_memo_live}"><img src="https://img.shields.io/badge/Market%20Memo-LIVE-111827?style=for-the-badge&logo=githubpages&logoColor=white" alt="Market Memo"></a>',
            f'<a href="https://github.com/{owner}/vibe-coding-playground"><img src="https://img.shields.io/badge/Market%20Dashboard-GitHub-24292F?style=for-the-badge&logo=github&logoColor=white" alt="Market Dashboard"></a>',
            "",
            "</div>",
            "",
            "---",
            "",
            "## 지금 만드는 것",
            "",
        ]
    )

    lines.extend(project_cards(config, activities, now_days))
    lines.extend(["", "## 최근 흐름", ""])

    if latest_activities:
        lines.append("| 시각 | 프로젝트 | 작업 |")
        lines.append("|---|---|---|")
        repo_titles = {
            item["repo"]: item["title"] for item in config["tracked_repositories"]
        }
        for activity in latest_activities:
            repo_url = f"https://github.com/{owner}/{activity.repo}"
            repo_title = repo_titles.get(activity.repo, activity.repo)
            lines.append(
                f"| {relative_time(activity.happened_at, tz)} | "
                f"[{markdown_cell(str(repo_title))}]({repo_url}) | "
                f"[{markdown_cell(activity.message)}]({activity.url}) |"
            )
    else:
        lines.append("최근 표시할 주요 작업이 없습니다.")

    lines.extend(["", "## 최근 리서치", ""])
    lines.append(
        f"> 전체 자료는 **[Market Memo 웹사이트]({market_memo_live})**에서 검색하고 읽을 수 있습니다."
    )
    lines.append("")

    if recent_documents:
        lines.append("| 업데이트 | 자료 |")
        lines.append("|---|---|")
        for document in recent_documents:
            lines.append(
                f"| {relative_time(document.happened_at, tz)} | "
                f"[{markdown_cell(document.title)}]({document.url}) |"
            )
    else:
        lines.append("최근 업데이트된 자료가 없습니다.")

    lines.extend(["", "## 요즘 보는 것", ""])
    if interests:
        lines.append(" · ".join(f"[{title}]({url})" for title, url in interests))
    else:
        lines.append("아직 표시할 관심 주제가 없습니다.")

    lines.extend(
        [
            "",
            "## 사용하는 도구",
            "",
            '<p align="left">',
            '<img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"> ',
            '<img src="https://img.shields.io/badge/Java-ED8B00?style=flat-square&logo=openjdk&logoColor=white" alt="Java"> ',
            '<img src="https://img.shields.io/badge/Spring%20Boot-6DB33F?style=flat-square&logo=springboot&logoColor=white" alt="Spring Boot"> ',
            '<img src="https://img.shields.io/badge/GitHub%20Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white" alt="GitHub Actions"> ',
            '<img src="https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker"> ',
            '<img src="https://img.shields.io/badge/Raspberry%20Pi-A22846?style=flat-square&logo=raspberrypi&logoColor=white" alt="Raspberry Pi"> ',
            '<img src="https://img.shields.io/badge/AWS-232F3E?style=flat-square&logo=amazonwebservices&logoColor=white" alt="AWS">',
            "</p>",
            "",
            "## 만드는 방식",
            "",
            "- **필요하면 직접 만듭니다.** 반복해서 확인하는 정보는 대시보드나 자동화로 바꿉니다.",
            "- **기록은 다음 판단을 위한 데이터로 남깁니다.** 뉴스 한 줄보다 배경·원인·다음 단계를 연결합니다.",
            "- **작게 만들고 계속 개선합니다.** 실제로 써보고 불편한 부분부터 고칩니다.",
            "",
            "---",
            "",
        ]
    )

    if latest_activities:
        latest_source_time = max(a.happened_at for a in latest_activities).astimezone(tz)
        lines.append(
            f"<sub>최근 활동 데이터 기준: {latest_source_time:%Y-%m-%d %H:%M} KST · "
            "GitHub Actions가 주기적으로 자동 갱신합니다.</sub>"
        )
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
    recent_documents = fetch_recent_documents(config, token)
    content = render(config, activities, interests, recent_documents)
    README_PATH.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
