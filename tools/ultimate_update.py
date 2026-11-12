#!/usr/bin/env python3
"""Track upstream SOTN Ultimate (PS1 Version) releases and build their original image.

    python tools/ultimate_update.py check [--json]
        Ask GitHub for upstream releases and compare the newest tag with the
        newest base we support (work/bases.json). When a newer one exists, its
        release notes (+ the changed-file list between the two tags) are saved
        to docs/upstream_notes_<tag>.txt.
        exit 0 = nothing new, 10 = a newer upstream version exists, 2 = error.

    python tools/ultimate_update.py fetch <tag>
        Download builder.html (+ checksums.txt, README.txt, release notes) of
        that release into 원본롬/builders/<tag>/.

    python tools/ultimate_update.py build <tag> [--out PATH] [--keep-browser-log]
        Run 원본롬/builders/<tag>/builder.html in headless Chrome/Edge with the
        three source discs, save the .bin/.cue, check the MD5 against the one the
        page reports, and record the base in work/bases.json.
        Default output: 원본롬/SOTN Ultimate (PS1 Version) <tag>.bin/.cue
        (refuses to overwrite an existing file).

    python tools/ultimate_update.py bases
        List the supported bases.

Needs: Python playwright (pip install playwright) and an installed Chrome or
Edge (no playwright browser download needed). The build needs ~8 GB free RAM
and takes a few minutes.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = os.path.join(ROOT, "원본롬")
BUILDERS = os.path.join(ROM, "builders")
BASES = os.path.join(ROOT, "work", "bases.json")
DOCS = os.path.join(ROOT, "docs")
REPO = "renanbianchi/sotn-ultimate"
API = "https://api.github.com/repos/" + REPO
UA = "sotn-release-checker/1.0"
NAME = "SOTN Ultimate (PS1 Version)"
SOURCES = [
    "Castlevania - Symphony of the Night (USA) (Track 1).bin",
    "Akumajou Dracula X - Gekka no Yasoukyoku (Japan) (2M) (Track 1).bin",
    "Castlevania - The Dracula X Chronicles (USA).iso",
]
FETCH_ASSETS = re.compile(r"^(builder\.html|checksums\.txt|README\.txt|release_notes.*\.txt)$", re.I)

SEED = {
    "v1.2": {"image": "원본롬/SOTN Ultimate (PS1 Version) v1.2.bin",
             "md5": "b8b9cd07c9251919bcf02c8ebbb4602b"},
    "v1.4": {"image": "원본롬/SOTN Ultimate (PS1 Version) v1.4.bin",
             "md5": "901d74656aedbd8da3050d6a3716f32f"},
}


# ---------------------------------------------------------------- helpers

def vkey(tag):
    """'v1.4' / 'v1.4.1' / '1.10' -> sortable tuple; non-version tags sort first."""
    m = re.match(r"^v?(\d+(?:\.\d+)*)", tag.strip())
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def http_get(url, accept="application/vnd.github+json"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def api(path):
    return json.loads(http_get(API + path))


def md5_file(path, chunk=1 << 22):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def load_bases():
    if os.path.exists(BASES):
        with open(BASES, encoding="utf-8") as f:
            return json.load(f)
    bases = {}
    for tag, d in SEED.items():
        p = os.path.join(ROOT, d["image"])
        bases[tag] = {"image": d["image"], "md5": d["md5"],
                      "size": os.path.getsize(p) if os.path.exists(p) else None}
    save_bases(bases)
    return bases


def save_bases(bases):
    os.makedirs(os.path.dirname(BASES), exist_ok=True)
    ordered = {k: bases[k] for k in sorted(bases, key=vkey)}
    with open(BASES, "w", encoding="utf-8") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=2)
        f.write("\n")


def releases():
    rel = [r for r in api("/releases?per_page=100") if not r.get("draft") and not r.get("prerelease")]
    rel = [r for r in rel if vkey(r["tag_name"])]
    rel.sort(key=lambda r: vkey(r["tag_name"]))
    return rel


def release(tag):
    return api("/releases/tags/" + tag)


# ---------------------------------------------------------------- check

def cmd_check(args):
    bases = load_bases()
    have = max(bases, key=vkey)
    rel = releases()
    if not rel:
        print("no upstream releases found", file=sys.stderr)
        return 2
    newest = rel[-1]
    tag = newest["tag_name"]
    newer = [r for r in rel if vkey(r["tag_name"]) > vkey(have)]
    info = {"supported": sorted(bases, key=vkey), "newest_supported": have,
            "newest_upstream": tag, "new_versions": [r["tag_name"] for r in newer]}
    if not newer:
        if args.json:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print(f"up to date: newest upstream {tag}, newest supported base {have}")
        return 0

    # notes for every newer release (normally just one)
    for r in newer:
        t = r["tag_name"]
        lines = [f"{r['name']}  ({t}, published {r['published_at']})",
                 f"https://github.com/{REPO}/releases/tag/{t}", "",
                 "assets:"]
        for a in r["assets"]:
            lines.append(f"  {a['name']}  {a['size']} bytes  {a['browser_download_url']}")
        lines += ["", "=" * 72, "release body", "=" * 72, r.get("body") or "(empty)"]
        for a in r["assets"]:
            if re.match(r"^release_notes.*\.txt$", a["name"], re.I) and a["size"] < 1 << 20:
                try:
                    txt = http_get(a["browser_download_url"], "application/octet-stream").decode("utf-8", "replace")
                    lines += ["", "=" * 72, a["name"], "=" * 72, txt]
                except Exception as e:  # notes are a convenience
                    lines += ["", f"({a['name']} download failed: {e})"]
        # source diff from the newest supported base to this tag
        prev = have
        lines += ["", "=" * 72, f"source diff {prev}...{t}", "=" * 72,
                  f"https://github.com/{REPO}/compare/{prev}...{t}"]
        try:
            cmp_ = api(f"/compare/{prev}...{t}")
            lines.append(f"{cmp_.get('total_commits')} commits, {len(cmp_.get('files', []))} files"
                         " (GitHub lists at most 300 files)")
            for c in cmp_.get("commits", []):
                lines.append("  commit " + c["sha"][:10] + "  " + c["commit"]["message"].splitlines()[0])
            lines.append("")
            for f in cmp_.get("files", []):
                lines.append(f"  {f['status']:<9} +{f['additions']:<5} -{f['deletions']:<5} {f['filename']}")
        except Exception as e:
            lines.append(f"(compare failed: {e}; the old tag may not exist upstream — "
                         f"clone the repo and diff by hand)")
        os.makedirs(DOCS, exist_ok=True)
        out = os.path.join(DOCS, f"upstream_notes_{t}.txt")
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        info.setdefault("notes", {})[t] = out
        info.setdefault("assets", {})[t] = [a["name"] for a in r["assets"]]

    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        print(f"NEW upstream version(s): {', '.join(info['new_versions'])} "
              f"(newest supported base: {have})")
        for r in newer:
            t = r["tag_name"]
            print(f"\n--- {t}: {r['name']} ({r['published_at']})")
            for a in r["assets"]:
                print(f"    asset {a['name']} ({a['size']} bytes)")
            print(f"    notes saved: {info['notes'][t]}")
            print((r.get("body") or "").strip())
    return 10


# ---------------------------------------------------------------- fetch

def cmd_fetch(args):
    r = release(args.tag)
    dest = os.path.join(BUILDERS, args.tag)
    os.makedirs(dest, exist_ok=True)
    got = []
    for a in r["assets"]:
        if not FETCH_ASSETS.match(a["name"]):
            continue
        p = os.path.join(dest, os.path.basename(a["name"]))
        if os.path.exists(p) and os.path.getsize(p) == a["size"]:
            got.append(p)
            continue
        print(f"downloading {a['name']} ({a['size']} bytes)")
        data = http_get(a["browser_download_url"], "application/octet-stream")
        if len(data) != a["size"]:
            print(f"size mismatch for {a['name']}: {len(data)} != {a['size']}", file=sys.stderr)
            return 2
        with open(p, "wb") as f:
            f.write(data)
        got.append(p)
    if not any(p.endswith("builder.html") for p in got):
        print("release has no builder.html", file=sys.stderr)
        return 2
    # checksums.txt (if any) for the builder itself
    ck = os.path.join(dest, "checksums.txt")
    if os.path.exists(ck):
        text = open(ck, encoding="utf-8", errors="replace").read()
        for p in got:
            n = os.path.basename(p)
            if n == "checksums.txt":
                continue
            for algo in ("sha256", "md5", "sha1"):
                h = hashlib.new(algo, open(p, "rb").read()).hexdigest()
                if h in text.lower():
                    print(f"{n}: {algo} matches checksums.txt")
                    break
    print("saved to " + dest)
    for p in got:
        print("  " + os.path.basename(p))
    return 0


# ---------------------------------------------------------------- build

def expected_md5(tag):
    """MD5 the page's MANIFEST.target says the result must have."""
    d = os.path.join(BUILDERS, tag)
    page = os.path.join(d, "builder.html")
    with open(page, "rb") as f:
        head = f.read()
    m = re.search(rb'"target"\s*:\s*\{[^}]*?"md5"\s*:\s*"([0-9a-f]{32})"', head)
    return m.group(1).decode() if m else None


def find_browser():
    cands = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for c in cands:
        if os.path.exists(c):
            return c
    return None


def cmd_build(args):
    from playwright.sync_api import sync_playwright

    tag = args.tag
    page_path = os.path.join(BUILDERS, tag, "builder.html")
    if not os.path.exists(page_path):
        print(f"no {page_path}; run: fetch {tag}", file=sys.stderr)
        return 2
    srcs = [os.path.join(ROM, s) for s in SOURCES]
    for s in srcs:
        if not os.path.exists(s):
            print("missing source disc: " + s, file=sys.stderr)
            return 2
    out_bin = os.path.abspath(args.out) if args.out else os.path.join(ROM, f"{NAME} {tag}.bin")
    if not out_bin.lower().endswith(".bin"):
        out_bin += ".bin"
    out_cue = out_bin[:-4] + ".cue"
    if os.path.exists(out_bin) or os.path.exists(out_cue):
        print(f"refusing to overwrite {out_bin} / .cue (use --out)", file=sys.stderr)
        return 2
    exe = find_browser()
    if not exe:
        print("no Chrome/Edge found", file=sys.stderr)
        return 2
    want = expected_md5(tag)
    print(f"builder {page_path}\nbrowser {exe}\nexpected md5 (page manifest) {want}")

    t0 = time.time()
    url = "file:///" + page_path.replace("\\", "/")
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=exe, headless=True,
                                    args=["--js-flags=--max-old-space-size=12288",
                                          "--disable-background-timer-throttling",
                                          "--disable-renderer-backgrounding"])
        ctx = browser.new_context(accept_downloads=True)
        page = ctx.new_page()
        page.on("pageerror", lambda e: print("page error:", e, file=sys.stderr))
        page.goto(url, wait_until="load", timeout=300_000)
        with page.expect_file_chooser() as fc:
            page.click("#pick")
        fc.value.set_files(srcs)
        page.wait_for_function("() => !document.getElementById('build').disabled", timeout=600_000)
        print("discs identified:", page.inner_text("#added"))
        page.click("#build")
        last, shown_at = "", 0.0
        while True:
            state = page.evaluate("""() => ({
                done: !document.getElementById('done').hidden,
                bad: [...document.querySelectorAll('#steps .bad')].map(e => e.textContent),
                cur: document.getElementById('cur').textContent,
                pct: document.getElementById('pct').textContent,
                building: document.getElementById('buildSub').textContent })""")
            if state["bad"]:
                print("BUILD FAILED: " + " | ".join(state["bad"]), file=sys.stderr)
                browser.close()
                return 3
            if state["done"]:
                break
            if state["cur"] != last or time.time() - shown_at >= 15:
                print(f"  [{int(time.time() - t0):4d}s] {state['cur']} {state['pct']}", flush=True)
                last, shown_at = state["cur"], time.time()
            time.sleep(1)
        verdict = page.inner_text("#verdict")
        shown = page.inner_text("#md5")
        print("page:", verdict, "|", shown)
        m = re.search(r"[0-9a-f]{32}", shown)
        page_md5 = m.group(0) if m else want
        os.makedirs(os.path.dirname(out_bin), exist_ok=True)
        with page.expect_download(timeout=600_000) as dl:
            page.click("#saveBin")
        dl.value.save_as(out_bin)
        with page.expect_download(timeout=60_000) as dl:
            page.click("#saveCue")
        cue_tmp = out_cue + ".tmp"
        dl.value.save_as(cue_tmp)
        browser.close()

    # the .cue points at the .bin by name; rewrite it for our file name
    with open(cue_tmp, encoding="utf-8", errors="replace") as f:
        cue = f.read()
    os.remove(cue_tmp)
    cue = re.sub(r'FILE "[^"]*"', 'FILE "' + os.path.basename(out_bin) + '"', cue, count=1)
    with open(out_cue, "w", encoding="utf-8", newline="") as f:
        f.write(cue)

    got = md5_file(out_bin)
    size = os.path.getsize(out_bin)
    secs = int(time.time() - t0)
    print(f"wrote {out_bin} ({size} bytes) in {secs} s\nmd5 {got}")
    if got != page_md5:
        print(f"MD5 MISMATCH: file {got} != page {page_md5}", file=sys.stderr)
        return 4
    print("md5 matches the page's verified md5")
    if args.no_record:
        return 0
    bases = load_bases()
    rel = os.path.relpath(out_bin, ROOT).replace("\\", "/")
    bases[tag] = {"image": rel, "md5": got, "size": size}
    save_bases(bases)
    print(f"recorded base {tag} in {os.path.relpath(BASES, ROOT)}")
    return 0


def cmd_bases(args):
    for tag, d in load_bases().items():
        p = os.path.join(ROOT, d["image"])
        print(f"{tag:8} {d['md5']} {d.get('size')} {d['image']}"
              f"{'' if os.path.exists(p) else '  (MISSING)'}")
    return 0


def main():
    for st in (sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--json", action="store_true")
    f = sub.add_parser("fetch")
    f.add_argument("tag")
    b = sub.add_parser("build")
    b.add_argument("tag")
    b.add_argument("--out", help="output .bin path (default 원본롬/<name> <tag>.bin)")
    b.add_argument("--no-record", action="store_true", help="don't add the result to work/bases.json")
    sub.add_parser("bases")
    args = ap.parse_args()
    try:
        return {"check": cmd_check, "fetch": cmd_fetch, "build": cmd_build, "bases": cmd_bases}[args.cmd](args)
    except urllib.error.URLError as e:
        print(f"network error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
