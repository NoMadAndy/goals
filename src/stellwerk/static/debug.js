(function () {
  const root = document.getElementById('debugConsole');
  if (!root) return;

  const toggle = document.getElementById('debugToggle');
  const clearBtn = document.getElementById('debugClear');
  const statusEl = document.getElementById('debugStatus');
  const logEl = document.getElementById('debugLog');

  function setOpen(open) {
    root.dataset.open = open ? 'true' : 'false';
  }

  function appendLine(line) {
    logEl.textContent += line + '\n';
    logEl.scrollTop = logEl.scrollHeight;
  }

  function formatEvent(ev) {
    const ts = ev.ts ? new Date(ev.ts * 1000).toLocaleTimeString() : '';
    const lvl = (ev.level || 'info').toUpperCase();
    const msg = ev.message || '';
    let suffix = '';
    if (ev.data) {
      try {
        suffix = ' ' + JSON.stringify(ev.data);
      } catch (_) {
        suffix = ' [data]';
      }
    }
    return `[${ts}] ${lvl} ${msg}${suffix}`.trim();
  }

  toggle?.addEventListener('click', () => {
    setOpen(root.dataset.open !== 'true');
  });

  clearBtn?.addEventListener('click', () => {
    logEl.textContent = '';
  });

  // Load snapshot
  fetch('/debug/snapshot')
    .then((r) => r.json())
    .then((payload) => {
      if (!payload.enabled) {
        statusEl.textContent = 'deaktiviert';
        return;
      }
      statusEl.textContent = 'verbunden';
      (payload.events || []).forEach((ev) => appendLine(formatEvent(ev)));
    })
    .catch(() => {
      statusEl.textContent = 'Snapshot fehlgeschlagen';
    });

  // Live stream
  try {
    const es = new EventSource('/debug/stream');
    es.onopen = () => {
      statusEl.textContent = 'verbunden';
    };
    es.onerror = () => {
      statusEl.textContent = 'unterbrochen';
    };
    es.onmessage = (e) => {
      try {
        const ev = JSON.parse(e.data);
        appendLine(formatEvent(ev));
      } catch (_) {
        appendLine(String(e.data));
      }
    };
  } catch (_) {
    statusEl.textContent = 'SSE nicht verfügbar';
  }
})();
