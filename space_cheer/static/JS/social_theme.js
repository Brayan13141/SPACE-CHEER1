/* Portal Social v2: acento de color + densidad, client-side (localStorage).
   No persiste en servidor todavía — eso se decide con Apariencia.dc.html. */
(function () {
  'use strict';

  var ACCENTS = {
    purpura: { acc: '#a855f7', acc2: '#e879f9', soft: 'rgba(168,85,247,.16)', ink: '#180627' },
    cyan:    { acc: '#22d3ee', acc2: '#818cf8', soft: 'rgba(34,211,238,.14)', ink: '#04202a' },
    rosa:    { acc: '#ec4899', acc2: '#fb7185', soft: 'rgba(236,72,153,.15)', ink: '#2b0617' },
    verde:   { acc: '#34d399', acc2: '#2dd4bf', soft: 'rgba(52,211,153,.14)', ink: '#032019' },
    azul:    { acc: '#60a5fa', acc2: '#38bdf8', soft: 'rgba(96,165,250,.15)', ink: '#071c33' },
    ambar:   { acc: '#fbbf24', acc2: '#fb923c', soft: 'rgba(251,191,36,.14)', ink: '#2a1a02' }
  };

  function applyAccent(root, id) {
    var a = ACCENTS[id] || ACCENTS.purpura;
    root.style.setProperty('--acc', a.acc);
    root.style.setProperty('--acc2', a.acc2);
    root.style.setProperty('--acc-soft', a.soft);
    root.style.setProperty('--acc-ink', a.ink);
    root.querySelectorAll('[data-accent-dot]').forEach(function (dot) {
      dot.classList.toggle('is-active', dot.dataset.accentDot === id);
    });
    try { localStorage.setItem('sc-accent', id); } catch (e) { /* localStorage no disponible */ }
  }

  function applyDensity(root, density, toggleBtn) {
    root.classList.toggle('sc-feed-compact', density === 'compacta');
    if (toggleBtn) {
      toggleBtn.textContent = 'Densidad: ' + (density === 'compacta' ? 'Compacta' : 'Cómoda');
    }
    try { localStorage.setItem('sc-density', density); } catch (e) { /* localStorage no disponible */ }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var root = document.querySelector('.sc-v2');
    if (!root) return;

    var savedAccent = 'purpura';
    var savedDensity = root.dataset.initialDensity === 'COMPACT' ? 'compacta' : 'comoda';
    try {
      savedAccent = localStorage.getItem('sc-accent') || savedAccent;
      savedDensity = localStorage.getItem('sc-density') || savedDensity;
    } catch (e) { /* localStorage no disponible */ }

    applyAccent(root, savedAccent);
    applyDensity(root, savedDensity, document.querySelector('[data-density-toggle]'));

    root.querySelectorAll('[data-accent-dot]').forEach(function (dot) {
      dot.addEventListener('click', function () { applyAccent(root, dot.dataset.accentDot); });
    });

    var densityBtn = document.querySelector('[data-density-toggle]');
    if (densityBtn) {
      densityBtn.addEventListener('click', function () {
        var current = root.classList.contains('sc-feed-compact') ? 'compacta' : 'comoda';
        applyDensity(root, current === 'compacta' ? 'comoda' : 'compacta', densityBtn);
      });
    }
  });
})();
