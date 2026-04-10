const charty = (function() {
  const palette = [
    '#4878d0','#ee854a','#6acc64','#d65f5f','#956cb4','#8c613c','#dc7ec0','#797979','#d5bb67','#82c6e2',
    '#7a9fdc','#f4a876','#8fdb8a','#e38888','#b18fca','#a9806a','#e8a4d6','#9a9a9a','#e3d08f','#a7dbee',
    '#2e5aa8','#d66b28','#4ab345','#c03a3a','#7a4e9d','#6f4623','#ca5aa9','#5a5a5a','#c4a73f','#5bb0d5',
    '#1d4580','#b5561a','#359a2e','#a02525','#5f3880','#543316','#b03d91','#3e3e3e','#a88d25','#3a95bf'
  ];

  // Compatible with shared theme.js — reads data-theme attribute
  function getCurrentTheme() {
    const html = document.documentElement;
    if (html.getAttribute('data-theme') === 'dark' ||
        html.classList.contains('dark') ||
        document.body.getAttribute('data-theme') === 'dark') {
      return 'dark';
    }
    return 'light';
  }

  function getThemedLayoutBase() {
    const isDark = getCurrentTheme() === 'dark';
    return {
      font: { family: 'Times New Roman, serif', size: 14, color: isDark ? '#e0e0e0' : '#000' },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: isDark ? '#1e1e1e' : '#fff',
      margin: { t: 60, b: 100, l: 70, r: 30 },
      xaxis: {
        showline: true, linewidth: 1.5, linecolor: isDark ? '#555' : '#000', mirror: true,
        ticks: 'outside', tickwidth: 1, tickcolor: isDark ? '#555' : '#000',
        tickfont: { size: 11, color: isDark ? '#ccc' : '#000' },
        showgrid: false, tickangle: -30
      },
      yaxis: {
        showline: true, linewidth: 1.5, linecolor: isDark ? '#555' : '#000', mirror: true,
        ticks: 'outside', tickwidth: 1, tickcolor: isDark ? '#555' : '#000',
        tickfont: { size: 11, color: isDark ? '#ccc' : '#000' },
        showgrid: true, gridcolor: isDark ? '#333' : '#e0e0e0', gridwidth: 0.5, zeroline: false
      },
      legend: {
        font: { size: 11, color: isDark ? '#ccc' : '#000' },
        bordercolor: isDark ? '#555' : '#ccc', borderwidth: 1,
        bgcolor: isDark ? 'rgba(30,30,30,0.9)' : 'rgba(255,255,255,0.9)'
      }
    };
  }

  function lightenColor(hex, factor) {
    const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    return '#' + [r,g,b].map(x => Math.round(x + (255-x)*factor).toString(16).padStart(2,'0')).join('');
  }

  return { palette, getCurrentTheme, getThemedLayoutBase, lightenColor };
})();

window.charty = charty;