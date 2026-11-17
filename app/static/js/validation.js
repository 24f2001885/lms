/*
FILE PURPOSE: Progressive enhancement for client-side validation (TDR 7: small scripts
that MIRROR server rules but never replace them). Without JavaScript the browser still
validates from the same HTML5 attributes and the server always re-validates.
*/
(function () {
  "use strict";

  function loadConfig() {
    var el = document.getElementById("validation-config");
    if (!el || !el.textContent) {
      console.warn("[validation] #validation-config missing");
      return null;
    }
    try {
      return JSON.parse(el.textContent);
    } catch (err) {
      console.warn("[validation] invalid #validation-config JSON");
      return null;
    }
  }

  function formatMsg(template, params) {
    if (!template) return "Invalid value.";
    return template.replace(/\{(\w+)\}/g, function (_, key) {
      return params && params[key] !== undefined ? String(params[key]) : "";
    });
  }

  function getFieldLabel(form, field) {
    if (field.id) {
      var lbl = form.querySelector('label[for="' + field.id + '"]');
      if (lbl) {
        return lbl.textContent.replace(/\((required|optional)\)/gi, "").trim();
      }
    }
    return field.name || "Field";
  }

  function countDecimals(raw) {
    var parts = String(raw).trim().split(".");
    return parts.length === 2 ? parts[1].length : 0;
  }

  function isValidDateTimeLocal(val) {
    var m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(val);
    if (!m) return false;
    var year = parseInt(m[1], 10);
    var month = parseInt(m[2], 10);
    var day = parseInt(m[3], 10);
    var hour = parseInt(m[4], 10);
    var minute = parseInt(m[5], 10);
    if (month < 1 || month > 12 || day < 1 || day > 31) return false;
    if (hour < 0 || hour > 23 || minute < 0 || minute > 59) return false;
    var dt = new Date(Date.UTC(year, month - 1, day));
    return (
      dt.getUTCFullYear() === year &&
      dt.getUTCMonth() === month - 1 &&
      dt.getUTCDate() === day
    );
  }

  function checkField(form, field, cfg) {
    if (field.disabled || field.type === "hidden" || field.type === "submit" || field.type === "button") {
      return null;
    }
    var msgs = cfg.messages || {};
    var raw = field.value || "";
    var val = field.type === "password" ? raw : raw.trim();

    if (field.type === "radio" || field.type === "checkbox") {
      if (field.required) {
        var group = form.querySelectorAll('input[name="' + field.name + '"]');
        var anyChecked = Array.prototype.some.call(group, function (el) {
          return el.checked;
        });
        if (!anyChecked) return formatMsg(msgs.required);
      }
      return null;
    }

    if (field.required && val.length === 0) {
      return formatMsg(msgs.required);
    }
    if (val.length === 0) {
      if (field.validity && field.validity.badInput) {
        return formatMsg(msgs.invalid_number);
      }
      return null;
    }

    var isMultiline = field.tagName === "TEXTAREA";
    for (var i = 0; i < val.length; i++) {
      var code = val.charCodeAt(i);
      if (code < 32 || code === 127 || (code >= 128 && code <= 159)) {
        if (isMultiline && (val[i] === "\n" || val[i] === "\r" || val[i] === "\t")) {
          continue;
        }
        return formatMsg(msgs.unsafe_characters);
      }
    }

    var minLen = field.getAttribute("minlength");
    var maxLen = field.getAttribute("maxlength");
    var isNewPassword = field.getAttribute("autocomplete") === "new-password";

    if (isNewPassword) {
      var pMin = minLen ? parseInt(minLen, 10) : (cfg.limits.password_min || 8);
      var pMax = maxLen ? parseInt(maxLen, 10) : (cfg.limits.password_max || 128);
      if (val.length < pMin) return formatMsg(msgs.password_too_short, { min: pMin });
      if (val.length > pMax) return formatMsg(msgs.password_too_long, { max: pMax });
      if (!/[A-Za-z]/.test(val)) return formatMsg(msgs.password_no_letter);
      if (!/[0-9]/.test(val)) return formatMsg(msgs.password_no_digit);
    } else {
      if (minLen !== null && maxLen !== null) {
        var mn = parseInt(minLen, 10);
        var mx = parseInt(maxLen, 10);
        if (val.length < mn || val.length > mx) {
          return formatMsg(msgs.between_length, { min: mn, max: mx });
        }
      } else if (minLen !== null && val.length < parseInt(minLen, 10)) {
        return formatMsg(msgs.min_length, { min: parseInt(minLen, 10) });
      } else if (maxLen !== null && val.length > parseInt(maxLen, 10)) {
        return formatMsg(msgs.max_length, { max: parseInt(maxLen, 10) });
      }
    }

    if (field.type === "email") {
      var emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRe.test(val)) return formatMsg(msgs.invalid_email);
    }

    if (field.type === "number" || field.getAttribute("inputmode") === "decimal" || field.getAttribute("inputmode") === "numeric") {
      var num = Number(val);
      if (isNaN(num)) return formatMsg(msgs.invalid_number);
      var stepAttr = field.getAttribute("step");
      if (stepAttr && stepAttr !== "any" && stepAttr.indexOf(".") !== -1) {
        var allowedPlaces = stepAttr.split(".")[1].length;
        if (countDecimals(val) > allowedPlaces) {
          return formatMsg(msgs.too_many_decimals, { places: allowedPlaces });
        }
      }
      var minAttr = field.getAttribute("min");
      var maxAttr = field.getAttribute("max");
      if (minAttr !== null && maxAttr !== null) {
        if (num < Number(minAttr) || num > Number(maxAttr)) {
          return formatMsg(msgs.between_value, { min: minAttr, max: maxAttr });
        }
      } else if (minAttr !== null && num < Number(minAttr)) {
        return formatMsg(msgs.min_value, { min: minAttr });
      } else if (maxAttr !== null && num > Number(maxAttr)) {
        return formatMsg(msgs.max_value, { max: maxAttr });
      }
    }

    var patternAttr = field.getAttribute("pattern");
    if (patternAttr) {
      var anchored = patternAttr;
      if (anchored.charAt(0) !== "^") anchored = "^(?:" + anchored + ")$";
      try {
        var re = new RegExp(anchored);
        if (!re.test(val)) {
          var titleAttr = field.getAttribute("title") || "";
          return formatMsg(msgs.pattern_mismatch, { title: titleAttr });
        }
      } catch (e) {
        /* ignore invalid pattern */
      }
    }

    if (field.type === "datetime-local" || field.getAttribute("data-datetime-local") === "true") {
      if (!isValidDateTimeLocal(val)) return formatMsg(msgs.invalid_datetime);
    }

    var ruleSpec = field.getAttribute("data-rule");
    if (ruleSpec) {
      var rules = ruleSpec.split("|");
      for (var r = 0; r < rules.length; r++) {
        var parts = rules[r].split(":");
        var rName = parts[0];
        var otherName = parts[1];
        var otherField = form.elements[otherName] || document.getElementById(otherName);
        if (!otherField || !otherField.value) continue;
        var otherVal = otherField.type === "password" ? otherField.value : otherField.value.trim();
        if (!otherVal) continue;
        var lbl = getFieldLabel(form, field);
        var otherLbl = getFieldLabel(form, otherField);
        if (rName === "match" && val !== otherVal) {
          return formatMsg(msgs.passwords_mismatch);
        }
        if (rName === "different" && val === otherVal) {
          return formatMsg(msgs.password_same_as_current);
        }
        if (rName === "after" && !(val > otherVal)) {
          if (field.name === "end_at") return formatMsg(msgs.end_after_start);
          return formatMsg(msgs.rule_after, { label: lbl, other: otherLbl });
        }
        if (rName === "not-before" && val < otherVal) {
          return formatMsg(msgs.rule_not_before, { label: lbl, other: otherLbl });
        }
        if (rName === "not-after" && val > otherVal) {
          return formatMsg(msgs.rule_not_after, { label: lbl, other: otherLbl });
        }
      }
    }

    return null;
  }

  function renderFieldState(field, errorMsg) {
    var id = field.id || field.name;
    var errId = id + "-error";
    var errEl = document.getElementById(errId);
    if (!errEl && field.parentNode) {
      errEl = document.createElement("div");
      errEl.id = errId;
      errEl.className = "invalid-feedback";
      field.parentNode.appendChild(errEl);
    }
    var desc = (field.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
    if (errorMsg) {
      field.classList.add("is-invalid");
      field.setAttribute("aria-invalid", "true");
      if (desc.indexOf(errId) === -1) desc.push(errId);
      field.setAttribute("aria-describedby", desc.join(" "));
      if (errEl) {
        errEl.textContent = "Error: " + errorMsg;
        errEl.setAttribute("role", "alert");
      }
    } else {
      field.classList.remove("is-invalid");
      field.removeAttribute("aria-invalid");
      if (errEl) {
        errEl.textContent = "";
        errEl.removeAttribute("role");
      }
    }
  }

  function updateSummary(form, errors) {
    var summary = form.querySelector("[data-error-summary]");
    if (!summary) {
      if (errors.length > 0 && errors[0].field.focus) errors[0].field.focus();
      return;
    }
    while (summary.firstChild) summary.removeChild(summary.firstChild);
    if (errors.length === 0) {
      summary.classList.add("d-none");
      return;
    }
    summary.classList.remove("d-none");
    var heading = document.createElement("p");
    heading.className = "fw-bold mb-1";
    heading.textContent = "Please fix the following errors:";
    summary.appendChild(heading);
    var ul = document.createElement("ul");
    ul.className = "mb-0";
    errors.forEach(function (item) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = "#" + (item.field.id || item.field.name);
      a.textContent = getFieldLabel(form, item.field) + ": " + item.message;
      a.addEventListener("click", function (ev) {
        ev.preventDefault();
        item.field.focus();
      });
      li.appendChild(a);
      ul.appendChild(li);
    });
    summary.appendChild(ul);
    summary.focus();
  }

  function initPasswordHelper(field, cfg) {
    var targetId = field.getAttribute("data-strength-target");
    if (!targetId) return;
    var target = document.getElementById(targetId);
    if (!target) return;
    var pMin = cfg.limits.password_min || 8;
    field.addEventListener("input", function () {
      var v = field.value || "";
      var ok = v.length >= pMin && /[A-Za-z]/.test(v) && /[0-9]/.test(v);
      target.textContent = ok
        ? "Looks good"
        : "At least " + pMin + " characters, a letter and a number";
    });
  }

  function initCharCounter(field, cfg) {
    var maxAttr = field.getAttribute("maxlength");
    if (!maxAttr || !field.parentNode) return;
    var counter = field.parentNode.querySelector(".char-counter");
    if (!counter) return;
    var max = parseInt(maxAttr, 10);
    var tpl = (cfg.messages && cfg.messages.char_counter) || "{count} of {max} characters";
    function refresh() {
      var len = (field.value || "").length;
      var remaining = max - len;
      if (remaining <= 20 || remaining === max) {
        counter.setAttribute("aria-live", "polite");
      } else {
        counter.removeAttribute("aria-live");
      }
      counter.textContent = formatMsg(tpl, { count: len, max: max });
    }
    field.addEventListener("input", refresh);
    refresh();
  }

  function initSubmitOnce(form) {
    var clickedBtn = null;
    var buttons = form.querySelectorAll('button[type="submit"][data-submit-once], input[type="submit"][data-submit-once]');
    Array.prototype.forEach.call(buttons, function (btn) {
      btn.addEventListener("click", function () {
        clickedBtn = btn;
      });
    });

    form.addEventListener("submit", function (ev) {
      if (ev.defaultPrevented) return;
      if (form.getAttribute("data-submitting") === "true") {
        ev.preventDefault();
        return;
      }
      form.setAttribute("data-submitting", "true");
      var activeBtn = clickedBtn || buttons[0];
      if (activeBtn && activeBtn.name) {
        var hidden = form.querySelector('input[type="hidden"][data-submit-mirror="true"]');
        if (!hidden) {
          hidden = document.createElement("input");
          hidden.type = "hidden";
          hidden.setAttribute("data-submit-mirror", "true");
          form.appendChild(hidden);
        }
        hidden.name = activeBtn.name;
        hidden.value = activeBtn.value || "";
      }
      setTimeout(function () {
        Array.prototype.forEach.call(buttons, function (btn) {
          if (!btn.getAttribute("data-original-text")) {
            btn.setAttribute("data-original-text", btn.textContent || btn.value || "");
          }
          btn.disabled = true;
          btn.setAttribute("aria-busy", "true");
          if (btn.tagName === "BUTTON") {
            btn.textContent = "Please wait...";
          } else {
            btn.value = "Please wait...";
          }
        });
      }, 0);
    });

    window.addEventListener("pageshow", function (ev) {
      if (ev.persisted) {
        form.removeAttribute("data-submitting");
        Array.prototype.forEach.call(buttons, function (btn) {
          btn.disabled = false;
          btn.removeAttribute("aria-busy");
          var orig = btn.getAttribute("data-original-text");
          if (orig) {
            if (btn.tagName === "BUTTON") btn.textContent = orig;
            else btn.value = orig;
          }
        });
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var cfg = loadConfig();
    if (!cfg) return;

    var allForms = document.querySelectorAll("form");
    Array.prototype.forEach.call(allForms, function (form) {
      if (form.hasAttribute("data-validate")) {
        form.noValidate = true;
        var controls = form.querySelectorAll("input, select, textarea");
        Array.prototype.forEach.call(controls, function (field) {
          if (field.getAttribute("autocomplete") === "new-password") {
            initPasswordHelper(field, cfg);
          }
          if (field.hasAttribute("maxlength")) {
            initCharCounter(field, cfg);
          }
          field.addEventListener("blur", function () {
            field.setAttribute("data-touched", "true");
            var err = checkField(form, field, cfg);
            renderFieldState(field, err);
          });
          field.addEventListener("input", function () {
            if (field.classList.contains("is-invalid") || field.getAttribute("data-touched") === "true") {
              var err = checkField(form, field, cfg);
              renderFieldState(field, err);
            }
          });
        });

        form.addEventListener("submit", function (ev) {
          var errors = [];
          Array.prototype.forEach.call(controls, function (field) {
            var err = checkField(form, field, cfg);
            renderFieldState(field, err);
            if (err) errors.push({ field: field, message: err });
          });
          if (errors.length > 0) {
            ev.preventDefault();
            updateSummary(form, errors);
          } else {
            updateSummary(form, []);
          }
        });
      }
      initSubmitOnce(form);
    });
  });
})();
