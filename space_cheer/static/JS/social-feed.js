/* Feed social: like AJAX, preview de imágenes al publicar, modal compartir.
   CSRF: cookie legible porque CSRF_COOKIE_HTTPONLY=False (decisión S25). */
(function () {
  'use strict';

  function getCookie(name) {
    var m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? decodeURIComponent(m.pop()) : '';
  }

  document.addEventListener('DOMContentLoaded', function () {
    // ── Like toggle ──
    document.querySelectorAll('[data-like-url]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (btn.disabled) return; // ya hay una petición en curso, ignorar doble click
        btn.disabled = true;
        fetch(btn.dataset.likeUrl, {
          method: 'POST',
          headers: { 'X-CSRFToken': getCookie('csrftoken') },
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            var icon = btn.querySelector('i');
            icon.className = data.liked ? 'bi bi-heart-fill text-danger' : 'bi bi-heart';
            btn.querySelector('[data-like-count]').textContent = data.like_count;
          })
          .catch(function () { /* silencioso: el contador simplemente no cambia */ })
          .finally(function () { btn.disabled = false; });
      });
    });

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
