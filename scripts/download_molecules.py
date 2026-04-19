#!/usr/bin/env python3
"""
Download 2D (PNG) and 3D (SDF) structure files for all molecules
in sugars.html, including D/L chirality variants and α/β anomers.

Usage:
    python download_molecules.py
    python download_molecules.py --out path/to/dir --size 400
    python download_molecules.py --no-3d          # 2D only

Output:
    assets/img/molecules/{slug}_2d.png
    assets/img/molecules/{slug}_3d.sdf

Respects PubChem rate limit (≤5 req/s).
Skips files that already exist — safe to re-run after interruption.
Deduplicates: if two slugs share the same CID, the file is downloaded
once and copied, so no redundant network requests.
"""

import argparse
import os
import shutil
import time
import urllib.error
import urllib.request
from collections import defaultdict

# ── CLI ───────────────────────────────────────────────────────────────────────
p = argparse.ArgumentParser()
p.add_argument("--out",   default="assets/img/molecules")
p.add_argument("--size",  default=300, type=int, help="2D PNG size in px")
p.add_argument("--no-3d", action="store_true",   help="Skip 3D SDF downloads")
args = p.parse_args()
os.makedirs(args.out, exist_ok=True)

# ── Molecule list (slug, CID) ─────────────────────────────────────────────────
# All CIDs verified against the current sugars.html.
# Polysaccharide "fragments" use the oligosaccharide repeat unit as a proxy
# (true polymers have no single PubChem CID with 3D coordinates).

MOLECULES = [
    # ── 代表性 D型
    ("glucose_D",              5793),
    ("fructose_D",             2723872),
    ("galactose_D",            6036),
    ("mannose_D",              18950),
    ("xylose_D",               135191),
    ("ribose_D",               10975657),
    ("fucose_L",               17106),

    # ── L型开链
    ("glucose_L_open",         2724488),
    ("fructose_L_open",        5460024),
    ("galactose_L_open",       84996),
    ("mannose_L_open",         82308),
    ("xylose_L_open",          95259),
    ("ribose_L_open",          90428),
    ("fucose_D_rare",          94270),

    # ── D型环状异头体
    ("glucose_alpha_D_pyra",   79025),
    ("glucose_beta_D_pyra",    64689),
    ("fructose_alpha_D_fura",  11105942),
    ("fructose_beta_D_fura",   439709),
    ("fructose_alpha_D_pyra",  440545),
    ("galactose_alpha_D_pyra", 439357),
    ("galactose_beta_D_pyra",  439353),
    ("mannose_alpha_D_pyra",   185698),
    ("mannose_beta_D_pyra",    439680),
    ("xylose_alpha_D_pyra",    6027),
    ("xylose_beta_D_pyra",     125409),
    ("ribose_alpha_D_fura",    445894),
    ("ribose_beta_D_fura",     447347),
    ("fucose_alpha_L_pyra",    439554),
    ("fucose_beta_L_pyra",     444863),

    # ── L型环状异头体
    ("glucose_alpha_L_pyra",   6971003),
    ("glucose_beta_L_pyra",    6992084),
    ("fructose_alpha_L_fura",  15942891),
    ("fructose_beta_L_fura",   439553),
    ("fructose_alpha_L_pyra",  10154314),
    ("galactose_alpha_L_pyra", 439583),
    ("galactose_beta_L_pyra",  6971007),
    ("mannose_alpha_L_pyra",   6971016),
    ("mannose_beta_L_pyra",    1549080),
    ("xylose_alpha_L_pyra",    444344),
    ("xylose_beta_L_pyra",     445916),
    ("ribose_alpha_L_fura",    6971005),
    ("ribose_beta_L_fura",     6971004),

    # ── 二糖
    ("sucrose",                5988),
    ("lactose",                84571),
    ("maltose",                439341),
    ("cellobiose",             10712),
    ("trehalose",              7427),
    ("gentiobiose",            20056559),

    # ── 寡糖
    ("raffinose",              439242),
    ("gentianose",             117678),
    ("stachyose",              439531),
    ("maltotriose",            92146),

    # ── Polysaccharides (fragments as proxy)
    ("amylose_fragment",       439341),   # maltose     — α-1,4 repeat unit
    ("amylopectin_fragment",   92146),    # maltotriose — α-1,4 backbone
    ("cellulose_fragment",     10712),    # cellobiose  — β-1,4 repeat unit
    ("glycogen_fragment",      439341),   # maltose     — α-1,4 backbone
]

# ── PubChem ───────────────────────────────────────────────────────────────────
BASE    = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"}
DELAY   = 0.22   # ≈ 4.5 req/s  (limit is 5/s)


def fetch(url: str, path: str) -> bool:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
        return True
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}")
        return False
    except Exception as e:
        print(str(e))
        return False


# Build cid → first-seen slug mapping for deduplication
cid_first: dict[int, str] = {}
for slug, cid in MOLECULES:
    cid_first.setdefault(cid, slug)

downloaded_2d: set[int] = set()
downloaded_3d: set[int] = set()
total = len(MOLECULES)

for i, (slug, cid) in enumerate(MOLECULES, 1):
    tag = f"[{i:>2}/{total}]"

    # ── 2D PNG ────────────────────────────────────────────────────────────────
    dst2 = os.path.join(args.out, f"{slug}_2d.png")
    if os.path.exists(dst2):
        print(f"{tag} [skip] {slug}_2d.png")
    elif cid in downloaded_2d:
        src2 = os.path.join(args.out, f"{cid_first[cid]}_2d.png")
        shutil.copy2(src2, dst2)
        print(f"{tag} [copy] {slug}_2d.png")
    else:
        print(f"{tag} [ 2D ] {slug} (CID {cid}) … ", end="", flush=True)
        url = f"{BASE}/{cid}/PNG?image_size={args.size}x{args.size}"
        if fetch(url, dst2):
            downloaded_2d.add(cid)
            print("✓")
        else:
            print("✗")
        time.sleep(DELAY)

    if args.no_3d:
        continue

    # ── 3D SDF ────────────────────────────────────────────────────────────────
    dst3 = os.path.join(args.out, f"{slug}_3d.sdf")
    if os.path.exists(dst3):
        print(f"{tag} [skip] {slug}_3d.sdf")
    elif cid in downloaded_3d:
        src3 = os.path.join(args.out, f"{cid_first[cid]}_3d.sdf")
        if os.path.exists(src3):
            shutil.copy2(src3, dst3)
            print(f"{tag} [copy] {slug}_3d.sdf")
    else:
        print(f"{tag} [ 3D ] {slug} (CID {cid}) … ", end="", flush=True)
        url = f"{BASE}/{cid}/SDF?record_type=3d"
        if fetch(url, dst3):
            downloaded_3d.add(cid)
            print("✓")
        else:
            print("✗")
        time.sleep(DELAY)

print(f"\n✓  Done  →  {args.out}/")
print(f"   2D: {len(downloaded_2d)} unique CIDs downloaded, "
      f"{sum(1 for s,_ in MOLECULES if os.path.exists(os.path.join(args.out, f'{s}_2d.png')))} files total")
if not args.no_3d:
    print(f"   3D: {len(downloaded_3d)} unique CIDs downloaded, "
          f"{sum(1 for s,_ in MOLECULES if os.path.exists(os.path.join(args.out, f'{s}_3d.sdf')))} files total")
