/* ── Report / Results Rendering Logic ── */

document.addEventListener('DOMContentLoaded', () => {
  const raw = sessionStorage.getItem('screening_result');
  if (!raw) {
    // Show the no-result placeholder instead of instantly redirecting
    const noResult = document.getElementById('no-result');
    const reportContent = document.getElementById('report-content');
    if (noResult) noResult.style.display = 'block';
    if (reportContent) reportContent.style.display = 'none';
    showToast('No screening data found. Please run a new analysis.', 'warning');
    return;
  }

  // Reveal report and hide placeholder
  const noResult = document.getElementById('no-result');
  const reportContent = document.getElementById('report-content');
  if (noResult) noResult.style.display = 'none';
  if (reportContent) reportContent.style.display = 'block';

  const result = JSON.parse(raw);
  renderReport(result);
});

/* ─────────────────────────────── Main Renderer ── */
function renderReport(r) {
  renderVerdictBanner(r);
  renderGauge(r.risk_score);
  renderMetaInfo(r);
  renderImages(r);
  renderAnomalies(r.anomalies || []);
  renderExifFlags(r.exif_flags || []);
  renderSummary(r.summary);
  renderTamperedRegions(r.tampered_regions || []);

  // Fade in elements
  document.querySelectorAll('.fade-in').forEach((el, i) => {
    el.style.animationDelay = `${i * 0.07}s`;
  });
}

/* ─────────────────────────────── Verdict Banner ── */
function renderVerdictBanner(r) {
  const banner = document.getElementById('verdict-banner');
  if (!banner) return;
  const emojis = { GENUINE: '✅', SUSPICIOUS: '⚠️', FAKE: '🚫' };
  const titles = { GENUINE: 'Document Appears Genuine', SUSPICIOUS: 'Suspicious — Manual Review Required', FAKE: 'Forgery Detected — Document is Fake' };

  banner.className = `verdict-banner ${r.verdict}`;
  banner.innerHTML = `
    <div class="verdict-emoji">${emojis[r.verdict] || '🔍'}</div>
    <div>
      <div class="verdict-title ${r.verdict}">${titles[r.verdict] || r.verdict}</div>
      <div class="verdict-summary">Confidence: <strong>${r.confidence}%</strong> · Scan ID: <strong>#${r.scan_id}</strong></div>
    </div>
    <div style="margin-left: auto;">
      <span class="badge badge-${verdictClass(r.verdict)}">
        <span class="badge-dot"></span>
        ${r.verdict}
      </span>
    </div>
  `;
}

/* ─────────────────────────────── Animated Gauge ── */
function renderGauge(score) {
  const svg = document.getElementById('gauge-svg');
  if (!svg) return;

  const C = 490; // matches stroke-dasharray in SVG (2π×78 ≈ 490)
  const fill = document.getElementById('gauge-fill');
  const scoreText = document.getElementById('gauge-score-text');
  const verdictText = document.getElementById('gauge-verdict-text');

  const color = riskColor(score);
  fill.setAttribute('stroke', color);

  scoreText.textContent = score;
  scoreText.setAttribute('fill', color);

  const verdict = score <= 20 ? 'LOW RISK' : score <= 60 ? 'MEDIUM' : 'HIGH RISK';
  verdictText.textContent = verdict;

  // Animate: transition is on the element, just set the target offset
  setTimeout(() => {
    const offset = C - (score / 100) * C;
    fill.setAttribute('stroke-dashoffset', offset);
  }, 200);
}

/* ─────────────────────────────── Meta Info ── */
function renderMetaInfo(r) {
  const setEl = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };
  setEl('meta-scan-id',   `#${r.scan_id}`);
  setEl('meta-doc-type',  docLabel(r.document_type));
  setEl('meta-timestamp', formatDateTime(r.timestamp));
  setEl('meta-filename',  r.file_name || '—');
  setEl('meta-filesize',  r.file_size_kb ? `${r.file_size_kb} KB` : '—');
  setEl('meta-anomalies', (r.anomalies || []).length);
  setEl('meta-regions',   (r.tampered_regions || []).length);
  setEl('meta-confidence', `${r.confidence}%`);

  // Risk bar
  const bar = document.getElementById('risk-bar-fill');
  const barNum = document.getElementById('risk-bar-num');
  if (bar) {
    bar.style.width = '0%';
    bar.style.background = riskColor(r.risk_score);
    setTimeout(() => { bar.style.width = `${r.risk_score}%`; }, 300);
  }
  if (barNum) {
    barNum.textContent = `${r.risk_score}/100`;
    barNum.style.color = riskColor(r.risk_score);
  }
}

/* ─────────────────────────────── Images ── */
function renderImages(r) {
  const origImg = document.getElementById('original-img');
  const annotImg = document.getElementById('annotated-img');
  const noAnnot = document.getElementById('no-annotation-msg');

  if (origImg && r.original_image_b64) {
    origImg.src = `data:image/jpeg;base64,${r.original_image_b64}`;
  }

  if (annotImg && r.annotated_image_b64) {
    annotImg.src = `data:image/jpeg;base64,${r.annotated_image_b64}`;
    if (noAnnot) noAnnot.style.display = 'none';
  } else if (noAnnot) {
    noAnnot.style.display = 'flex';
    if (annotImg) annotImg.style.display = 'none';
  }
}

/* ─────────────────────────────── Anomalies ── */
function renderAnomalies(anomalies) {
  const container = document.getElementById('anomaly-list');
  const emptyMsg  = document.getElementById('anomaly-empty');
  if (!container) return;

  if (anomalies.length === 0) {
    container.innerHTML = '';
    if (emptyMsg) emptyMsg.style.display = 'flex';
    return;
  }

  if (emptyMsg) emptyMsg.style.display = 'none';

  const sevOrder = { HIGH: 0, MEDIUM: 1, LOW: 2 };
  const sorted = [...anomalies].sort((a, b) =>
    (sevOrder[a.severity] ?? 3) - (sevOrder[b.severity] ?? 3)
  );

  container.innerHTML = sorted.map((a, i) => `
    <div class="anomaly-item fade-in" style="animation-delay:${i * 0.08}s">
      <div class="anomaly-severity-dot sev-${a.severity?.toLowerCase()}"></div>
      <div class="anomaly-content">
        <div class="anomaly-type">${a.type || 'Unknown'}</div>
        <div class="anomaly-desc">${a.description || '—'}</div>
      </div>
      <span class="anomaly-sev-badge sev-badge-${a.severity?.toLowerCase()}">${a.severity}</span>
    </div>
  `).join('');
}

/* ─────────────────────────────── EXIF Flags ── */
function renderExifFlags(flags) {
  const container = document.getElementById('exif-flags-list');
  const section   = document.getElementById('exif-section');
  if (!container) return;

  if (flags.length === 0) {
    if (section) section.style.display = 'none';
    return;
  }

  if (section) section.style.display = 'block';
  container.innerHTML = flags.map(f => `
    <div class="exif-flag">
      <span>⚠️</span>
      <span>${f}</span>
    </div>
  `).join('');
}

/* ─────────────────────────────── Summary ── */
function renderSummary(summary) {
  const el = document.getElementById('ai-summary');
  if (el) el.textContent = summary || 'No summary available.';
}

/* ─────────────────────────────── Tampered Regions Table ── */
function renderTamperedRegions(regions) {
  const container = document.getElementById('regions-list');
  const section   = document.getElementById('regions-section');
  if (!container) return;

  if (regions.length === 0) {
    if (section) section.style.display = 'none';
    return;
  }

  if (section) section.style.display = 'block';
  container.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Region Label</th>
          <th>Position (x, y)</th>
          <th>Size (w × h)</th>
        </tr>
      </thead>
      <tbody>
        ${regions.map((r, i) => `
          <tr>
            <td class="td-mono">${i + 1}</td>
            <td>${r.label || '—'}</td>
            <td class="td-mono">${Math.round(r.x)}%, ${Math.round(r.y)}%</td>
            <td class="td-mono">${Math.round(r.w)}% × ${Math.round(r.h)}%</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

/* ─────────────────────────────── Export / Actions ── */
window.downloadReport = function () {
  const raw = sessionStorage.getItem('screening_result');
  if (!raw) return;
  const result = JSON.parse(raw);
  const exportData = { ...result };
  delete exportData.annotated_image_b64;
  delete exportData.original_image_b64;

  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url;
  a.download = `screening_report_${result.scan_id}_${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
  showToast('Report downloaded successfully!', 'success');
};

window.newScan = function () {
  sessionStorage.removeItem('screening_result');
  window.location.href = '/screen';
};
