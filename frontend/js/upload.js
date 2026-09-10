/* ── Document Upload & Screening Logic ── */

let selectedFile = null;
let selectedDocType = 'aadhaar';

/* ── DOM refs ── */
const dropZone     = document.getElementById('drop-zone');
const fileInput    = document.getElementById('file-input');
const previewWrap  = document.getElementById('upload-preview');
const previewImg   = document.getElementById('preview-img');
const previewName  = document.getElementById('preview-name');
const previewSize  = document.getElementById('preview-size');
const analyzeBtn   = document.getElementById('analyze-btn');
const loadingOvl   = document.getElementById('loading-overlay');
const docTypeBtns  = document.querySelectorAll('.doc-type-btn');

/* ─────────────────────────────── File Selection ── */

function handleFile(file) {
  if (!file || !file.type.startsWith('image/')) {
    showToast('Please select a valid image file (JPG, PNG, WebP)', 'error');
    return;
  }
  const maxMB = 10;
  if (file.size > maxMB * 1024 * 1024) {
    showToast(`File too large. Maximum is ${maxMB} MB.`, 'error');
    return;
  }

  selectedFile = file;
  const url = URL.createObjectURL(file);
  previewImg.src = url;
  previewName.textContent = file.name;
  previewSize.textContent = (file.size / 1024).toFixed(1) + ' KB';
  previewWrap.style.display = 'block';
  analyzeBtn.disabled = false;
  showToast('Document loaded. Select type and click Analyze.', 'success');
}

/* Drop zone events */
dropZone.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', (e) => {
  if (e.target.files[0]) handleFile(e.target.files[0]);
});

dropZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
});

/* ─────────────────────────────── Doc Type Selection ── */

docTypeBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    docTypeBtns.forEach(b => b.classList.remove('selected'));
    btn.classList.add('selected');
    selectedDocType = btn.dataset.type;
  });
});

/* Set aadhaar as default selected */
document.querySelector('[data-type="aadhaar"]')?.classList.add('selected');

/* ─────────────────────────────── Loading Steps Animation ── */

const LOADING_STEPS = [
  { id: 'step-upload',    label: 'Uploading document securely…' },
  { id: 'step-exif',     label: 'Extracting EXIF metadata…' },
  { id: 'step-preproc',  label: 'Preprocessing image…' },
  { id: 'step-ai',       label: 'Running Gemini Vision AI analysis…' },
  { id: 'step-annotate', label: 'Generating annotated report…' },
];

function animateLoadingSteps() {
  let current = 0;
  const interval = setInterval(() => {
    if (current > 0) {
      const prev = document.getElementById(LOADING_STEPS[current - 1].id);
      if (prev) {
        prev.classList.remove('active');
        prev.classList.add('done');
        prev.querySelector('.loading-step-icon').textContent = '✓';
      }
    }
    if (current < LOADING_STEPS.length) {
      const cur = document.getElementById(LOADING_STEPS[current].id);
      if (cur) cur.classList.add('active');
      current++;
    } else {
      clearInterval(interval);
    }
  }, 900);
  return interval;
}

/* ─────────────────────────────── Analyze Button ── */

analyzeBtn.addEventListener('click', async () => {
  if (!selectedFile) {
    showToast('Please select a document image first.', 'warning');
    return;
  }

  // Show loading overlay
  loadingOvl.classList.add('visible');
  analyzeBtn.disabled = true;

  // Reset loading steps
  LOADING_STEPS.forEach(s => {
    const el = document.getElementById(s.id);
    if (el) {
      el.classList.remove('active', 'done');
      el.querySelector('.loading-step-icon').textContent = '';
    }
  });
  const stepInterval = animateLoadingSteps();

  try {
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('document_type', selectedDocType);

    const response = await fetch(`${API_BASE}/api/screen`, {
      method: 'POST',
      body: formData,
    });

    clearInterval(stepInterval);

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || `Server error: ${response.status}`);
    }

    const result = await response.json();

    // Save result to sessionStorage and navigate to report page
    sessionStorage.setItem('screening_result', JSON.stringify(result));
    window.location.href = '/report';

  } catch (err) {
    clearInterval(stepInterval);
    loadingOvl.classList.remove('visible');
    analyzeBtn.disabled = false;
    showToast(err.message || 'Analysis failed. Please try again.', 'error', 5000);
    console.error('Screening error:', err);
  }
});
