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
    # ── Monosaccharides — main (open-chain or dominant form) ──────────────────
    ("glucose",                 5793),
    ("fructose",                2723872),
    ("galactose",               6036),
    ("mannose",                 18950),
    ("xylose",                  135191),
    ("ribose",                  10975657),   # corrected from 5311110
    ("fucose",                  17106),      # corrected from 18950321

    # ── Monosaccharides — D / L chirality open-chain ──────────────────────────
    ("glucose_D_open",          5793),
    ("glucose_L_open",          107689),
    ("fructose_D_open",         2723872),
    ("fructose_L_open",         159034),
    ("galactose_D_open",        6036),
    ("galactose_L_open",        91666),
    ("mannose_D_open",          18950),
    ("mannose_L_open",          122386),
    ("xylose_D_open",           135191),
    ("xylose_L_open",           61495),
    ("ribose_D_open",           10975657),
    ("ribose_L_open",           68327),
    ("fucose_L_main",           17106),
    ("fucose_D_rare",           439553),

    # ── Monosaccharides — α / β anomers ──────────────────────────────────────
    ("glucose_alpha_D_pyra",    79025),
    ("glucose_beta_D_pyra",     64689),
    ("fructose_beta_D_pyra",    2723872),
    ("fructose_beta_D_fura",    2723877),
    ("galactose_alpha_D",       439559),
    ("galactose_beta_D",        439557),
    ("mannose_alpha_D",         439530),
    ("mannose_beta_D",          439531),
    ("xylose_alpha_D",          16088714),
    ("xylose_beta_D",           24894893),
    ("ribose_alpha_D_fura",     3004008),
    ("ribose_beta_D_fura",      440997),
    ("fucose_alpha_L",          439554),
    ("fucose_beta_L",           102007),

    # ── Disaccharides ─────────────────────────────────────────────────────────
    ("sucrose",                 5988),
    ("lactose",                 84571),
    ("maltose",                 439341),
    ("cellobiose",              10712),
    ("trehalose",               7427),
    ("gentiobiose",             20056559),   # corrected from 91502565

    # ── Tri- & tetrasaccharides ───────────────────────────────────────────────
    ("raffinose",               65533),
    ("gentianose",              442813),
    ("stachyose",               441374),
    ("maltotriose",             439586),

    # ── Polysaccharides (oligosaccharide fragments as proxy) ──────────────────
    ("amylose_fragment",        439341),   # maltose       — α-1,4 repeat unit
    ("amylopectin_fragment",    439586),   # maltotriose   — α-1,4 backbone
    ("cellulose_fragment",      10712),    # cellobiose    — β-1,4 repeat unit
    ("glycogen_fragment",       439341),   # maltose       — α-1,4 backbone
]

# ── PubChem ───────────────────────────────────────────────────────────────────
BASE    = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid"
HEADERS = {"User-Agent": "carbohydrate-encyclopedia/2.0 (educational)"}
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
