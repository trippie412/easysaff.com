/* ============================================================
   GreenLend — main.js (vanilla JS, no dependencies)
   ============================================================ */
(function () {
  'use strict';

  /* ---------- Utils ---------- */
  function debounce(fn, wait) {
    var t;
    return function () {
      var ctx = this, args = arguments;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, wait);
    };
  }

  function fmtKes(n) {
    return 'KES ' + Number(n || 0).toLocaleString('en-KE');
  }

  /* ---------- 1. Navbar shadow on scroll ---------- */
  function initNavbar() {
    var nav = document.querySelector('.navbar-glass');
    if (!nav) return;
    var onScroll = function () {
      nav.classList.toggle('scrolled', window.scrollY > 10);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  /* ---------- 2. Flash auto-dismiss ---------- */
  function initFlash() {
    document.querySelectorAll('.flash-alert').forEach(function (el) {
      setTimeout(function () {
        el.classList.add('leaving');
        setTimeout(function () { el.remove(); }, 380);
      }, 5000);
    });
  }

  /* ---------- 3. Animated counters ---------- */
  function initCounters() {
    var els = document.querySelectorAll('[data-counter]');
    if (!els.length) return;
    function animate(el) {
      var target = parseFloat(el.getAttribute('data-target') || '0');
      var prefix = el.getAttribute('data-prefix') || '';
      var suffix = el.getAttribute('data-suffix') || '';
      var duration = 1200, start = null;
      function frame(ts) {
        if (!start) start = ts;
        var p = Math.min((ts - start) / duration, 1);
        var eased = 1 - Math.pow(1 - p, 3);
        el.textContent = prefix + Math.round(target * eased).toLocaleString('en-KE') + suffix;
        if (p < 1) requestAnimationFrame(frame);
      }
      requestAnimationFrame(frame);
    }
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            io.unobserve(entry.target);
            animate(entry.target);
          }
        });
      }, { threshold: 0.2 });
      els.forEach(function (el) { io.observe(el); });
    } else {
      els.forEach(animate);
    }
  }

  /* ---------- 4. Canvas bar chart ---------- */
  function initCharts() {
    document.querySelectorAll('canvas[data-chart]').forEach(function (canvas) {
      var labels = [], values = [];
      try { labels = JSON.parse(canvas.getAttribute('data-labels') || '[]'); } catch (e) {}
      try { values = JSON.parse(canvas.getAttribute('data-values') || '[]'); } catch (e) {}
      if (!values.length) {
        canvas.parentElement.innerHTML = '<p class="text-muted small text-center m-0 p-3">No data yet.</p>';
        return;
      }
      drawChart(canvas, labels, values);
      var redraw = debounce(function () { drawChart(canvas, labels, values); }, 200);
      window.addEventListener('resize', redraw);
    });
  }

  function drawChart(canvas, labels, values) {
    var dpr = window.devicePixelRatio || 1;
    var cssW = canvas.clientWidth || canvas.parentElement.clientWidth || 320;
    var cssH = canvas.clientHeight || 220;
    canvas.width = cssW * dpr;
    canvas.height = cssH * dpr;
    var ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);

    var padL = 46, padR = 12, padT = 26, padB = 30;
    var chartW = cssW - padL - padR;
    var chartH = cssH - padT - padB;
    var max = Math.max.apply(null, values) * 1.15 || 1;

    // gridlines + y labels
    ctx.font = '11px Inter, Arial, sans-serif';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    var lines = 4;
    for (var i = 0; i <= lines; i++) {
      var y = padT + chartH - (chartH * i / lines);
      var v = max * i / lines;
      ctx.strokeStyle = '#e2e8f0';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(padL, y);
      ctx.lineTo(cssW - padR, y);
      ctx.stroke();
      ctx.fillStyle = '#94a3b8';
      ctx.fillText(Math.round(v).toLocaleString('en-KE'), padL - 8, y);
    }

    // bars
    var n = values.length;
    var slot = chartW / n;
    var barW = Math.min(slot * 0.58, 44);
    var grad = ctx.createLinearGradient(0, padT, 0, padT + chartH);
    grad.addColorStop(0, '#10b981');
    grad.addColorStop(1, '#047857');

    values.forEach(function (val, idx) {
      var h = (val / max) * chartH;
      var x = padL + slot * idx + (slot - barW) / 2;
      var y = padT + chartH - h;
      var r = Math.min(8, barW / 2);

      ctx.beginPath();
      ctx.moveTo(x, y + r);
      ctx.lineTo(x, padT + chartH - r);
      ctx.quadraticCurveTo(x, padT + chartH, x + r, padT + chartH);
      ctx.lineTo(x + barW - r, padT + chartH);
      ctx.quadraticCurveTo(x + barW, padT + chartH, x + barW, padT + chartH - r);
      ctx.lineTo(x + barW, y + r);
      ctx.quadraticCurveTo(x + barW, y, x + barW - r, y);
      ctx.lineTo(x + r, y);
      ctx.quadraticCurveTo(x, y, x, y + r);
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();

      // value on top
      ctx.textAlign = 'center';
      ctx.textBaseline = 'bottom';
      ctx.fillStyle = '#0f172a';
      ctx.font = '600 10.5px Inter, Arial, sans-serif';
      ctx.fillText(Math.round(val).toLocaleString('en-KE'), x + barW / 2, y - 4);

      // label
      ctx.textBaseline = 'top';
      ctx.fillStyle = '#64748b';
      ctx.font = '11px Inter, Arial, sans-serif';
      ctx.fillText(labels[idx] || '', x + barW / 2, padT + chartH + 8);
    });
  }

  /* ---------- 5. STK Push polling ---------- */
  function initStkPolling() {
    if (!window.STK_STATUS_URL) return;
    var attempts = 0;
    var MAX_ATTEMPTS = 48;   // ~2 minutes
    var DELAY = 2500;        // ms

    function show(id) {
      ['stkProcessing', 'stkSuccess', 'stkFailed'].forEach(function (s) {
        var el = document.getElementById(s);
        if (!el) return;
        el.classList.toggle('d-none', s !== id);
        el.classList.toggle('d-flex', s === id);
      });
    }

    function poll() {
      attempts += 1;
      fetch(window.STK_STATUS_URL, { headers: { 'Accept': 'application/json' } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var s = String(data.status || '').toLowerCase();
          if (s === 'completed' || s === 'success' || s === 'paid') {
            show('stkSuccess');
          } else if (s === 'failed' || s === 'cancelled' || s === 'declined' || s === 'reversed') {
            show('stkFailed');
          } else if (attempts < MAX_ATTEMPTS) {
            setTimeout(poll, DELAY);
          } else {
            show('stkFailed');
          }
        })
        .catch(function () {
          if (attempts < MAX_ATTEMPTS) setTimeout(poll, DELAY);
          else show('stkFailed');
        });
    }

    setTimeout(poll, 2500);
  }

  /* ---------- 6. Fee calculator (live) ---------- */
  function initFeeCalculators() {
    var inputs = document.querySelectorAll('.fee-amount-input');
    var cards = document.querySelectorAll('[data-fee-calculator]');
    if (!inputs.length || !cards.length) return;

    function setText(id, text) {
      cards.forEach(function (card) {
        var el = card.querySelector('#' + id);
        if (el) el.textContent = text;
      });
    }

    function setHint(text) {
      cards.forEach(function (card) {
        var el = card.querySelector('#feeHint');
        if (el) el.textContent = text;
      });
    }

    function update(amount) {
      if (!amount || amount < 1) {
        setText('feeReceive', 'KES 0');
        setText('feeFee', 'KES 0');
        setText('feeTotal', 'KES 0');
        setHint('Enter an amount above to see the exact breakdown.');
        return;
      }
      fetch('/payments/api/fee?amount=' + encodeURIComponent(amount),
            { headers: { 'Accept': 'application/json' } })
        .then(function (r) {
          if (!r.ok) throw new Error('bad status');
          return r.json();
        })
        .then(function (data) {
          var fee = (data.service_fee != null) ? data.service_fee
                  : (data.fee != null) ? data.fee : 0;
          var total = (data.total_amount_to_pay != null) ? data.total_amount_to_pay
                    : (data.total != null) ? data.total : (amount + fee);
          setText('feeReceive', fmtKes(amount));
          setText('feeFee', fmtKes(fee));
          setText('feeTotal', fmtKes(total));
          setHint('Total to pay via M-PESA: ' + fmtKes(total) +
                  ' (includes service fee of ' + fmtKes(fee) + ').');
        })
        .catch(function () {
          setHint('Could not reach the fee service. Please retry.');
        });
    }

    inputs.forEach(function (input) {
      input.addEventListener('input', debounce(function () {
        update(parseInt(input.value, 10));
      }, 250));
      if (input.value) update(parseInt(input.value, 10));
    });
  }

  /* ---------- 7. Product / list filters ---------- */
  function initFilters() {
    var buttons = document.querySelectorAll('[data-filter]');
    if (!buttons.length) return;
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        var f = btn.getAttribute('data-filter');
        buttons.forEach(function (b) {
          b.classList.toggle('btn-grad', b === btn);
          b.classList.toggle('btn-light', b !== btn);
        });
        document.querySelectorAll('[data-category]').forEach(function (card) {
          var show = (f === 'all') || card.getAttribute('data-category') === f;
          card.classList.toggle('d-none', !show);
        });
      });
    });
  }

  /* ---------- 8. Confirm-on-submit forms ---------- */
  function initConfirmForms() {
    document.querySelectorAll('form[data-confirm]').forEach(function (form) {
      form.addEventListener('submit', function (e) {
        var msg = form.getAttribute('data-confirm') ||
                  'Are you sure you want to continue?';
        if (!window.confirm(msg)) e.preventDefault();
      });
    });
  }

  /* ---------- 9. Password visibility toggle ---------- */
  function initPasswordToggles() {
    document.querySelectorAll('.password-toggle').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var group = btn.closest('.input-group');
        var input = group ? group.querySelector('input[type="password"], input[type="text"]') : null;
        if (!input) return;
        var show = input.type === 'password';
        input.type = show ? 'text' : 'password';
        btn.innerHTML = show ? '<i class="bi bi-eye-slash"></i>' : '<i class="bi bi-eye"></i>';
      });
    });
  }

  /* ---------- Boot ---------- */
  document.addEventListener('DOMContentLoaded', function () {
    initNavbar();
    initFlash();
    initCounters();
    initCharts();
    initStkPolling();
    initFeeCalculators();
    initFilters();
    initConfirmForms();
    initPasswordToggles();
  });
})();