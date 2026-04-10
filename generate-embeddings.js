#!/usr/bin/env node
/**
 * generate-embeddings.js
 *
 * 扫描 pages/ 目录下所有 .html 文件，读取 meta 标签，
 * 生成 site.json（页面清单）和 embeddings.json（向量索引）。
 *
 * 每个页面 .html 需包含：
 *   <title>页面名称</title>
 *   <meta name="description" content="...中英文描述...">
 *   <meta name="icon"        content="🔬">
 *   <meta name="tag"         content="工具">
 *   <meta name="pinned"      content="true">   ← 可选，默认 false
 *
 * 用法：
 *   npm run embeddings
 */

import { pipeline, env } from '@xenova/transformers';
import { readFileSync, writeFileSync, readdirSync, mkdirSync } from 'fs';
import { join } from 'path';

env.allowLocalModels = false;

// ── 1. 扫描 pages/ 目录 ────────────────────────────────
const PAGES_DIR = 'pages';

function getMeta(html, name) {
  const m = html.match(new RegExp(`<meta[^>]+name=["']${name}["'][^>]+content=["']([^"']+)["']`, 'i'))
           || html.match(new RegExp(`<meta[^>]+content=["']([^"']+)["'][^>]+name=["']${name}["']`, 'i'));
  return m ? m[1].trim() : null;
}

function getTitle(html) {
  const m = html.match(/<title>([^<]+)<\/title>/i);
  return m ? m[1].trim() : null;
}

let files;
try {
  files = readdirSync(PAGES_DIR).filter(f => f.endsWith('.html'));
} catch {
  console.error(`❌  找不到 ${PAGES_DIR}/ 目录`);
  process.exit(1);
}

if (!files.length) {
  console.error(`❌  ${PAGES_DIR}/ 目录下没有 .html 文件`);
  process.exit(1);
}

const PAGES = [];
for (const file of files) {
  const html = readFileSync(join(PAGES_DIR, file), 'utf8');
  const name = getTitle(html) || file.replace('.html', '');
  const desc = getMeta(html, 'description') || '';
  const icon = getMeta(html, 'icon') || '📄';
  const tag  = getMeta(html, 'tag')  || '其他';
  const pinned = getMeta(html, 'pinned') === 'true';

  PAGES.push({ name, url: `${PAGES_DIR}/${file}`, icon, desc, tag, pinned });
  console.log(`  ✓ ${file}  →  ${name}`);
}

console.log(`\n📄  共找到 ${PAGES.length} 个页面`);

// ── 2. 写出 site.json ──────────────────────────────────
mkdirSync('data', { recursive: true });
writeFileSync('data/site.json', JSON.stringify(PAGES, null, 2));
console.log('📝  site.json 已生成');

// ── 3. 加载模型，计算 embeddings ───────────────────────
console.log('\n⏳  加载模型 paraphrase-multilingual-MiniLM-L12-v2 …');
const extractor = await pipeline(
  'feature-extraction',
  'Xenova/paraphrase-multilingual-MiniLM-L12-v2',
  { quantized: true }
);

const embeddings = [];
for (const [i, page] of PAGES.entries()) {
  const text = `${page.name} ${page.desc} ${page.tag}`;
  // pooling + normalize 已由 pipeline 处理，直接取 data
  const out = await extractor(text, { pooling: 'mean', normalize: true });
  embeddings.push(Array.from(out.data));
  console.log(`  [${i + 1}/${PAGES.length}] ${page.name}`);
}

writeFileSync('data/embeddings.json', JSON.stringify(embeddings));
console.log(`\n✅  embeddings.json 已生成（${PAGES.length} 条，每条 ${embeddings[0].length} 维）`);