(function () {
  const containerId = 'toastContainer';

  function ensureContainer() {
    let el = document.getElementById(containerId);
    if (el) return el;
    el = document.createElement('div');
    el.id = containerId;
    el.className = 'toast-container';
    el.setAttribute('aria-live', 'polite');
    document.body.appendChild(el);
    return el;
  }

  function toast(level, message, data, opts) {
    const container = ensureContainer();

    const key = opts && opts.key ? String(opts.key) : '';
    let t = key ? container.querySelector(`.toast[data-key="${key}"]`) : null;
    const isNew = !t;
    if (!t) {
      t = document.createElement('div');
      if (key) t.dataset.key = key;
      container.appendChild(t);
    }
    t.className = `toast ${level || 'info'}`.trim();

    t.textContent = '';

    const msg = document.createElement('div');
    msg.className = 'toast-msg';
    msg.textContent = String(message || '');
    t.appendChild(msg);

    if (data && (data.route || data.task || data.status || data.attempt || data.error)) {
      const meta = document.createElement('div');
      meta.className = 'toast-meta';
      const parts = [];
      if (data.route) parts.push(String(data.route));
      if (data.task) parts.push(String(data.task));
      if (data.status) parts.push(`Status ${data.status}`);
      if (typeof data.attempt === 'number') parts.push(`Versuch ${data.attempt}`);
      if (data.error) parts.push(String(data.error));
      meta.textContent = parts.join(' · ');
      t.appendChild(meta);
    }

    const persist = !!(opts && opts.persist);

    // Auto-dismiss (unless persist)
    const timeoutMs = level === 'error' ? 8000 : 4500;
    if (t._toastTimer) window.clearTimeout(t._toastTimer);
    if (!persist) {
      t._toastTimer = window.setTimeout(() => {
        t.classList.add('hide');
        window.setTimeout(() => t.remove(), 250);
      }, timeoutMs);
    }

    if (isNew) {
      // No-op; insertion already happened.
    }
  }

  function parseSseChunks(onEvent) {
    let buffer = '';
    return (chunkText) => {
      buffer += chunkText;
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';
      for (const part of parts) {
        const line = part
          .split('\n')
          .map((l) => l.trim())
          .find((l) => l.startsWith('data:'));
        if (!line) continue;
        const raw = line.slice('data:'.length).trim();
        if (!raw) continue;
        try {
          onEvent(JSON.parse(raw));
        } catch (_) {
          onEvent({ level: 'info', message: raw });
        }
      }
    };
  }

  async function streamPlan(form) {
    const action = form.getAttribute('action') || '';
    if (!action.endsWith('/plan')) return false;

    const url = action + '/stream';

    const button = form.querySelector('button[type="submit"]');
    const contextInput = form.querySelector('input[name="context"]');

    button?.setAttribute('disabled', 'disabled');
    contextInput?.setAttribute('disabled', 'disabled');

    toast('info', 'KI: Planung läuft…', null, { key: 'plan-status', persist: true });

    try {
      const resp = await fetch(url, {
        method: 'POST',
        body: new FormData(form),
        headers: { Accept: 'text/event-stream' },
      });

      if (!resp.ok || !resp.body) {
        toast('error', 'KI: Anfrage fehlgeschlagen');
        button?.removeAttribute('disabled');
        contextInput?.removeAttribute('disabled');
        return true;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();

      const handleChunk = parseSseChunks((ev) => {
        if (ev.redirect) {
          // Small delay so the final status is visible.
          window.setTimeout(() => window.location.assign(ev.redirect), 500);
          return;
        }
        if (ev.message) {
          const lvl = ev.level || 'info';
          const data = ev.data || null;
          const isHeartbeat = ev.message === 'KI: arbeitet noch…';
          const suffix = isHeartbeat && data && typeof data.seconds === 'number' ? ` (${data.seconds}s)` : '';
          const done = ev.message === 'Fertig' || ev.message === 'KI: Plan fertig';
          toast(lvl, `${ev.message}${suffix}`, data, { key: 'plan-status', persist: !done });
        }
      });

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        handleChunk(decoder.decode(value, { stream: true }));
      }

      // If the stream ended without an explicit redirect, make that visible.
      toast('warn', 'KI: Stream beendet (kein Redirect). Seite ggf. neu laden.', null, { key: 'plan-status' });

      button?.removeAttribute('disabled');
      contextInput?.removeAttribute('disabled');
      return true;
    } catch (_) {
      toast('error', 'KI: Stream abgebrochen');
      button?.removeAttribute('disabled');
      contextInput?.removeAttribute('disabled');
      return true;
    }
  }

  document.addEventListener('submit', (e) => {
    const form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    const action = form.getAttribute('action') || '';
    if (!action.endsWith('/plan')) return;

    e.preventDefault();
    void streamPlan(form);
  });

  // Expose for debugging if needed
  window.StellwerkToast = { toast };
})();
