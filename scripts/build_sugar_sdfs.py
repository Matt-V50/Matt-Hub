#!/usr/bin/env python3
"""
build_sugar_sdfs.py — 从 sugars.html 的 SMILES 字典批量生成 3D SDF 文件

管线: SMILES → AddHs → ETKDGv3 多构象嵌入 → MMFF94s 能量优化 → 取最低能 → 写 SDF

为什么这些选择:
  - ETKDGv3: 2020 发布的 RDKit 默认嵌入算法, 对糖类小环扭转有专门校正
  - MMFF94s: MMFF94 的静态变体, 对糖/核酸类氢键网络建模更准; 失败时 UFF 兜底
  - 多构象 + 能量排序: 糖的羟基很灵活, 单构象很容易卡在局部极小
  - pruneRmsThresh: 去除几何近重复构象, 加速并提升构象多样性
  - randomSeed: 固定种子让 D/L 糖真正互为镜像, 可复现

用法:
    python build_sugar_sdfs.py sugars.html -o ./molecules_3d
    python build_sugar_sdfs.py sugars.html -o ./out --only '^glucose' --overwrite
    python build_sugar_sdfs.py sugars.html -n 50  # 更多构象, 更准但更慢

依赖:
    pip install rdkit
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path

try:
    from rdkit import Chem, RDLogger
    from rdkit.Chem import AllChem
except ImportError:
    sys.exit("需要 rdkit: pip install rdkit")

# 静音 RDKit 的构象嵌入日志噪音 (保留 error 级)
RDLogger.DisableLog('rdApp.warning')
RDLogger.DisableLog('rdApp.info')


# ─── SMILES 字典提取 ────────────────────────────────────────────────────────
def extract_smiles_dict(html_path: Path) -> dict[str, str]:
    """从 sugars.html 里正则抓取 const SMILES = {...} 块"""
    text = html_path.read_text(encoding='utf-8')
    m = re.search(r'const\s+SMILES\s*=\s*\{(.+?)\n\};', text, re.DOTALL)
    if not m:
        raise RuntimeError(f"在 {html_path} 中未找到 `const SMILES = {{...}}` 块")
    body = m.group(1)
    # 每行形如:   glucose_D_open:   'O=C[C@H](O)...',
    # 允许 key 前后空白, SMILES 里绝不含单引号 (sugars.html 已验证)
    pairs = re.findall(r"^\s*(\w+)\s*:\s*'([^']+)'\s*,?\s*(?://.*)?$",
                       body, re.MULTILINE)
    if not pairs:
        raise RuntimeError("SMILES 字典为空或正则失配")
    return dict(pairs)


# ─── 3D 嵌入 + 优化 ──────────────────────────────────────────────────────────
def embed_and_optimize(smi: str, num_confs: int, seed: int):
    """
    返回 (mol_with_3d, energy_kcal_mol, force_field_used) 或 None

    流程:
      1. SMILES → mol (带立体化学)
      2. AddHs (3D 必需)
      3. ETKDGv3 多构象嵌入
      4. MMFF94s 优化 (失败则 UFF)
      5. 取最低能量构象
    """
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return None
    mol = Chem.AddHs(mol)

    # ETKDGv3 参数: 对糖尤其重要的几个开关
    params = AllChem.ETKDGv3()
    params.randomSeed = seed
    params.useSmallRingTorsions = True    # 呋喃糖 5 元环扭转校正
    params.useBasicKnowledge = True       # 键长/键角先验
    params.enforceChirality = True        # 强制立体化学一致
    params.pruneRmsThresh = 0.5           # 去重近重复构象 (Å)

    conf_ids = list(AllChem.EmbedMultipleConfs(mol, numConfs=num_confs, params=params))

    # 兜底: 随机初始坐标再试一次
    if not conf_ids:
        params.useRandomCoords = True
        conf_ids = list(AllChem.EmbedMultipleConfs(mol, numConfs=num_confs, params=params))

    if not conf_ids:
        return None

    # MMFF94s 优化 (sugars/糖苷首选)
    energies = []
    ff_used = None
    try:
        props = AllChem.MMFFGetMoleculeProperties(mol, mmffVariant='MMFF94s')
        if props is None:
            raise RuntimeError('MMFF params unavailable')
        for cid in conf_ids:
            ff = AllChem.MMFFGetMoleculeForceField(mol, props, confId=cid)
            if ff is None:
                continue
            ff.Minimize(maxIts=500)
            energies.append((cid, ff.CalcEnergy()))
        ff_used = 'MMFF94s'
    except Exception:
        energies.clear()

    # UFF 兜底 (极少数有奇怪原子的情况)
    if not energies:
        for cid in conf_ids:
            try:
                ff = AllChem.UFFGetMoleculeForceField(mol, confId=cid)
                if ff is None:
                    continue
                ff.Minimize(maxIts=500)
                energies.append((cid, ff.CalcEnergy()))
            except Exception:
                pass
        ff_used = 'UFF'

    if not energies:
        return None

    energies.sort(key=lambda x: x[1])
    best_cid, best_energy = energies[0]

    # 移除其他构象, 只留最低能那个; 设为 confId=0 方便写入
    keep_conf = Chem.Conformer(mol.GetConformer(best_cid))
    mol.RemoveAllConformers()
    mol.AddConformer(keep_conf, assignId=True)

    return mol, best_energy, ff_used


def write_sdf(mol, slug: str, smi: str, energy: float, ff: str, out_path: Path):
    """写单构象 SDF, 附带元数据作为 SD tags"""
    mol.SetProp('_Name', slug)
    mol.SetProp('SMILES', smi)
    mol.SetProp('InChIKey', Chem.MolToInchiKey(mol))
    mol.SetProp('MolecularFormula', Chem.rdMolDescriptors.CalcMolFormula(mol))
    mol.SetProp('energy_kcal_mol', f'{energy:.3f}')
    mol.SetProp('force_field', ff)
    mol.SetProp('embed_method', 'ETKDGv3')
    writer = Chem.SDWriter(str(out_path))
    writer.write(mol)
    writer.close()


# ─── 主流程 ───────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description='从 sugars.html 批量生成 3D SDF 文件',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument('html', type=Path, help='sugars.html 路径')
    ap.add_argument('-o', '--out-dir', type=Path, default=Path('./molecules_3d'),
                    help='SDF 输出目录')
    ap.add_argument('-n', '--num-confs', type=int, default=20,
                    help='每分子嵌入的构象数 (多 = 更准, 但更慢)')
    ap.add_argument('--seed', type=int, default=42, help='ETKDG 随机种子')
    ap.add_argument('--overwrite', action='store_true', help='覆盖已存在的 SDF')
    ap.add_argument('--only', help='只处理匹配此正则的 slug')
    args = ap.parse_args()

    if not args.html.exists():
        sys.exit(f'文件不存在: {args.html}')

    smiles = extract_smiles_dict(args.html)
    print(f'提取到 {len(smiles)} 条 SMILES')

    if args.only:
        pat = re.compile(args.only)
        smiles = {k: v for k, v in smiles.items() if pat.search(k)}
        print(f'筛选到 {len(smiles)} 条 (匹配 /{args.only}/)')

    if not smiles:
        sys.exit('没有要处理的 SMILES')

    args.out_dir.mkdir(parents=True, exist_ok=True)

    ok = skip = fail = 0
    t0 = time.time()
    fails = []

    for i, (slug, smi) in enumerate(smiles.items(), 1):
        out_path = args.out_dir / f'{slug}_3d.sdf'
        prefix = f'[{i:3d}/{len(smiles)}] {slug:40s}'

        if out_path.exists() and not args.overwrite:
            print(f'{prefix} SKIP (已存在)')
            skip += 1
            continue

        t_mol = time.time()
        try:
            result = embed_and_optimize(smi, args.num_confs, args.seed)
            if result is None:
                print(f'{prefix} FAIL (嵌入/优化失败)')
                fail += 1
                fails.append(slug)
                continue
            mol, energy, ff = result
            write_sdf(mol, slug, smi, energy, ff, out_path)
            dt = time.time() - t_mol
            print(f'{prefix} OK   E={energy:+8.2f} kcal/mol  {ff:<7s}  {dt:5.1f}s')
            ok += 1
        except Exception as e:
            print(f'{prefix} FAIL ({type(e).__name__}: {e})')
            fail += 1
            fails.append(slug)

    total = time.time() - t0
    print(f'\n完成: {ok} ok, {skip} skipped, {fail} failed  ({total:.1f}s 总计)')
    if fails:
        print('失败列表:')
        for s in fails:
            print(f'  - {s}')
    return 0 if fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
