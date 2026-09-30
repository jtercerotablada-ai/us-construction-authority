(function () {
  'use strict';
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---------------------------------------------------------------- reveal on scroll
  var reveals = document.querySelectorAll('.reveal');
  var settle = function (el) {
    // after the entrance animation, drop the delay so hover transitions respond immediately
    setTimeout(function () { el.classList.remove('reveal-d1', 'reveal-d2', 'reveal-d3'); }, 1300);
  };
  if ('IntersectionObserver' in window && !reduceMotion) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('is-visible'); settle(e.target); io.unobserve(e.target); }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
    reveals.forEach(function (el) { io.observe(el); });
  } else {
    reveals.forEach(function (el) { el.classList.add('is-visible'); });
  }
  window.addEventListener('beforeprint', function () { reveals.forEach(function (el) { el.classList.add('is-visible'); }); });

  window.__uscpa = true; // reveal is wired up: the <head> fallback can stand down

  var FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])';

  // Keep keyboard focus inside `root` while it is open.
  function trapFocus(root, e) {
    if (e.key !== 'Tab') return;
    var items = Array.prototype.filter.call(root.querySelectorAll(FOCUSABLE), function (el) {
      return el.getClientRects().length > 0 || el === document.activeElement;
    });
    if (!items.length) return;
    var first = items[0], last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  // ---------------------------------------------------------------- header
  var header = document.querySelector('.header');
  var onScroll = function () { if (header) header.classList.toggle('is-scrolled', window.scrollY > 10); };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  // ---------------------------------------------------------------- mobile menu
  var burger = document.getElementById('hamburger');
  var menu = document.getElementById('mobileMenu');
  if (burger && menu) {
    var menuOpen = false;
    var setMenu = function (open, restoreFocus) {
      menuOpen = open;
      if (open && header) {
        document.documentElement.style.setProperty('--hdr', Math.max(0, header.getBoundingClientRect().bottom) + 'px');
      }
      menu.classList.toggle('is-open', open);
      burger.classList.toggle('is-open', open);
      burger.setAttribute('aria-expanded', open);
      burger.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
      document.body.classList.toggle('menu-open', open);
      document.body.style.overflow = open ? 'hidden' : '';
      if (open) {
        var first = menu.querySelector('a');
        if (first) setTimeout(function () { first.focus(); }, 50);
      } else if (restoreFocus) {
        burger.focus();
      }
    };
    burger.addEventListener('click', function () { setMenu(!menuOpen, true); });
    menu.querySelectorAll('a').forEach(function (a) { a.addEventListener('click', function () { setMenu(false); }); });
    document.addEventListener('keydown', function (e) {
      if (!menuOpen) return;
      if (e.key === 'Escape') { setMenu(false, true); return; }
      if (e.key === 'Tab') {
        // cycle through the menu links and the close (hamburger) button
        var items = [burger].concat(Array.prototype.slice.call(menu.querySelectorAll('a')));
        var i = items.indexOf(document.activeElement);
        e.preventDefault();
        var next = e.shiftKey ? (i <= 0 ? items.length - 1 : i - 1) : (i === items.length - 1 ? 0 : i + 1);
        items[next].focus();
      }
    });
    var desktop = window.matchMedia('(min-width: 1181px)');
    var onDesktop = function () { if (desktop.matches && menuOpen) setMenu(false); };
    if (desktop.addEventListener) desktop.addEventListener('change', onDesktop); else desktop.addListener(onDesktop);
  }

  // ---------------------------------------------------------------- blueprint (home hero)
  var bp = document.querySelector('.blueprint');
  if (bp) {
    var svg = bp.querySelector('svg');
    if (reduceMotion && svg && svg.pauseAnimations) svg.pauseAnimations();
    bp.querySelectorAll('.draw').forEach(function (p) {
      if (p.getTotalLength && !p.classList.contains('bp-wire')) p.style.setProperty('--len', Math.ceil(p.getTotalLength()));
    });
    var tip = bp.querySelector('.bp-tip');
    var spots = bp.querySelectorAll('.hotspot');
    var introTimer = null, userActed = false;
    var show = function (spot) {
      clearTimeout(introTimer); clearTimeout(hideTimer);
      var r = spot.querySelector('.core').getBoundingClientRect();
      var box = bp.getBoundingClientRect();
      tip.innerHTML = '<small>' + spot.dataset.cat + '</small><strong>' + spot.dataset.title + '</strong><span>' + spot.dataset.text + '</span>';
      var rawX = r.left + r.width / 2 - box.left;
      var half = tip.offsetWidth / 2 || 120;
      var x = Math.max(half + 6, Math.min(box.width - half - 6, rawX));
      tip.style.left = x + 'px';
      tip.style.top = (r.top - box.top) + 'px';
      tip.style.setProperty('--arrow', (rawX - x) + 'px');
      tip.classList.add('is-visible');
      spots.forEach(function (s) { s.classList.toggle('is-active', s === spot); });
    };
    var hideTimer = null;
    var hide = function () {
      clearTimeout(hideTimer);
      tip.classList.remove('is-visible');
      spots.forEach(function (s) { s.classList.remove('is-active'); });
    };
    spots.forEach(function (spot) {
      spot.addEventListener('mouseenter', function () { userActed = true; show(spot); });
      spot.addEventListener('focus', function () { userActed = true; show(spot); });
      spot.addEventListener('mouseleave', function () { hideTimer = setTimeout(hide, 180); });
      spot.addEventListener('blur', hide);
    });
    tip.addEventListener('mouseenter', function () { clearTimeout(hideTimer); });
    tip.addEventListener('mouseleave', hide);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') hide(); });
    // one-time hint so visitors discover the points (mouse users, motion allowed)
    if (spots.length && !reduceMotion && window.matchMedia('(hover: hover)').matches) {
      setTimeout(function () {
        if (userActed || bp.querySelector('.hotspot:hover, .hotspot:focus')) return;
        show(spots[0]);
        introTimer = setTimeout(function () { if (!userActed) hide(); }, 2600);
      }, 2400);
    }
  }

  // ---------------------------------------------------------------- tabs (WAI-ARIA tabs pattern)
  document.querySelectorAll('[data-tabs]').forEach(function (list) {
    var tabs = Array.prototype.slice.call(list.querySelectorAll('[role="tab"]'));
    var select = function (tab, focus) {
      tabs.forEach(function (t) {
        var on = t === tab;
        t.classList.toggle('is-active', on);
        t.setAttribute('aria-selected', on);
        t.tabIndex = on ? 0 : -1;
        var panel = document.getElementById(t.getAttribute('aria-controls'));
        if (panel) { panel.classList.toggle('is-active', on); panel.hidden = !on; }
      });
      if (focus) tab.focus();
    };
    tabs.forEach(function (t, i) {
      t.addEventListener('click', function () { select(t); });
      t.addEventListener('keydown', function (e) {
        var n = null;
        if (e.key === 'ArrowRight') n = tabs[(i + 1) % tabs.length];
        else if (e.key === 'ArrowLeft') n = tabs[(i - 1 + tabs.length) % tabs.length];
        else if (e.key === 'Home') n = tabs[0];
        else if (e.key === 'End') n = tabs[tabs.length - 1];
        if (n) { e.preventDefault(); select(n, true); }
      });
    });
  });

  // ---------------------------------------------------------------- visual / infrared comparison
  document.querySelectorAll('.compare').forEach(function (c) {
    var range = c.querySelector('.compare__range');
    var set = function (v) { v = Math.max(0, Math.min(100, v)); c.style.setProperty('--pos', v + '%'); range.value = v; };
    range.addEventListener('input', function () { set(+range.value); });
    set(+range.value);
    // touch-action: pan-y lets vertical swipes scroll the page; horizontal drags move the handle
    var dragging = false, startX = 0, startY = 0, decided = false;
    var fromEvent = function (e) { var r = c.getBoundingClientRect(); return (e.clientX - r.left) / r.width * 100; };
    c.addEventListener('pointerdown', function (e) {
      dragging = true; decided = e.pointerType === 'mouse'; startX = e.clientX; startY = e.clientY;
      if (decided) { set(fromEvent(e)); c.setPointerCapture(e.pointerId); }
    });
    c.addEventListener('pointermove', function (e) {
      if (!dragging) return;
      if (!decided) {
        var dx = Math.abs(e.clientX - startX), dy = Math.abs(e.clientY - startY);
        if (dx < 6 && dy < 6) return;
        if (dy > dx) { dragging = false; return; }
        decided = true; c.setPointerCapture(e.pointerId);
      }
      set(fromEvent(e));
    });
    var end = function () { dragging = false; };
    c.addEventListener('pointerup', end);
    c.addEventListener('pointercancel', end);
  });

  // ---------------------------------------------------------------- numbered pins <-> legend
  // Tooltips are shifted so they stay inside their diagram frame.
  var clampTip = function (pin) {
    var tipEl = pin.querySelector('.pin__tip');
    var clip = pin.closest('.detail__figure') || pin.closest('.dg-frame');
    if (!tipEl || !clip) return;
    tipEl.style.setProperty('--shift', '0px');
    var t = tipEl.getBoundingClientRect(), f = clip.getBoundingClientRect();
    var pad = 6, shift = 0;
    if (t.left < f.left + pad) shift = f.left + pad - t.left;
    else if (t.right > f.right - pad) shift = f.right - pad - t.right;
    tipEl.style.setProperty('--shift', shift + 'px');
    // not enough room above the pin: show the tooltip below it
    if (!pin.dataset.below) pin.dataset.below = pin.classList.contains('pin--b') ? '1' : '0';
    if (pin.dataset.below === '0') pin.classList.toggle('pin--b', t.top < f.top + pad);
  };
  var bindPins = function (frame, list) {
    if (!frame) return;
    var pins = frame.querySelectorAll('.pin');
    var items = list ? list.querySelectorAll('li') : [];
    var setOn = function (n, scrollPin) {
      pins.forEach(function (p) {
        var on = p.dataset.n === n;
        p.classList.toggle('is-on', on);
        if (on) {
          clampTip(p);
          if (scrollPin) {
            var r = p.getBoundingClientRect();
            if (r.top < 80 || r.bottom > window.innerHeight - 90) p.scrollIntoView({ block: 'center', behavior: reduceMotion ? 'auto' : 'smooth' });
          }
        }
      });
      items.forEach(function (li) { li.classList.toggle('is-on', li.dataset.n === n); });
    };
    pins.forEach(function (p) {
      p.addEventListener('pointerenter', function (e) { clampTip(p); if (e.pointerType === 'mouse') setOn(p.dataset.n); });
      p.addEventListener('pointerleave', function (e) { document.body.classList.remove('tips-off'); if (e.pointerType === 'mouse') setOn(null); });
      p.addEventListener('focus', function () { setOn(p.dataset.n); });
      p.addEventListener('click', function (e) { e.stopPropagation(); setOn(p.dataset.n); });
      p.addEventListener('keydown', function (e) { if (e.key === 'Escape' && p.classList.contains('is-on') && !p.closest('#lightbox')) { e.stopPropagation(); setOn(null); } });
    });
    items.forEach(function (li) {
      li.addEventListener('pointerenter', function (e) { if (e.pointerType === 'mouse') setOn(li.dataset.n); });
      li.addEventListener('pointerleave', function (e) { if (e.pointerType === 'mouse') setOn(null); });
      li.addEventListener('click', function () { setOn(li.dataset.n, true); });
    });
  };
  document.querySelectorAll('.detail__figure').forEach(function (fig) {
    bindPins(fig.querySelector('.dg-frame'), fig.parentElement.querySelector('.legend'));
  });

  // ---------------------------------------------------------------- lightbox (diagram viewer)
  var lb = document.getElementById('lightbox');
  if (lb) {
    var stage = lb.querySelector('.lightbox__stage');
    var inner = lb.querySelector('.lightbox__inner');
    var lbTitle = lb.querySelector('.lightbox__title');
    var lbText = lb.querySelector('.lightbox__text');
    var lbList = lb.querySelector('.lightbox__side .legend');
    var closeBtn = lb.querySelector('.lightbox__close');
    var opener = null, clearTimer = null;
    var isOpen = function () { return lb.classList.contains('is-open'); };

    var open = function (trigger) {
      var tpl = trigger.querySelector('template.dg-tpl');
      var frag;
      if (tpl) {
        frag = tpl.content.cloneNode(true);
      } else {
        var f = trigger.querySelector('.dg-frame');
        if (!f) return;
        frag = document.createDocumentFragment();
        frag.appendChild(f.cloneNode(true));
      }
      clearTimeout(clearTimer);
      var legendEl = frag.querySelector('.legend');
      if (legendEl) legendEl.parentNode.removeChild(legendEl);
      stage.innerHTML = '';
      stage.appendChild(frag);
      var img = stage.querySelector('img');
      if (img) img.removeAttribute('loading');
      lbList.innerHTML = legendEl ? legendEl.innerHTML : '';
      inner.classList.toggle('no-legend', !legendEl);
      lbTitle.innerHTML = trigger.dataset.title || 'Diagram';
      lbText.innerHTML = trigger.dataset.text || '';
      bindPins(stage.querySelector('.dg-frame'), lbList);
      opener = document.activeElement;
      lb.classList.add('is-open');
      lb.setAttribute('aria-hidden', 'false');
      lb.scrollTop = 0;
      document.body.style.overflow = 'hidden';
      setTimeout(function () { closeBtn.focus(); }, 30);
    };
    var close = function () {
      if (!isOpen()) return;
      lb.classList.remove('is-open');
      lb.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = '';
      clearTimer = setTimeout(function () { stage.innerHTML = ''; lbList.innerHTML = ''; }, 350);
      if (opener && opener.focus) opener.focus();
    };

    document.querySelectorAll('[data-lightbox]').forEach(function (el) {
      el.addEventListener('click', function (e) {
        if (e.target.closest('.pin')) return;
        open(el);
      });
      if (el.getAttribute('role') === 'button') {
        el.addEventListener('keydown', function (e) {
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(el); }
        });
      }
    });
    document.querySelectorAll('[data-open-lightbox]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var host = btn.closest('[data-lightbox]');
        if (host) open(host);
      });
    });
    lb.addEventListener('click', function (e) {
      if (e.target === lb || e.target === inner || e.target.closest('.lightbox__close')) close();
    });
    document.addEventListener('keydown', function (e) {
      if (!isOpen()) return;
      if (e.key === 'Escape') { close(); return; }
      trapFocus(lb, e);
    });
  }

  // ---------------------------------------------------------------- appointment form
  var form = document.getElementById('appointmentForm');
  if (form) {
    var card = form.closest('.form-card');
    var params = new URLSearchParams(window.location.search);
    var svc = params.get('service');
    if (svc) {
      var details = form.querySelector('#details');
      if (details && !details.value) details.value = 'Service: ' + svc.slice(0, 120) + '\n';
    }
    var div = params.get('division');
    if (div) {
      form.querySelectorAll('input[name="division"]').forEach(function (r) { if (r.value === div) r.checked = true; });
    }
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (!form.checkValidity()) { form.reportValidity(); return; }
      var d = new FormData(form);
      var body = [
        'Name: ' + d.get('firstName'),
        'Email: ' + d.get('email'),
        'Phone: ' + d.get('phone'),
        'Best time to call: ' + d.get('bestTime'),
        'Division: ' + (d.get('division') || '-'),
        '',
        'Project details:',
        d.get('details') || '-'
      ].join('\n');
      window.location.href = 'mailto:cia4solutions@gmail.com'
        + '?subject=' + encodeURIComponent('Free Evaluation Request - ' + d.get('firstName'))
        + '&body=' + encodeURIComponent(body);
      card.classList.add('is-sent');
      card.scrollIntoView({ block: 'start', behavior: reduceMotion ? 'auto' : 'smooth' });
      var h = card.querySelector('.form-success h2');
      if (h) setTimeout(function () { h.focus({ preventScroll: true }); }, 50);
    });
    var edit = card.querySelector('[data-edit-request]');
    if (edit) edit.addEventListener('click', function () {
      card.classList.remove('is-sent');
      var first = form.querySelector('#firstName');
      if (first) first.focus();
    });
  }

  // Escape dismisses any hover tooltip on the page (WCAG 1.4.13)
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    document.body.classList.add('tips-off');
    document.querySelectorAll('.pin.is-on').forEach(function (p) { p.classList.remove('is-on'); });
    document.querySelectorAll('.legend li.is-on').forEach(function (li) { li.classList.remove('is-on'); });
  });

  var y = document.getElementById('year');
  if (y) y.textContent = new Date().getFullYear();
})();
