/* ── Document Upload & Screening Logic ── */

let selectedFile = null;
let selectedDocType = 'aadhaar';
let liveSelfieBlob = null;
let webcamStream = null;

/* ── DOM Helper ── */
const $ = (id) => document.getElementById(id);

document.addEventListener('DOMContentLoaded', () => {
  initUploadPage();
});

// Also trigger immediately if DOM is already loaded
if (document.readyState === 'interactive' || document.readyState === 'complete') {
  initUploadPage();
}

let isInitialized = false;

function initUploadPage() {
  if (isInitialized) return;
  isInitialized = true;

  const dropZone          = $('drop-zone');
  const fileInput         = $('file-input');
  const previewWrap       = $('upload-preview');
  const previewImg        = $('preview-img');
  const previewName       = $('preview-name');
  const previewSize       = $('preview-size');
  const analyzeBtn        = $('analyze-btn');
  const loadingOvl        = $('loading-overlay');
  const docTypeBtns       = document.querySelectorAll('.doc-type-btn');

  /* Webcam refs */
  const cameraContainer   = $('camera-container');
  const webcamVideo       = $('webcam-video');
  const webcamCanvas      = $('webcam-canvas');
  const selfiePreviewWrap = $('selfie-preview-container');
  const selfiePreviewImg  = $('selfie-preview-img');
  const startCameraBtn    = $('start-camera-btn');
  const captureSelfieBtn  = $('capture-selfie-btn');
  const retakeSelfieBtn   = $('retake-selfie-btn');
  const selfieFileInput   = $('selfie-file-input');

  /* ─────────────────────────────── File Selection ── */

  function handleFile(file) {
    if (!file || !file.type.startsWith('image/')) {
      if (typeof showToast === 'function') showToast('Please select a valid image file (JPG, PNG, WebP)', 'error');
      return;
    }
    const maxMB = 10;
    if (file.size > maxMB * 1024 * 1024) {
      if (typeof showToast === 'function') showToast(`File too large. Maximum is ${maxMB} MB.`, 'error');
      return;
    }

    selectedFile = file;
    const url = URL.createObjectURL(file);
    if (previewImg) previewImg.src = url;
    if (previewName) previewName.textContent = file.name;
    if (previewSize) previewSize.textContent = (file.size / 1024).toFixed(1) + ' KB';
    if (previewWrap) previewWrap.style.display = 'block';
    if (analyzeBtn) analyzeBtn.disabled = false;
    if (typeof showToast === 'function') showToast('Document loaded. Select type and click Analyze.', 'success');
  }

  if (dropZone) {
    dropZone.onclick = () => fileInput && fileInput.click();
    dropZone.ondragover = (e) => {
      e.preventDefault();
      dropZone.classList.add('drag-over');
    };
    dropZone.ondragleave = () => dropZone.classList.remove('drag-over');
    dropZone.ondrop = (e) => {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
      if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
    };
  }

  if (fileInput) {
    fileInput.onchange = (e) => {
      if (e.target.files[0]) handleFile(e.target.files[0]);
    };
  }

  /* ─────────────────────────────── Doc Type Selection ── */

  docTypeBtns.forEach(btn => {
    btn.onclick = () => {
      docTypeBtns.forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      selectedDocType = btn.dataset.type;
    };
  });

  /* Set aadhaar as default selected */
  document.querySelector('[data-type="aadhaar"]')?.classList.add('selected');

  /* ─────────────────────────────── Webcam Controls ── */

  async function startCamera() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      if (typeof showToast === 'function') {
        showToast('Camera not supported or blocked by HTTP connection. Please use "Upload Selfie".', 'error');
      }
      return;
    }

    try {
      webcamStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' }
      });
      if (webcamVideo) webcamVideo.srcObject = webcamStream;
      if (cameraContainer) cameraContainer.style.display = 'block';
      if (selfiePreviewWrap) selfiePreviewWrap.style.display = 'none';
      if (startCameraBtn) startCameraBtn.style.display = 'none';
      if (captureSelfieBtn) captureSelfieBtn.style.display = 'inline-flex';
      if (retakeSelfieBtn) retakeSelfieBtn.style.display = 'none';
      if (typeof showToast === 'function') showToast('Camera started. Align your face in the oval frame.', 'info');
    } catch (err) {
      console.error('Camera access error:', err);
      if (typeof showToast === 'function') {
        showToast('Could not access camera. Please allow camera permissions or upload a selfie image.', 'error');
      }
    }
  }

  function stopCamera() {
    if (webcamStream) {
      webcamStream.getTracks().forEach(track => track.stop());
      webcamStream = null;
    }
    if (cameraContainer) cameraContainer.style.display = 'none';
  }

  if (startCameraBtn) {
    startCameraBtn.onclick = (e) => {
      e.preventDefault();
      startCamera();
    };
  }

  if (captureSelfieBtn) {
    captureSelfieBtn.onclick = (e) => {
      e.preventDefault();
      if (!webcamVideo || !webcamVideo.videoWidth) return;

      webcamCanvas.width = webcamVideo.videoWidth;
      webcamCanvas.height = webcamVideo.videoHeight;
      const ctx = webcamCanvas.getContext('2d');
      
      ctx.translate(webcamCanvas.width, 0);
      ctx.scale(-1, 1);
      ctx.drawImage(webcamVideo, 0, 0, webcamCanvas.width, webcamCanvas.height);

      webcamCanvas.toBlob((blob) => {
        if (!blob) return;
        liveSelfieBlob = blob;
        const url = URL.createObjectURL(blob);
        if (selfiePreviewImg) selfiePreviewImg.src = url;

        stopCamera();
        if (selfiePreviewWrap) selfiePreviewWrap.style.display = 'block';
        if (captureSelfieBtn) captureSelfieBtn.style.display = 'none';
        if (retakeSelfieBtn) retakeSelfieBtn.style.display = 'inline-flex';
        if (startCameraBtn) startCameraBtn.style.display = 'none';
        if (typeof showToast === 'function') showToast('Live selfie captured! Ready for verification.', 'success');
      }, 'image/jpeg', 0.92);
    };
  }

  if (retakeSelfieBtn) {
    retakeSelfieBtn.onclick = (e) => {
      e.preventDefault();
      liveSelfieBlob = null;
      if (selfiePreviewWrap) selfiePreviewWrap.style.display = 'none';
      startCamera();
    };
  }

  if (selfieFileInput) {
    selfieFileInput.onchange = (e) => {
      const file = e.target.files[0];
      if (!file || !file.type.startsWith('image/')) {
        if (typeof showToast === 'function') showToast('Please select a valid image file for selfie.', 'error');
        return;
      }
      liveSelfieBlob = file;
      const url = URL.createObjectURL(file);
      if (selfiePreviewImg) selfiePreviewImg.src = url;

      stopCamera();
      if (selfiePreviewWrap) selfiePreviewWrap.style.display = 'block';
      if (startCameraBtn) startCameraBtn.style.display = 'none';
      if (captureSelfieBtn) captureSelfieBtn.style.display = 'none';
      if (retakeSelfieBtn) retakeSelfieBtn.style.display = 'inline-flex';
      if (typeof showToast === 'function') showToast('Selfie image loaded successfully.', 'success');
    };
  }

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

  if (analyzeBtn) {
    analyzeBtn.onclick = async (e) => {
      e.preventDefault();
      if (!selectedFile) {
        if (typeof showToast === 'function') showToast('Please select a document image first.', 'warning');
        return;
      }

      stopCamera();

      if (loadingOvl) loadingOvl.classList.add('visible');
      analyzeBtn.disabled = true;

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

        const apiBase = typeof API_BASE !== 'undefined' ? API_BASE : '';
        const response = await fetch(`${apiBase}/api/screen`, {
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

        sessionStorage.setItem('screening_result', JSON.stringify(result));
        window.location.href = '/report';

      } catch (err) {
        clearInterval(stepInterval);
        if (loadingOvl) loadingOvl.classList.remove('visible');
        analyzeBtn.disabled = false;
        if (typeof showToast === 'function') {
          showToast(err.message || 'Analysis failed. Please try again.', 'error', 5000);
        }
        console.error('Screening error:', err);
      }
    };
  }
}
