#!/usr/bin/env python3
"""Regenerate the product table in README.md from this repo's GitHub releases.

Conventions:
  * Release tags look like `<product>-v<version>` (e.g. `mobileiq-v1.0`).
  * The newest non-draft, non-prerelease version of each product is listed.
  * Checksum / signature assets are skipped; every other asset gets a row,
    labelled with a platform guessed from its file extension.

Only the text between the BEGIN/END markers in README.md is replaced.
"""
import json
import os
import re
import subprocess
import sys
import urllib.request

REPO = os.environ.get("GITHUB_REPOSITORY", "Brad2533/Public-Deploy")
README = os.environ.get("README_PATH", "README.md")
BEGIN = "<!-- BEGIN PRODUCT TABLE (auto-generated, do not edit by hand) -->"
END = "<!-- END PRODUCT TABLE -->"

TAG_RE = re.compile(r"^(?P<product>.+?)-v(?P<version>\d[\w.+-]*)$")
SKIP_SUFFIXES = (".sha256", ".sha512", ".sha1", ".md5", ".sig", ".asc", ".minisig", ".sbom", ".json.sig")
PLATFORMS = [
    ((".apk", ".aab"), "Android"),
    ((".ipa",), "iOS"),
    ((".exe", ".msi", ".msix"), "Windows"),
    ((".dmg", ".pkg"), "macOS"),
    ((".appimage", ".deb", ".rpm", ".snap", ".flatpak"), "Linux"),
]


def api_get(path):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        req = urllib.request.Request(
            f"https://api.github.com/{path}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    out = subprocess.run(["gh", "api", path], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def fetch_releases():
    releases, page = [], 1
    while True:
        batch = api_get(f"repos/{REPO}/releases?per_page=100&page={page}")
        releases.extend(batch)
        if len(batch) < 100:
            return releases
        page += 1


def version_key(version):
    return tuple(int(n) for n in re.findall(r"\d+", version))


def platform_of(name):
    lower = name.lower()
    for suffixes, label in PLATFORMS:
        if lower.endswith(suffixes):
            return label
    return "Other"


def display_name(release, product_slug, version):
    name = (release.get("name") or "").strip()
    stripped = re.sub(r"[\s-]*v?" + re.escape(version) + r"$", "", name, flags=re.I).strip()
    return stripped or product_slug.replace("-", " ").replace("_", " ").title()


def build_table(releases):
    latest = {}
    for rel in releases:
        if rel.get("draft") or rel.get("prerelease"):
            continue
        m = TAG_RE.match(rel["tag_name"])
        if not m:
            continue
        slug, ver = m["product"].lower(), m["version"]
        if slug not in latest or version_key(ver) > version_key(latest[slug][1]):
            latest[slug] = (rel, ver)

    rows = []
    for slug in sorted(latest):
        rel, ver = latest[slug]
        title = display_name(rel, slug, ver)
        tag_url = f"https://github.com/{REPO}/releases/tag/{rel['tag_name']}"
        date = (rel.get("published_at") or "")[:10]
        for asset in sorted(rel.get("assets", []), key=lambda a: a["name"]):
            if asset["name"].lower().endswith(SKIP_SUFFIXES):
                continue
            rows.append(
                f"| {title} | {platform_of(asset['name'])} | [{ver}]({tag_url}) | "
                f"[`{asset['name']}`]({asset['browser_download_url']}) | {date} |"
            )

    if not rows:
        return "_No releases yet._"
    header = [
        "| Product | Platform | Latest version | Download this file | Released |",
        "|---|---|---|---|---|",
    ]
    return "\n".join(header + rows)


def main():
    with open(README, encoding="utf-8") as f:
        text = f.read()
    if BEGIN not in text or END not in text:
        sys.exit(f"Markers not found in {README}")
    table = build_table(fetch_releases())
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    new_text = f"{head}{BEGIN}\n{table}\n{END}{tail}"
    if new_text == text:
        print("README already up to date.")
        return
    with open(README, "w", encoding="utf-8") as f:
        f.write(new_text)
    print("README updated.")


if __name__ == "__main__":
    main()
