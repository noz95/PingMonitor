// ── Shared utilities ──────────────────────────────────────────────────────────

function esc(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function statusBadge(status) {
  const map = { up: 'success', down: 'danger', unknown: 'secondary' };
  const cls = map[status] || 'secondary';
  const dot = `<span class="status-dot dot-${status}"></span>`;
  return `<span class="badge badge-status-${status} bg-${cls}">${dot}${status.toUpperCase()}</span>`;
}

async function api(url, method = 'GET', body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body !== null) opts.body = JSON.stringify(body);
  try {
    const res = await fetch(url, opts);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      toast(err.error || `Erreur ${res.status}`, 'danger');
      throw new Error(err.error || res.status);
    }
    return res.json();
  } catch (e) {
    if (!(e instanceof Error && e.message.match(/^\d+$/))) {
      console.error(url, e);
    }
    throw e;
  }
}

function toast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const id = 'toast-' + Date.now();
  const icons = { success: 'bi-check-circle-fill', danger: 'bi-exclamation-circle-fill', info: 'bi-info-circle-fill' };
  const icon = icons[type] || icons.info;
  container.insertAdjacentHTML('beforeend', `
    <div id="${id}" class="toast align-items-center text-bg-${type} border-0 show" role="alert">
      <div class="d-flex">
        <div class="toast-body"><i class="bi ${icon} me-2"></i>${esc(message)}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    </div>`);
  setTimeout(() => document.getElementById(id)?.remove(), 4000);
}
