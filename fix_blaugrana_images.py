
#!/usr/bin/env python3
"""Safely patch Blaugrana's player-photo/team-logo priority issues in www/index.html.

Run from the repository root:
    python fix_blaugrana_images.py

A dated backup is created before the file is changed. The script refuses to write
if any expected source snippet is missing or ambiguous.
"""
from __future__ import annotations
import argparse
from datetime import datetime
from pathlib import Path
import sys
import subprocess

TEAM_QUEUE = r'''  /* Real-team badge fallback: fill missing remote logos without touching match/table data. */
  var realTeamQueue = [], realTeamQueued = {}, realTeamBusy = false, realTeamTimer = null;
  MEDIA.teamMiss = MEDIA.teamMiss || {};
  function queueRealTeamLogo(name) {
    if (!name) return;
    var k = canonTeam(name);
    if (!k || realTeamQueued[k]) return;
    if (MEDIA.teams[norm(name)] && safeHttp(MEDIA.teams[norm(name)])) return;
    if (MEDIA.teams[k] && safeHttp(MEDIA.teams[k])) return;
    var missed = +MEDIA.teamMiss[k] || 0;
    if (missed && Date.now() - missed < 7 * 24 * 60 * 60 * 1000) return;
    realTeamQueued[k] = true;
    realTeamQueue.push({ name: String(name), key: k });
    if (realTeamTimer) clearTimeout(realTeamTimer);
    realTeamTimer = setTimeout(runRealTeamLogoQueue, 150);
  }
  function runRealTeamLogoQueue() {
    if (realTeamBusy || !realTeamQueue.length) return;
    realTeamBusy = true;
    var item = realTeamQueue.shift();
    var url = "https://www.thesportsdb.com/api/v1/json/123/searchteams.php?t=" + encodeURIComponent(item.name);
    fetch(url, { method: "GET", cache: "force-cache" })
      .then(function (resp) { if (!resp.ok) throw new Error("team logo HTTP " + resp.status); return resp.json(); })
      .then(function (data) {
        var teams = Array.isArray(data && data.teams) ? data.teams : [], found = null;
        for (var i = 0; i < teams.length; i++) {
          var t = teams[i];
          if (!t) continue;
          var names = [t.strTeam, t.strTeamAlternate, t.strTeamShort];
          var match = names.some(function (candidate) {
            if (!candidate) return false;
            if (canonTeam(candidate) === item.key) return true;
            return String(candidate).split(/[;,|]/).some(function (part) { return canonTeam(part) === item.key; });
          });
          if (match) { found = t; break; }
        }
        var logo = found && (found.strBadge || found.strTeamBadge || found.strTeamLogo);
        if (safeHttp(logo)) {
          delete MEDIA.teamMiss[item.key];
          saveTeamLogo(item.name, logo, true);
        } else {
          MEDIA.teamMiss[item.key] = Date.now();
          sv(MEDIA_KEY, MEDIA);
        }
      })
      .catch(function () {
        MEDIA.teamMiss[item.key] = Date.now();
        sv(MEDIA_KEY, MEDIA);
      })
      .finally(function () {
        realTeamBusy = false;
        realTeamQueued[item.key] = false;
        if (realTeamQueue.length) realTeamTimer = setTimeout(runRealTeamLogoQueue, 500);
      });
  }
  function queueKnownRealTeamLogos() {
    var names = {}, add = function (v) {
      if (typeof v === "string" && v.trim()) names[v.trim()] = true;
    };
    if (typeof ALLC !== "undefined" && Array.isArray(ALLC)) ALLC.forEach(function (t) { add(t && (t.n || t.name || (Array.isArray(t) ? t[0] : ""))); });
    if (typeof LG !== "undefined" && LG) Object.keys(LG).forEach(function (league) {
      if (Array.isArray(LG[league])) LG[league].forEach(function (t) { add(t && (t[0] || t.n || t.name)); });
    });
    if (typeof CAL !== "undefined" && Array.isArray(CAL)) CAL.forEach(function (m) {
      if (!m) return; add(m.o); add(m.homeName); add(m.awayName);
    });
    Object.keys(names).forEach(queueRealTeamLogo);
  }
  setTimeout(queueKnownRealTeamLogos, 800);
'''

REPLACEMENTS = [
    (
        '  function teamLogo(name) {\n'
        '    var k = norm(name), c = canonTeam(name);\n'
        '    if (typeof LOGOS !== "undefined" && LOGOS && LOGOS[name]) return "/_blob/" + LOGOS[name];\n'
        '    if (MEDIA.teams[k] && safeHttp(MEDIA.teams[k])) return MEDIA.teams[k];\n'
        '    if (MEDIA.teams[c] && safeHttp(MEDIA.teams[c])) return MEDIA.teams[c];\n'
        '    if (c === "barcelona" || k === "jr" || k === "fc barcelona") return BARCA_CREST;\n'
        '    return "";\n'
        '  }',
        '  function teamLogo(name) {\n'
        '    var k = norm(name), c = canonTeam(name);\n'
        '    /* Prefer verified remote logos over bundled legacy artwork. */\n'
        '    if (MEDIA.teams[k] && safeHttp(MEDIA.teams[k])) return MEDIA.teams[k];\n'
        '    if (MEDIA.teams[c] && safeHttp(MEDIA.teams[c])) return MEDIA.teams[c];\n'
        '    if (c === "barcelona" || k === "jr" || k === "fc barcelona") return BARCA_CREST;\n'
        '    if (typeof LOGOS !== "undefined" && LOGOS && LOGOS[name]) return "/_blob/" + LOGOS[name];\n'
        '    return "";\n'
        '  }'
    ),
    (
        '      else {if((PH&&PH[id])||(DPH&&DPH[id]))return;el.style.backgroundImage=\'url("\'+url.replace(/"/g,"%22")+\'")\';el.style.backgroundSize="cover";el.style.backgroundPosition="center 25%";el.style.backgroundColor="#eef1f5";el.innerHTML="";}',
        '      else {el.style.backgroundImage=\'url("\'+url.replace(/"/g,"%22")+\'")\';el.style.backgroundSize="cover";el.style.backgroundPosition="center 25%";el.style.backgroundColor="#eef1f5";el.innerHTML="";}'
    ),
    (
        '      if(!safeHttp(url)||(PH&&PH[id])||(DPH&&DPH[id])){resolve(false);return;}',
        '      if(!safeHttp(url)){resolve(false);return;}'
    ),
    (
        '    id=String(id);if(playerImage(id)||queuedPlayers[id])return;',
        '    id=String(id);if((MEDIA.players[id]&&safeHttp(MEDIA.players[id]))||queuedPlayers[id])return;'
    ),
    (
        '        var url=found&&(safeHttp(found.strThumb)?found.strThumb:found.strCutout);if(safeHttp(url))usePlayerImage(id,url);else{MEDIA.playerMiss[id]=Date.now();sv(MEDIA_KEY,MEDIA);}',
        '        var url=found&&(safeHttp(found.strThumb)?found.strThumb:found.strCutout);if(safeHttp(url))usePlayerImage(id,url);else{delete MEDIA.playerMiss[id];sv(MEDIA_KEY,MEDIA);}'
    ),
]

PLAYER_IMAGE_OLD = '  function playerImage(id) { id=String(id); if(PH&&PH[id])return PH[id]; if(DPH&&DPH[id])return "/_blob/"+DPH[id]; return MEDIA.players[id]||""; }'
PLAYER_IMAGE_NEW = '  function playerImage(id) { id=String(id); if(MEDIA.players[id]&&safeHttp(MEDIA.players[id]))return MEDIA.players[id]; if(PH&&PH[id])return PH[id]; if(DPH&&DPH[id])return "/_blob/"+DPH[id]; return ""; }'
ANCHOR = '  cacheCurrentMatchLogos();\n  function loadWikiPlayerPhotos() {'


def ensure_safety_branch(path: Path) -> str | None:
    """Create a dedicated branch when running from main/master in a Git checkout."""
    try:
        root = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path.parent,
                              check=True, capture_output=True, text=True).stdout.strip()
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=root,
                                check=True, capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    if branch not in ("main", "master"):
        return branch
    base = "fix/real-team-player-images"
    candidate = base
    suffix = 2
    while subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{candidate}"],
                         cwd=root).returncode == 0:
        candidate = f"{base}-{suffix}"
        suffix += 1
    subprocess.run(["git", "switch", "-c", candidate], cwd=root, check=True,
                   capture_output=True, text=True)
    return candidate


def patch(path: Path, dry_run: bool = False) -> tuple[int, Path | None]:
    original = path.read_text(encoding="utf-8")
    updated = original
    # The user may already have applied the earlier one-line playerImage edit in Codespaces.
    player_old_count = updated.count(PLAYER_IMAGE_OLD)
    player_new_count = updated.count(PLAYER_IMAGE_NEW)
    if player_old_count == 1:
        updated = updated.replace(PLAYER_IMAGE_OLD, PLAYER_IMAGE_NEW, 1)
    elif player_old_count == 0 and player_new_count == 1:
        pass  # Already correct; continue with the remaining parts of the patch.
    else:
        raise RuntimeError(f"Expected one old or already-fixed playerImage() function; found old={player_old_count}, fixed={player_new_count}.")
    for old, new in REPLACEMENTS:
        count = updated.count(old)
        if count != 1:
            raise RuntimeError(f"Expected exactly one match for replacement, found {count}: {old[:100]!r}")
        updated = updated.replace(old, new, 1)
    count = updated.count(ANCHOR)
    if count != 1:
        raise RuntimeError(f"Expected exactly one team-logo insertion point, found {count}.")
    updated = updated.replace(ANCHOR, '  cacheCurrentMatchLogos();\n' + TEAM_QUEUE + '  function loadWikiPlayerPhotos() {', 1)
    if updated == original:
        raise RuntimeError("No changes produced; refusing to write.")
    # Basic structural sanity check: key sections outside the image subsystem remain present.
    for sentinel in ["/* المباريات */", "function updateStandings", "/* v9:", "function loadWikiPlayerPhotos()", "</body>"]:
        if sentinel not in updated and sentinel != "/* v9:":
            raise RuntimeError(f"Structural check failed: missing {sentinel!r}")
    if dry_run:
        return len(updated.splitlines()) - len(original.splitlines()), None
    branch = ensure_safety_branch(path)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(path.name + ".backup-images-" + stamp)
    backup.write_text(original, encoding="utf-8")
    path.write_text(updated, encoding="utf-8")
    # Return branch info via the backup's sibling marker, without changing the HTML.
    if branch:
        backup.with_suffix(backup.suffix + ".branch").write_text(branch, encoding="utf-8")
    return len(updated.splitlines()) - len(original.splitlines()), backup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default="www/index.html", help="Target index.html path")
    parser.add_argument("--dry-run", action="store_true", help="Validate patches without writing")
    args = parser.parse_args()
    path = Path(args.file)
    if not path.is_file():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 2
    try:
        delta, backup = patch(path, args.dry_run)
    except Exception as exc:
        print(f"ERROR: {exc}\nNo changes written.", file=sys.stderr)
        return 1
    if args.dry_run:
        print(f"PASS: all patch anchors found. Expected line-count change: {delta:+d}. No files changed.")
    else:
        print("PATCH APPLIED")
        print(f"Updated: {path}")
        print(f"Backup:  {backup}")
        branch_marker = backup.with_suffix(backup.suffix + ".branch")
        if branch_marker.exists():
            print(f"Branch:  {branch_marker.read_text(encoding='utf-8').strip()}")
        else:
            print("Branch:  unchanged (not running from main/master in a Git checkout).")
        print("Changes are limited to player-image priority/fallback and team-logo priority/fetching.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
