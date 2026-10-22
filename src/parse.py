import json
import time
from pathlib import Path
from urllib.parse import urlsplit

import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
CONFIG = dotenv_values(ROOT / ".env")

MOD_COUNT = int(CONFIG.get("MOD_COUNT") or 20)
if not 1 <= MOD_COUNT <= 50:
    raise ValueError("MOD_COUNT в .env должен быть от 1 до 50")

CF = "https://api.curseforge.com/v1"
MR = "https://api.modrinth.com/v2"
GH = "https://api.github.com"

CF_KEY = CONFIG.get("CURSEFORGE_API_KEY")
CF_HEADERS = {"x-api-key": CF_KEY}
MR_HEADERS = {"User-Agent": "minecraft-knowledge-graph-collector/1.0"}
GH_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2026-03-10",
}

if CONFIG.get("GITHUB_TOKEN"):
    GH_HEADERS["Authorization"] = "Bearer " + CONFIG["GITHUB_TOKEN"]

if CONFIG.get("MODRINTH_TOKEN"):
    MR_HEADERS["Authorization"] = CONFIG["MODRINTH_TOKEN"]

repos = {
    repo.strip().lower()
    for repo in (CONFIG.get("GITHUB_REPOS") or "").split(",")
    if repo.strip()
}


def get(url, headers, params=None):
    for attempt in range(3):
        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=(10, 60),
            )
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout as error:
            if attempt == 2:
                raise TimeoutError(f"Нет ответа от {url}") from error
            time.sleep(2)
    return None


def save(name, data):
    folder = ROOT / "data"
    folder.mkdir(exist_ok=True)
    (folder / name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_repos(*urls):
    for url in urls:
        link = urlsplit(url or "")
        parts = link.path.strip("/").split("/")
        if link.netloc.lower() in {"github.com", "www.github.com"} and len(parts) >= 2:
            repos.add("/".join(parts[:2]).removesuffix(".git").lower())


def curseforge_files(mod_id):
    result = []
    for index in range(0, 10000, 50):
        page = get(
            f"{CF}/mods/{mod_id}/files",
            CF_HEADERS,
            {"index": index, "pageSize": 50},
        ).json()
        result.extend(page["data"])
        if not page["data"] or len(result) >= page["pagination"]["totalCount"]:
            break
    return result


def github_issues(repo):
    result = []
    url = f"{GH}/repos/{repo}/issues?state=all&per_page=100"
    while url:
        response = get(url, GH_HEADERS)
        result.extend(item for item in response.json() if "pull_request" not in item)
        url = response.links.get("next", {}).get("url")
    return result


if CF_KEY:
    mods = get(
        f"{CF}/mods/search",
        CF_HEADERS,
        {
            "gameId": 432,
            "classId": 6,
            "pageSize": MOD_COUNT,
            "sortField": 6,
            "sortOrder": "desc",
        },
    ).json()["data"]

    for mod in mods:
        save(
            f"curseforge_{mod['id']}.json",
            {
                "mod": mod,
                "description": get(
                    f"{CF}/mods/{mod['id']}/description", CF_HEADERS
                ).json()["data"],
                "files": curseforge_files(mod["id"]),
            },
        )
        links = mod.get("links") or {}
        add_repos(links.get("sourceUrl"), links.get("issuesUrl"))


mods = get(
    f"{MR}/search",
    MR_HEADERS,
    {
        "facets": json.dumps([["project_type:mod"]]),
        "index": "downloads",
        "limit": MOD_COUNT,
    },
).json()["hits"]

for mod in mods:
    project_id = mod["project_id"]
    project = get(f"{MR}/project/{project_id}", MR_HEADERS).json()
    save(
        f"modrinth_{project_id}.json",
        {
            "project": project,
            "members": get(
                f"{MR}/project/{project_id}/members", MR_HEADERS
            ).json(),
            "versions": get(
                f"{MR}/project/{project_id}/version", MR_HEADERS
            ).json(),
        },
    )
    add_repos(project.get("source_url"), project.get("issues_url"))


for repo in sorted(repos):
    repository = get(f"{GH}/repos/{repo}", GH_HEADERS).json()
    save(
        f"github_{repo.replace('/', '_')}.json",
        {
            "repository": repository,
            "issues": github_issues(repo) if repository.get("has_issues", True) else [],
        },
    )