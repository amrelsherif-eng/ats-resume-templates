// Runs before the first paint. Arabic visitors get RTL straight away, and the page stays hidden until
// app.js has applied the Arabic text, so they never see an English flash or a layout jump.
(function () {
  var lang = 'en';
  try {
    var saved = localStorage.getItem('lang');
    if (saved === 'ar' || saved === 'en') lang = saved;
    else if ((navigator.language || '').toLowerCase().indexOf('ar') === 0) lang = 'ar';
  } catch (e) { /* storage blocked: keep English */ }
  if (lang !== 'ar') return;
  var root = document.documentElement;
  root.lang = 'ar';
  root.dir = 'rtl';
  root.classList.add('i18n-wait');
  // Fetch the Arabic font now (normally it starts only after the CSS is applied) so it is ready at reveal.
  ['400', '500', '700'].forEach(function (w) {
    var link = document.createElement('link');
    link.rel = 'preload'; link.as = 'font'; link.type = 'font/woff2'; link.crossOrigin = 'anonymous';
    link.href = 'assets/fonts/ibm-plex-sans-arabic-arabic-' + w + '-normal.woff2';
    document.head.appendChild(link);
  });
  // Safety net: never keep the page hidden if app.js fails to run.
  setTimeout(function () { root.classList.remove('i18n-wait'); }, 2500);
})();
