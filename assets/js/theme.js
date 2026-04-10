/* ── MattHub theme toggle ───────────────────────────── */
const browserPref = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';

const setTheme = (theme) => {
  const t = theme || localStorage.getItem('theme') || browserPref;
  if (t === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
    document.getElementById('theme-toggle').textContent = '☀️';
  } else {
    document.documentElement.removeAttribute('data-theme');
    document.getElementById('theme-toggle').textContent = '🌙';
  }
};

const toggleTheme = () => {
  const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  localStorage.setItem('theme', next);
  setTheme(next);
};

setTheme();