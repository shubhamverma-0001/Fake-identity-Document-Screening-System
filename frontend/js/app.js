/* ── Shared app utilities ── */
const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') ? 'http://localhost:8000' : window.location.origin;

/* ── Active nav highlighting ── */
function setActiveNav() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.remove('active');
    const href = el.getAttribute('href') || el.dataset.href || '';
    if (
      (path === '/' && (href === '/' || href === 'index.html')) ||
      (path === '/screen' && href.includes('screen')) ||
      (path === '/report' && href.includes('report'))
    ) {
      el.classList.add('active');
    }
  });
}

/* ── Toast notifications ── */
function showToast(message, type = 'info', duration = 3500) {
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();

  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || ''}</span><span>${message}</span>`;
  document.body.appendChild(toast);

  requestAnimationFrame(() => {
    requestAnimationFrame(() => toast.classList.add('show'));
  });

  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 400);
  }, duration);
}

/* ── Format date/time ── */
function formatDateTime(isoString) {
  if (!isoString) return '—';
  const d = new Date(isoString);
  return d.toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: true
  });
}

/* ── Get verdict color class ── */
function verdictClass(verdict) {
  const map = { GENUINE: 'genuine', SUSPICIOUS: 'suspicious', FAKE: 'fake' };
  return map[verdict?.toUpperCase()] || 'suspicious';
}

/* ── Risk score color ── */
function riskColor(score) {
  if (score <= 20) return '#10b981';
  if (score <= 60) return '#f59e0b';
  return '#ef4444';
}

/* ── Document type label map ── */
const DOC_LABELS = {
  aadhaar: 'Aadhaar Card',
  passport: 'Passport',
  pan: 'PAN Card',
  driving_license: 'Driving License',
  other: 'Other Document',
};

function docLabel(type) {
  return DOC_LABELS[type] || type || 'Document';
}

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {
  setActiveNav();
});
