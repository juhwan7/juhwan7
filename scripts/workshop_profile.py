"""Public collection and idempotent, partial-failure-safe README generation."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import yaml

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- workshop:generated:start -->"
END = "<!-- workshop:generated:end -->"

def request_json(url, token=None):
    headers={"Accept":"application/vnd.github+json","User-Agent":"juhwan7-workshop", "X-GitHub-Api-Version":"2022-11-28"}
    if token: headers["Authorization"]="Bearer "+token
    with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=12) as r: return json.load(r)

def atomic_write(path, text):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+".tmp")
    temp.write_text(text,encoding="utf-8")
    temp.replace(path)

def read_json(path, default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError,json.JSONDecodeError): return default

def daily_focus(config, now):
    offset=(now.date()-date.fromisoformat(str(config["seed_date"]))).days
    return offset % len(config["projects"])

def is_routine(message):
    return bool(re.search(r"^(observe:|sensor:|heartbeat:|recovery: refresh|product: refresh market intelligence|chore: (update|refresh|mutate|sync)|.*record .*checkpoint|.*record .*heartbeat|.*record .*observation|.*update .*snapshot|.*refresh .*dashboard|Merge (branch|pull request))",message,re.I))

def category(paths):
    if paths and all(p.startswith(("data/","memory/")) for p in paths): return "기록 갱신"
    if paths and all(p.endswith((".md",".txt")) for p in paths): return "문서 변경"
    if paths and any(p.endswith((".py",".js",".mjs",".luau",".html",".css")) for p in paths): return "코드 변경"
    return "변경 기록"

def commit_record(item):
    commit=item.get("commit") or {}
    return {"sha":item["sha"],"message":commit.get("message","").splitlines()[0],"url":item["html_url"],
            "date":((commit.get("committer") or {}).get("date") or (commit.get("author") or {}).get("date")),"paths":[]}

def collect(config, previous, now, request=request_json):
    output={}; token=os.getenv("GITHUB_TOKEN")
    for project in config["projects"]:
        repo=project["repo"]; cached=previous.get(repo,{})
        try:
            base=f"https://api.github.com/repos/{config['owner']}/{repo}"
            meta=request(base,token)
            if meta.get("private") or meta.get("visibility") not in (None,"public"):
                output[repo]={"excluded":True,"error":"비공개 프로젝트 제외"}; continue
            items=request(base+"/commits?per_page=100",token)
            commits=[]; detail_budget=4
            for item in items:
                if not (item.get('commit') or {}).get('message'): continue
                record=commit_record(item)
                if is_routine(record["message"]): continue
                existing=next((c for c in cached.get("commits",[]) if c["sha"]==record["sha"]),None)
                if existing: record=existing
                else:
                    if detail_budget<=0: continue
                    detail_budget-=1
                    detail=request(base+"/commits/"+record["sha"],token)
                    record["paths"]=[f["filename"] for f in detail.get("files",[])]
                if record["paths"] and all(p.startswith(("data/","memory/")) for p in record["paths"]): continue
                commits.append(record)
                if len(commits)>=2: break
            # A high-volume sensor repo must not erase earlier meaningful changes.
            seen={c['sha'] for c in commits}
            commits.extend(c for c in cached.get('commits',[]) if c['sha'] not in seen)
            commits=sorted(commits,key=lambda c:c.get('date') or '',reverse=True)[:2]
            state={"default_branch":meta["default_branch"],"commits":commits,"error":None}
            core={k:v for k,v in cached.items() if k!="captured_at"}
            state["captured_at"]=cached.get("captured_at") if core==state else now.isoformat()
            output[repo]=state
        except (urllib.error.URLError,TimeoutError,ValueError,KeyError,TypeError,OSError) as exc:
            if isinstance(exc,urllib.error.HTTPError) and exc.code==404:
                output[repo]={"excluded":True,"error":"공개 접근 확인 불가"}
            else: output[repo]={**cached,"error":"자료 조회 지연 · 마지막 저장 자료 사용" if cached.get('commits') is not None else "자료 조회 불가"}
            print(f"{repo}: collection unavailable ({type(exc).__name__})",file=sys.stderr)
    return output

def safe(value): return html.escape(str(value),quote=True)

def markdown(value):
    value=html.escape(str(value),quote=False).replace("\n"," ")
    return re.sub(r"([\\`*{}\[\]()#+!|<>])",r"\\\1",value)

def picture(stem,alt,extension="png"):
    return (f'<picture>\n  <source media="(prefers-color-scheme: dark)" srcset="assets/{stem}-dark.{extension}">\n'
            f'  <source media="(prefers-color-scheme: light)" srcset="assets/{stem}-light.{extension}">\n'
            f'  <img alt="{safe(alt)}" src="assets/{stem}-light.{extension}" width="100%">\n</picture>')

def render_focus(config,index,theme):
    p=config["projects"][index];dark=theme=="dark"
    bg="#172126" if dark else "#f4f4eb"; fg="#e9ede4" if dark else "#253638"; muted="#9aacaa" if dark else "#697d78";accent=p["accent"]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="140" viewBox="0 0 1200 140" role="img" aria-label="오늘의 프로젝트 {safe(p['title'])}">
<rect width="1200" height="140" rx="8" fill="{bg}"/><rect width="7" height="140" fill="{accent}"/>
<circle cx="64" cy="70" r="26" fill="none" stroke="{accent}" stroke-width="2"/>
<text x="64" y="79" text-anchor="middle" fill="{fg}" font-family="sans-serif" font-size="24">{index+1:02d}</text>
<text x="114" y="42" fill="{muted}" font-family="sans-serif" font-size="14" letter-spacing="3">TODAY'S SPOTLIGHT</text>
<text x="110" y="94" fill="{fg}" font-family="sans-serif" font-size="37" font-weight="700">{safe(p['title'])}</text>
<g transform="translate(1000 26)" stroke="{accent}" fill="none" stroke-width="2"><ellipse cx="48" cy="44" rx="66" ry="25"/><ellipse cx="48" cy="44" rx="37" ry="44"/><path d="M-18 44h132M48 0v88"/><circle cx="93" cy="25" r="7" fill="{accent}"/></g></svg>\n'''

def render_readme(config,repositories,now):
    projects=[p for p in config["projects"] if not repositories.get(p["repo"],{}).get("excluded")]
    if not projects: raise ValueError("No publicly accessible projects; preserving README")
    featured=config["projects"][daily_focus(config,now)]
    if featured not in projects: featured=projects[0]
    owner=config["owner"]
    lines=[START,'<div align="center">','',picture("workshop","JUHWAN — 관측·검증·기억·발사·만남·생태계가 움직이는 미니어처 연구소","gif"),'',
           "### 시장을 관찰하고, 가설을 검증하고, 브라우저 안에 작은 세계를 만듭니다.",'',
           "[시장 연구](#시장을-읽는-장치) · [작은 세계](#브라우저와-게임-속-작은-세계) · [제작 방식](docs/WORKSHOP.md)",'',
           "<sub>프로젝트 구조를 코드로 그린 8초 루프 · 실시간 처리 화면이 아닌 시각적 은유</sub>",'',"</div>",'',
           picture("spotlight","오늘 전면에 등장하는 프로젝트","svg"),'',
           f"**[{featured['title']}](https://github.com/{owner}/{featured['repo']})** — {featured['hook']}",'',
           "<sub>한국 시간의 날짜에 따라 대표 프로젝트와 강조색이 바뀝니다.</sub>",'']
    for i,p in enumerate(config["projects"]):
        if p not in projects: continue
        if i==0: lines += ["## 시장을 읽는 장치",""]
        if i==3: lines += ["## 브라우저와 게임 속 작은 세계",""]
        repo_url=f"https://github.com/{owner}/{p['repo']}"
        lines += [f'<a href="{repo_url}">',picture(f"specimen-{i+1:02d}",p["title"]+" — "+p["visual"]),"</a>","",
                  f"### {i+1:02d} · [{p['title']}]({repo_url})","",f"**{p['hook']}**","",p["description"],"",
                  f"<sub>{safe(p['stage'])} · [단계 근거]({p['evidence_url']})</sub>",""]
        links=[f"[코드와 기록 ↗]({repo_url})"]
        if p.get("live_url"): links.append(f"[{p.get('live_label','체험하기')} ↗]({p['live_url']})")
        lines += [" · ".join(links),""]
    recent=[]
    for p in projects:
        for c in repositories.get(p["repo"],{}).get("commits",[]):
            if c.get("date"): recent.append((c["date"],p,c))
    recent.sort(key=lambda item:item[0],reverse=True)
    selected=[];used=set()
    for _,p,c in recent:
        if p["repo"] in used: continue
        used.add(p["repo"]);selected.append((p,c))
        if len(selected)==5: break
    lines += ["## 최근, 이런 부분을 바꿨습니다",""]
    for p,c in selected:
        dt=datetime.fromisoformat(c["date"].replace("Z","+00:00")).astimezone(ZoneInfo(config["timezone"]))
        lines += [f"- **{p['title']} · {category(c.get('paths',[]))}** — [{markdown(c['message'])}]({c['url']})<br>",f"  <sub>{dt:%Y-%m-%d %H:%M} KST</sub>"]
    if not selected: lines += ["현재 표시할 변경 기록이 없습니다."]
    lines += ["","<sub>반복 관측·스냅샷 및 데이터 전용 커밋을 제외한 최근 변경입니다. 파일 경로로 유형을 구분하며, 커밋 수를 개선 성과로 계산하지 않습니다.</sub>","",
              "## 만드는 방식","","관찰에서 출발해 가설을 세우고, 구현한 뒤 반례를 찾습니다. 실패와 결정은 다음 실험이 이어받을 수 있도록 저장소에 남깁니다. 시장 연구와 3D 실험은 서로 다른 결과물이지만, **검증할 수 있는 작은 시스템을 만든다**는 방향을 공유합니다.","",
              '<details id="이-장면은-어떻게-만들었을까">',"<summary><b>이 장면은 어떻게 만들었을까?</b></summary>","",
              "대표 장면과 프로젝트 이미지는 Python으로 좌표·형태·조명을 계산하고 Pillow로 그렸습니다. 80개 프레임을 GIF로 묶어 GitHub에서도 움직이게 했습니다. 라이트·다크 테마에는 각각 다른 에셋을 사용합니다.","",
              "관측 접시 → 검증 게이트 → 기억 선반, 발사대, 회전 테이블, 경쟁 생태계는 실제 프로젝트 구조에서 가져온 시각적 은유입니다. 실제 프로젝트 실행 화면을 촬영한 영상은 아닙니다.","",
              "GitHub Actions가 공개 프로젝트의 변경을 조회하고, 한국 시간 날짜에 따라 대표 프로젝트와 정적 표식을 바꿉니다. 큰 GIF는 재사용하므로 매일 새 영상이 저장되지 않습니다.","",
              "[장면 생성 코드](scripts/render_lab.py) · [프로필 생성 코드](scripts/workshop_profile.py) · [제작·상태 기준](docs/WORKSHOP.md)","","</details>","",
              "<details>","<summary><b>도구와 과거 실험</b></summary>","",
              "Python · Java · Spring Boot · JavaScript · Three.js · Roblox/Luau · GitHub Actions","",
              "[Wordle](https://github.com/juhwan7/wordle) · [README 미니 게임](https://github.com/juhwan7/readme-mini-game) · [Vibe Coding Playground](https://github.com/juhwan7/vibe-coding-playground)","","</details>","","---","",
              f"<sub>자료 반영: {now:%Y-%m-%d %H:%M} KST · 약 3시간 간격 조회 / 일일 대표 전환 · 예약 실행은 지연될 수 있습니다.</sub>","",
              "<sub>프로젝트 단계는 검토한 구현 범위입니다. 최근 커밋이나 배포 기록만으로 서비스 정상·게임 운영·AI의 현재 실행 여부를 판단하지 않습니다.</sub>",""]
    errors=[p for p in projects if repositories.get(p["repo"],{}).get("error")]
    if errors: lines += ["<sub>자료 조회 지연: "+", ".join(safe(p["title"]) for p in errors)+". 저장 자료를 사용하며, 저장 자료가 없는 프로젝트의 변경 기록은 생략합니다.</sub>",""]
    lines += [END]
    return "\n".join(lines)+"\n"

def replace_generated(existing,generated):
    if START in existing and END in existing:
        before,rest=existing.split(START,1);_,after=rest.split(END,1)
        return before+generated.rstrip("\n")+after
    return generated

def generate(root,config,repositories,now,force=False):
    index=daily_focus(config,now)
    if repositories.get(config["projects"][index]["repo"],{}).get("excluded"):
        index=next(i for i,p in enumerate(config["projects"]) if not repositories.get(p["repo"],{}).get("excluded"))
    meaningful={"version":3,"config":config,"day":str(now.date()),"repos":repositories}
    fingerprint=hashlib.sha256(json.dumps(meaningful,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()
    path=root/"data/profile-state.json";previous=read_json(path,{})
    if not force and previous.get("fingerprint")==fingerprint and (root/"README.md").exists(): return False
    generated=render_readme(config,repositories,now)
    readme=root/"README.md";existing=readme.read_text(encoding="utf-8") if readme.exists() else ""
    atomic_write(readme,replace_generated(existing,generated))
    for theme in ["light","dark"]: atomic_write(root/f"assets/spotlight-{theme}.svg",render_focus(config,index,theme))
    manifest={"fingerprint":fingerprint,"generated_at":now.isoformat(),"featured_repo":config["projects"][index]["repo"],"repositories":repositories}
    atomic_write(path,json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    return True

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--offline",action="store_true")
    parser.add_argument("--date",help="KST date for deterministic preview")
    parser.add_argument("--force",action="store_true")
    args=parser.parse_args()
    config=yaml.safe_load((ROOT/"profile.config.yml").read_text(encoding="utf-8"))
    now=datetime.now(ZoneInfo(config["timezone"]))
    if args.date: now=datetime.fromisoformat(args.date+"T12:00:00").replace(tzinfo=now.tzinfo)
    previous=read_json(ROOT/"data/profile-state.json",{}).get("repositories",{})
    repositories=previous if args.offline else collect(config,previous,now)
    print("Profile updated." if generate(ROOT,config,repositories,now,args.force) else "No content change; no files written.")

if __name__=="__main__": main()
