/**
 * sc-validation.js — Space Cheer client-side form validation
 * Vanilla JS, no dependencies. Works alongside Django's server-side validation.
 *
 * Usage:
 *   ScValidation.init(formElement, {
 *     fieldName: [rule, rule, ...],
 *   });
 *
 * Rule factories live in ScValidation.rules.*
 */
const ScValidation = (() => {
  'use strict';

  // ── Helpers ──────────────────────────────────────────────────────────────

  function getVal(field) {
    if (field.type === 'checkbox') return field.checked;
    return field.value;
  }

  function getFeedbackContainer(field) {
    // Look for an existing .sc-feedback sibling; otherwise append one
    const parent = field.parentElement;
    let fb = parent.querySelector('.sc-feedback');
    if (!fb) {
      fb = document.createElement('div');
      fb.className = 'sc-feedback';
      parent.appendChild(fb);
    }
    return fb;
  }

  function showError(field, msg) {
    field.classList.add('is-invalid');
    field.classList.remove('is-valid');
    const fb = getFeedbackContainer(field);
    fb.innerHTML = `<i class="bi bi-exclamation-circle me-1"></i>${msg}`;
    fb.style.display = 'block';
  }

  function clearError(field) {
    field.classList.remove('is-invalid');
    field.classList.add('is-valid');
    const fb = field.parentElement.querySelector('.sc-feedback');
    if (fb) fb.style.display = 'none';
  }

  function resetField(field) {
    field.classList.remove('is-invalid', 'is-valid');
    const fb = field.parentElement.querySelector('.sc-feedback');
    if (fb) fb.style.display = 'none';
  }

  // ── Core ──────────────────────────────────────────────────────────────────

  function validateField(field, rules) {
    const val = getVal(field);

    // Skip validation for optional empty text fields (only runs required rule)
    if (field.type !== 'checkbox' && val.trim() === '') {
      const hasRequired = rules.some(r => r._isRequired);
      if (!hasRequired) {
        resetField(field);
        return true;
      }
    }

    for (const rule of rules) {
      if (!rule.test(val, field)) {
        showError(field, rule.message);
        return false;
      }
    }
    clearError(field);
    return true;
  }

  /**
   * Attach validation to a form.
   * @param {HTMLFormElement} formEl
   * @param {Object} config  { fieldName: [rule, ...] }
   */
  function init(formEl, config) {
    if (!formEl) return;

    const entries = Object.entries(config);

    entries.forEach(([name, fieldRules]) => {
      const field = formEl.querySelector(`[name="${name}"]`);
      if (!field) return;

      const triggerEvents = field.type === 'checkbox' ? ['change'] : ['blur'];
      triggerEvents.forEach(evt =>
        field.addEventListener(evt, () => validateField(field, fieldRules))
      );
    });

    formEl.addEventListener('submit', e => {
      let allValid = true;
      entries.forEach(([name, fieldRules]) => {
        const field = formEl.querySelector(`[name="${name}"]`);
        if (field && !validateField(field, fieldRules)) allValid = false;
      });
      if (!allValid) {
        e.preventDefault();
        // Safety net: re-enable any submit button a synchronous spinner may have
        // already disabled before this listener ran.
        formEl.querySelectorAll('button[type="submit"]').forEach(btn => {
          btn.disabled = false;
        });
        const firstError = formEl.querySelector('.is-invalid');
        if (firstError) firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    });
  }

  // ── Rule factories ─────────────────────────────────────────────────────────

  const rules = {
    /** Field must not be empty (or checkbox must be checked) */
    required(msg) {
      const rule = {
        test: v => (typeof v === 'boolean' ? v : v.trim() !== ''),
        message: msg,
        _isRequired: true,
      };
      return rule;
    },

    /** Valid email format */
    email(msg) {
      return {
        test: v => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim()),
        message: msg,
      };
    },

    /** Minimum length */
    minLen(n, msg) {
      return { test: v => v.length >= n, message: msg };
    },

    /** Maximum length */
    maxLen(n, msg) {
      return { test: v => v.length <= n, message: msg };
    },

    /** Custom regex */
    pattern(re, msg) {
      return { test: v => re.test(v.trim()), message: msg };
    },

    /** Value must match another field's current value */
    matchField(otherId, msg) {
      return {
        test: v => v === (document.getElementById(otherId)?.value ?? ''),
        message: msg,
      };
    },

    /** Mexican 5-digit postal code */
    zipMx(msg) {
      return { test: v => /^\d{5}$/.test(v.trim()), message: msg };
    },

    /** Optional phone — valid if empty OR matches loose phone pattern */
    phoneMx(msg) {
      return {
        test: v => v.trim() === '' || /^[\+\d\s\-\(\)]{7,15}$/.test(v.trim()),
        message: msg,
      };
    },

    /** Checkbox must be checked */
    checked(msg) {
      return { test: v => v === true, message: msg };
    },

    /** Date must not be in the future */
    notFuture(msg) {
      return {
        test: v => {
          if (!v) return false;
          return new Date(v) <= new Date();
        },
        message: msg,
      };
    },

    /** Date must correspond to at least N years ago */
    minAge(years, msg) {
      return {
        test: v => {
          if (!v) return false;
          const birth = new Date(v);
          const cutoff = new Date();
          cutoff.setFullYear(cutoff.getFullYear() - years);
          return birth <= cutoff;
        },
        message: msg,
      };
    },
  };

  // ── Password strength helper ───────────────────────────────────────────────

  /**
   * Attach a visual strength meter below a password input.
   * @param {string} inputId   id of the <input type="password">
   * @param {string} wrapperId id of a container element where the meter is inserted
   */
  function attachStrengthMeter(inputId, wrapperId) {
    const input = document.getElementById(inputId);
    const wrapper = document.getElementById(wrapperId);
    if (!input || !wrapper) return;

    // Build meter HTML
    wrapper.innerHTML = `
      <div class="sc-strength-meter mt-2">
        <div class="sc-strength-bars d-flex gap-1 mb-1">
          <div class="sc-bar flex-fill"></div>
          <div class="sc-bar flex-fill"></div>
          <div class="sc-bar flex-fill"></div>
          <div class="sc-bar flex-fill"></div>
        </div>
        <div class="sc-strength-label small"></div>
      </div>`;

    const bars = wrapper.querySelectorAll('.sc-bar');
    const label = wrapper.querySelector('.sc-strength-label');

    const levels = [
      { color: '#dc3545', text: 'Muy débil' },
      { color: '#fd7e14', text: 'Débil' },
      { color: '#ffc107', text: 'Aceptable' },
      { color: '#28a745', text: 'Fuerte' },
    ];

    function score(pw) {
      let s = 0;
      if (pw.length >= 8) s++;
      if (/[A-Z]/.test(pw)) s++;
      if (/\d/.test(pw)) s++;
      if (/[^A-Za-z0-9]/.test(pw)) s++;
      return s;
    }

    input.addEventListener('input', () => {
      const pw = input.value;
      const s = pw.length === 0 ? 0 : Math.max(1, score(pw));

      bars.forEach((bar, i) => {
        bar.style.height = '4px';
        bar.style.borderRadius = '2px';
        bar.style.background = i < s ? levels[s - 1].color : 'rgba(255,255,255,0.1)';
        bar.style.transition = 'background 0.3s';
      });

      if (pw.length === 0) {
        label.textContent = '';
      } else {
        label.textContent = levels[s - 1].text;
        label.style.color = levels[s - 1].color;
      }
    });
  }

  return { init, rules, attachStrengthMeter };
})();
