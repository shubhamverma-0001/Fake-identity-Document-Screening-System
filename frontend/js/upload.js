/* ── Document Upload & Screening Logic ── */

let selectedFile = null;
let selectedDocType = 'aadhaar';
let liveSelfieBlob = null;
let webcamStream = null;

/* ── DOM refs ── */
const dropZone           = document.getElementById('drop-zone');
const fileInput          = document.getElementById('file-input');
const previewWrap        = document.getElementById('upload-preview');
const previewImg         = document.getElementById('preview-img');
const previewName        = document.getElementById('preview-name');
const previewSize        = document.getElementById('preview-size');
const analyzeBtn         = document.getElementById('analyze-btn');
const loadingOvl         = document.getElementById('loading-overlay');
const docTypeBtns        = document.querySelectorAll('.doc-type-btn');

/* Webcam DOM refs */
const cameraContainer    = document.getElementById('camera-container');
const webcamVideo        = document.getElementById('webcam-video');
const webcamCanvas       = document.getElementById('webcam-canvas');
const selfiePreviewWrap  = document.getElementById('selfie-preview-container');
const selfiePreviewImg   = document.getElementById('selfie-preview-img');
const startCameraBtn     = document.getElementById('start-camera-btn');
const captureSelfieBtn   = document.getElementById('capture-selfie-btn');
const retakeSelfieBtn    = document.getElementById('retake-selfie-btn');
const selfieFileInput    = document.getElementById('selfie-file-input');

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

/* ─────────────────────────────── Webcam & Selfie Logic ── */

async function startCamera() {
  try {
    webcamStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' }
    });
    webcamVideo.srcObject = webcamStream;
    cameraContainer.style.display = 'block';
    selfiePreviewWrap.style.display = 'none';
    startCameraBtn.style.display = 'none';
    captureSelfieBtn.style.display = 'inline-flex';
    retakeSelfieBtn.style.display = 'none';
    showToast('Camera started. Align your face in the oval frame.', 'info');
  } catch (err) {
    console.error('Camera access error:', err);
    showToast('Could not access camera. Please allow camera permissions or upload a selfie file.', 'error');
  }
}

function stopCamera() {
  if (webcamStream) {
    webcamStream.getTracks().forEach(track => track.stop());
    webcamStream = null;
  }
  cameraContainer.style.display = 'none';
}

captureSelfieBtn?.addEventListener('click', () => {
  if (!webcamVideo.videoWidth) return;

  webcamCanvas.width = webcamVideo.videoWidth;
  webcamCanvas.height = webcamVideo.videoHeight;
  const ctx = webcamCanvas.getContext('2d');
  
  // Mirror canvas horizontally to match mirrored video feed
  ctx.translate(webcamCanvas.width, 0);
  ctx.scale(-1, 1);
  ctx.drawImage(webcamVideo, 0, 0, webcamCanvas.width, webcamCanvas.height);

  webcamCanvas.toBlob((blob) => {
    if (!blob) return;
    liveSelfieBlob = blob;
    const url = URL.createObjectURL(blob);
    selfiePreviewImg.src = url;

    stopCamera();
    selfiePreviewWrap.style.display = 'block';
    captureSelfieBtn.style.display = 'none';
    retakeSelfieBtn.style.display = 'inline-flex';
    startCameraBtn.style.display = 'none';
    showToast('Live selfie captured! Ready for verification.', 'success');
  }, 'image/jpeg', 0.92);
});

startCameraBtn?.addEventListener('click', () => startCamera());

retakeSelfieBtn?.addEventListener('click', () => {
  liveSelfieBlob = null;
  selfiePreviewWrap.style.display = 'none';
  startCamera();
});

selfieFileInput?.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file || !file.type.startsWith('image/')) {
    showToast('Please select a valid image file for selfie.', 'error');
    return;
  }
  liveSelfieBlob = file;
  const url = URL.createObjectURL(file);
  selfiePreviewImg.src = url;

  stopCamera();
  selfiePreviewWrap.style.display = 'block';
  startCameraBtn.style.display = 'none';
  captureSelfieBtn.style.display = 'none';
  retakeSelfieBtn.style.display = 'inline-flex';
  showToast('Selfie image loaded.', 'success');
});

/* ─────────────────────────────── Loading Steps Animation ── */

const LOADING_STEPS = [
  { id: 'step-upload',    label: 'Uploading document & live selfie securely…' },
  { id: 'step-exif',     label: 'Extracting EXIF metadata…' },
  { id: 'step-preproc',  label: 'Preprocessing images & running face detection…' },
  { id: 'step-ai',       label: 'Running Gemini Vision AI forensic & face verification…' },
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

  // Stop camera stream if running
  stopCamera();

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

    if (liveSelfieBlob) {
      formData.append('live_file', liveSelfieBlob, 'selfie.jpg');
    }

    const response = await fetch(`${API_BASE}/api/screen`, {
      method: 'POST',
      body: formData,
    });

    clearInterval(stepInterval);

    if (!response.ok) {
      let errorMsg = `Server error (${response.status})`;
      try {
        const errJson = await response.json();
        if (errJson && errJson.detail) {
          errorMsg = typeof errJson.detail === 'string' ? errJson.detail : JSON.stringify(errJson.detail);
        }
      } catch (_) {
        try {
          const rawText = await response.text();
          if (rawText) errorMsg += `: ${rawText.substring(0, 120)}`;
        } catch (te) {}
      }
      throw new Error(errorMsg);
    }

    let result;
    try {
      result = await response.json();
    } catch (pe) {
      throw new Error('Server returned invalid response format.');
    }

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
