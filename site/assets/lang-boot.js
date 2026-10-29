// Redirect before paint to the matching pre-rendered language page.
(function () {
  var saved = null;
  try {
    saved = localStorage.getItem('lang');
  } catch (e) { /* storage blocked: keep English */ }
  var fromUrl = /[?&]lang=(en|ar)(&|$)/.exec(location.search);
  if (fromUrl) saved = fromUrl[1];
  var root = document.documentElement;
  var prerendered = root.dataset.prerendered === 'ar';
  var arabic = saved === 'ar' || (saved !== 'en' && (navigator.language || '').toLowerCase().indexOf('ar') === 0);
  var target = prerendered ? (saved === 'en' ? './' + location.hash : null) : (arabic ? 'ar.html' + location.hash : null);
  if (!target) return;
  try { location.replace(target); }
  catch (e) {
    if (!prerendered) {
      root.lang = 'ar'; root.dir = 'rtl'; root.classList.add('i18n-wait');
      setTimeout(function () { root.classList.remove('i18n-wait'); }, 2500);
    }
  }
})();
