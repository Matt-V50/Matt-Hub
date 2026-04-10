/* ── MattHub theme toggle ───────────────────────────── */
const browserPref = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';

// 立即设置 data-theme，避免页面闪烁（FOUC）
const _t = localStorage.getItem('theme') || browserPref;
if (_t === 'dark') document.documentElement.setAttribute('data-theme', 'dark');

// DOM ready 后再更新按钮 emoji
function _applyToggleEmoji() {
  const btn = document.getElementById('theme-toggle');
  if (!btn) return;
  btn.textContent = document.documentElement.getAttribute('data-theme') === 'dark' ? '☀️' : '🌙';
}

const setTheme = (theme) => {
  const t = theme || localStorage.getItem('theme') || browserPref;
  if (t === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  } else {
    document.documentElement.removeAttribute('data-theme');
  }
  _applyToggleEmoji();
};

const toggleTheme = () => {
  const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  localStorage.setItem('theme', next);
  setTheme(next);
};

document.addEventListener('DOMContentLoaded', _applyToggleEmoji);