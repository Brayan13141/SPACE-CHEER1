/* sc-submit-guard.js — Space Cheer: evita doble click / doble submit.
   Deshabilita los botones de submit de un <form> en cuanto se envía, para que
   un segundo click mientras la petición está en curso no dispare un POST duplicado.
   Vanilla JS, sin dependencias, cargado globalmente en base.html. */
(function () {
  'use strict';

  var LOADING_CLASS = 'sc-btn-loading';

  function lockButton(btn) {
    if (btn.disabled) return;
    btn.disabled = true;
    btn.classList.add(LOADING_CLASS);
  }

  // Delegado en document: cubre todos los <form> de la página, incluidos los
  // insertados dinámicamente (modales, fragments cargados por AJAX), porque
  // el evento 'submit' burbujea.
  document.addEventListener('submit', function (e) {
    // Si algo más (p.ej. sc-validation.js) ya bloqueó el submit por datos
    // inválidos, no tocar los botones — deben quedar clicables para reintentar.
    if (e.defaultPrevented) return;
    var form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(lockButton);
  });

  // Si el usuario navega hacia atrás y el navegador restaura la página desde
  // bfcache, los botones pueden quedar deshabilitados de la navegación previa.
  window.addEventListener('pageshow', function (e) {
    if (!e.persisted) return;
    document.querySelectorAll('.' + LOADING_CLASS).forEach(function (btn) {
      btn.disabled = false;
      btn.classList.remove(LOADING_CLASS);
    });
  });
})();
