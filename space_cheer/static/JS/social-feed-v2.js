/* Portal Social v2 — Feed: reacciones, notificaciones, preview de imágenes,
   modal compartir y scroll infinito.
   CSRF: cookie legible porque CSRF_COOKIE_HTTPONLY=False (decisión S25). */
(function () {
  'use strict';

  function getCookie(name) {
    var m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? decodeURIComponent(m.pop()) : '';
  }

  var REACTIONS = {
    APPLAUSE: '👏 Aplaudiste', FIRE: '🔥 ¡Fuego!', STAR: '⭐ Increíble',
    HEART: '❤️ Me encanta', MUSCLE: '💪 ¡Ánimo!'
  };

  function setReactionButtonState(wrap, reaction) {
    var mainBtn = wrap.querySelector('[data-reaction-main]');
    if (reaction) {
      mainBtn.textContent = REACTIONS[reaction] || '👏 Reaccionaste';
      mainBtn.classList.add('has-reacted');
      mainBtn.dataset.currentReaction = reaction;
    } else {
      mainBtn.textContent = '👏 Reaccionar';
      mainBtn.classList.remove('has-reacted');
      delete mainBtn.dataset.currentReaction;
    }
  }

  function sendReaction(wrap, reaction) {
    if (wrap.dataset.reacting === '1') return; // petición en curso, ignorar doble click
    wrap.dataset.reacting = '1';
    var url = wrap.dataset.likeUrl;
    fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': getCookie('csrftoken'),
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: 'reaction=' + encodeURIComponent(reaction)
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        setReactionButtonState(wrap, data.reaction);
        var article = wrap.closest('[data-post-card]');
        if (article) {
          var countEl = article.querySelector('[data-like-count]');
          if (countEl) countEl.textContent = data.like_count;
        }
      })
      .catch(function () { /* silencioso: el contador simplemente no cambia */ })
      .finally(function () { delete wrap.dataset.reacting; });
  }

  function wireReactionPicker(wrap) {
    var picker = wrap.querySelector('[data-reaction-picker]');
    var mainBtn = wrap.querySelector('[data-reaction-main]');
    var hideTimer = null;

    function show() { clearTimeout(hideTimer); picker.hidden = false; }
    function hide() { hideTimer = setTimeout(function () { picker.hidden = true; }, 150); }

    wrap.addEventListener('mouseenter', show);
    wrap.addEventListener('mouseleave', hide);
    picker.addEventListener('mouseenter', function () { clearTimeout(hideTimer); });
    picker.addEventListener('mouseleave', hide);

    picker.querySelectorAll('[data-reaction]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        picker.hidden = true;
        sendReaction(wrap, btn.dataset.reaction);
      });
    });

    mainBtn.addEventListener('click', function () {
      var current = mainBtn.dataset.currentReaction;
      sendReaction(wrap, current || 'APPLAUSE');
    });
  }

  function wireNotifDropdown(toggle, panel) {
    if (!toggle || !panel) return;
    toggle.addEventListener('click', function (ev) {
      ev.stopPropagation();
      var willOpen = panel.hidden;
      panel.hidden = !willOpen;
      toggle.classList.toggle('is-open', willOpen);
    });
    document.addEventListener('click', function (ev) {
      if (!panel.hidden && !panel.contains(ev.target) && ev.target !== toggle) {
        panel.hidden = true;
        toggle.classList.remove('is-open');
      }
    });
  }

  function wireLoadMore() {
    var btn = document.querySelector('[data-load-more]');
    if (!btn) return;
    btn.addEventListener('click', function () {
      var nextUrl = btn.dataset.nextUrl;
      if (!nextUrl) return;
      btn.disabled = true;
      btn.textContent = 'Cargando…';
      fetch(nextUrl, { headers: { 'X-Requested-With': 'fetch' } })
        .then(function (r) { return r.text(); })
        .then(function (html) {
          var wrapper = document.getElementById('sc-v2-posts');
          var holder = btn.closest('[data-load-more-wrap]');
          var temp = document.createElement('div');
          temp.innerHTML = html;
          var newNextUrl = temp.querySelector('[data-next-url]');
          temp.querySelectorAll('[data-post-card]').forEach(function (card) {
            wrapper.appendChild(card);
            initPostCard(card);
          });
          if (newNextUrl) {
            btn.dataset.nextUrl = newNextUrl.dataset.nextUrl;
            btn.disabled = false;
            btn.textContent = 'Ver más publicaciones';
          } else {
            holder.remove();
          }
        })
        .catch(function () {
          btn.disabled = false;
          btn.textContent = 'Ver más publicaciones';
        });
    });
  }

  function initPostCard(card) {
    var wrap = card.querySelector('[data-reaction-wrap]');
    if (wrap) wireReactionPicker(wrap);
    var commentFocusBtn = card.querySelector('[data-comment-focus]');
    if (commentFocusBtn) {
      commentFocusBtn.addEventListener('click', function () {
        var input = card.querySelector('.sc-v2-comment-form input');
        if (input) input.focus();
      });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-post-card]').forEach(initPostCard);

    wireNotifDropdown(document.querySelector('[data-notif-toggle]'), document.querySelector('[data-notif-panel]'));
    wireLoadMore();

    // ── Preview de imágenes + límite 4 ──
    var input = document.getElementById('postImagesInput');
    var preview = document.getElementById('postImagesPreview');
    if (input && preview) {
      input.addEventListener('change', function () {
        preview.innerHTML = '';
        if (input.files.length > 4) {
          input.value = '';
          preview.textContent = 'Máximo 4 imágenes.';
          return;
        }
        Array.prototype.forEach.call(input.files, function (file) {
          var img = document.createElement('img');
          img.className = 'sc-img-preview-thumb';
          img.src = URL.createObjectURL(file);
          preview.appendChild(img);
        });
      });
    }

    // ── Modal compartir: setear action del form ──
    var shareModal = document.getElementById('shareModal');
    if (shareModal) {
      shareModal.addEventListener('show.bs.modal', function (ev) {
        var trigger = ev.relatedTarget;
        if (trigger && trigger.dataset.shareUrl) {
          shareModal.querySelector('form').action = trigger.dataset.shareUrl;
        }
      });
    }
  });
})();
