/* ============================================================
   Grsai Studio — Frontend Application
   ============================================================ */

(function () {
  'use strict';

  // ---- State ----
  let tasks = [];
  let currentFilter = 'all';
  let pollTimer = null;
  let lightboxImages = [];
  let lightboxIndex = 0;
  const durationTimers = new Map();   // taskId -> intervalId
  const frozenDurations = new Map();  // taskId -> final duration string
  let currentView = 'generate';
  let promptLibrary = [];
  let savedPromptText = '';  // preserve prompt text during tab switch
  let referenceImages = [];
  const selectedReferenceIds = new Set();
  let reusedReferencePaths = [];

  // ---- DOM refs ----
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const form = $('#taskForm');
  const modelSelect = $('#model');
  const sizeSelect = $('#size');
  const sizeGpt = $('#sizeGpt');
  const sizeGptVip = $('#sizeGptVip');
  const ratioGroup = $('#ratioGroup');
  const uploadZone = $('#uploadZone');
  const uploadInput = $('#refImages');
  const uploadPreview = $('#uploadPreview');
  const referenceSelectGrid = $('#referenceSelectGrid');
  const referenceLibraryGrid = $('#referenceLibraryGrid');
  const referenceLibraryInput = $('#referenceLibraryInput');
  const referenceLibraryUploadBtn = $('#referenceLibraryUploadBtn');
  const submitBtn = $('#submitBtn');
  const taskList = $('#taskList');
  const taskEmpty = $('#taskEmpty');
  const healthDot = $('#healthDot');
  const healthText = $('#healthText');
  const lightbox = $('#lightbox');
  const lightboxImg = $('#lightboxImg');
  const lightboxInfo = $('#lightboxInfo');
  const lightboxDownload = $('#lightboxDownload');

  // ---- Helpers ----

  function formatTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso + (iso.endsWith('Z') ? '' : 'Z'));
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
  }

  function elapsed(created) {
    const start = new Date(created + (created.endsWith('Z') ? '' : 'Z')).getTime();
    const diff = Math.max(0, Date.now() - start);
    const s = Math.floor(diff / 1000);
    if (s < 60) return `${s}s`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}m ${s % 60}s`;
    const h = Math.floor(m / 60);
    return `${h}h ${m % 60}m`;
  }

  function startDurationTicker(taskId, createdAt) {
    if (durationTimers.has(taskId) || frozenDurations.has(taskId)) return;
    const update = () => {
      const span = taskList.querySelector(`.task-card[data-id="${taskId}"] .duration-value`);
      if (span) span.textContent = elapsed(createdAt);
    };
    update();
    durationTimers.set(taskId, setInterval(update, 1000));
  }

  function stopDurationTicker(taskId) {
    const id = durationTimers.get(taskId);
    if (id !== undefined) {
      clearInterval(id);
      durationTimers.delete(taskId);
    }
  }

  // ---- Prompt Library (localStorage) ----

  function loadPromptLibrary() {
    try {
      promptLibrary = JSON.parse(localStorage.getItem('grsai_prompt_library') || '[]');
    } catch { promptLibrary = []; }
  }

  function savePromptLibrary() {
    localStorage.setItem('grsai_prompt_library', JSON.stringify(promptLibrary));
  }

  function renderPromptLibrary() {
    const list = $('#promptList');
    if (!list) return;
    if (promptLibrary.length === 0) {
      list.innerHTML = '<div class="prompt-empty">No saved prompts yet.</div>';
      return;
    }
    list.innerHTML = promptLibrary.map((p) => `
      <div class="prompt-card" data-id="${p.id}">
        <div class="prompt-card-text">${esc(p.text)}</div>
        <div class="prompt-card-actions">
          <button class="prompt-btn prompt-btn-copy" data-id="${p.id}">Copy</button>
          <button class="prompt-btn prompt-btn-use" data-id="${p.id}">Use</button>
          <button class="prompt-btn prompt-btn-delete" data-id="${p.id}">Delete</button>
        </div>
      </div>
    `).join('');

    list.querySelectorAll('.prompt-btn-copy').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const item = promptLibrary.find((p) => String(p.id) === btn.dataset.id);
        if (!item) return;
        await navigator.clipboard.writeText(item.text);
        btn.textContent = 'Copied!';
        setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
      });
    });

    list.querySelectorAll('.prompt-btn-use').forEach((btn) => {
      btn.addEventListener('click', () => {
        const item = promptLibrary.find((p) => String(p.id) === btn.dataset.id);
        if (!item) return;
        switchView('generate');
        const promptEl = $('#prompt');
        promptEl.value = item.text;
        promptEl.focus();
      });
    });

    list.querySelectorAll('.prompt-btn-delete').forEach((btn) => {
      btn.addEventListener('click', () => {
        promptLibrary = promptLibrary.filter((p) => String(p.id) !== btn.dataset.id);
        savePromptLibrary();
        renderPromptLibrary();
      });
    });
  }

  function addPrompt(text) {
    if (!text.trim()) return;
    promptLibrary.unshift({ id: Date.now(), text: text.trim(), createdAt: new Date().toISOString() });
    savePromptLibrary();
    renderPromptLibrary();
  }

  // ---- Reference Image Library (server persisted) ----

  async function loadReferenceImages() {
    try {
      const res = await fetch('/api/reference-images');
      if (!res.ok) return;
      referenceImages = await res.json();
      const validIds = new Set(referenceImages.map((img) => String(img.id)));
      for (const id of Array.from(selectedReferenceIds)) {
        if (!validIds.has(id)) selectedReferenceIds.delete(id);
      }
      renderReferenceLibrary();
      renderReferencePicker();
    } catch {
      // Keep the current UI if the library request fails.
    }
  }

  async function uploadReferenceLibraryFiles(fileList) {
    const files = Array.from(fileList || []).filter((f) => f.type.startsWith('image/'));
    if (files.length === 0) return;

    for (const file of files) {
      const fd = new FormData();
      fd.append('image', file);
      const res = await fetch('/api/reference-images', { method: 'POST', body: fd });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `Failed to upload ${file.name}`);
      }
    }

    await loadReferenceImages();
  }

  function toggleReferenceSelection(id) {
    const key = String(id);
    if (selectedReferenceIds.has(key)) selectedReferenceIds.delete(key);
    else selectedReferenceIds.add(key);
    renderReferencePicker();
    renderReferenceLibrary();
  }

  function renderReferencePicker() {
    if (!referenceSelectGrid) return;
    if (referenceImages.length === 0) {
      referenceSelectGrid.innerHTML = '<div class="reference-empty">No saved reference images yet.</div>';
      return;
    }
    referenceSelectGrid.innerHTML = referenceImages.map((img) => {
      const selected = selectedReferenceIds.has(String(img.id));
      return `
        <button class="reference-select-card${selected ? ' selected' : ''}" type="button" data-id="${img.id}" title="${esc(img.original_filename)}">
          <img src="${esc(img.image_url)}" alt="${esc(img.original_filename)}" loading="lazy">
          <span>${selected ? 'Selected' : 'Select'}</span>
        </button>
      `;
    }).join('');

    referenceSelectGrid.querySelectorAll('.reference-select-card').forEach((btn) => {
      btn.addEventListener('click', () => toggleReferenceSelection(btn.dataset.id));
    });
  }

  function renderReferenceLibrary() {
    if (!referenceLibraryGrid) return;
    if (referenceImages.length === 0) {
      referenceLibraryGrid.innerHTML = '<div class="reference-empty">No saved reference images yet.</div>';
      return;
    }
    referenceLibraryGrid.innerHTML = referenceImages.map((img) => {
      const selected = selectedReferenceIds.has(String(img.id));
      return `
        <div class="reference-card${selected ? ' selected' : ''}" data-id="${img.id}">
          <button class="reference-card-image" type="button" data-action="toggle" title="Use for next generation">
            <img src="${esc(img.image_url)}" alt="${esc(img.original_filename)}" loading="lazy">
          </button>
          <div class="reference-card-meta">
            <span>${esc(img.original_filename)}</span>
            <button type="button" class="reference-delete" data-action="delete">Delete</button>
          </div>
        </div>
      `;
    }).join('');

    referenceLibraryGrid.querySelectorAll('.reference-card').forEach((card) => {
      const id = card.dataset.id;
      card.querySelector('[data-action="toggle"]').addEventListener('click', () => {
        toggleReferenceSelection(id);
      });
      card.querySelector('[data-action="delete"]').addEventListener('click', async () => {
        if (!confirm('Delete this reference image?')) return;
        const res = await fetch(`/api/reference-images/${id}`, { method: 'DELETE' });
        if (res.ok || res.status === 204) {
          selectedReferenceIds.delete(String(id));
          await loadReferenceImages();
        }
      });
    });
  }

  // ---- Form State Persistence (localStorage) ----

  function saveFormState() {
    const activeSize = getActiveSizeSelect();
    const state = {
      model: modelSelect.value,
      size: activeSize ? activeSize.value : '',
      quality: $('#quality').value,
      count: $('#count').value,
      parallel: $('#parallel').checked,
    };
    localStorage.setItem('grsai_form_state', JSON.stringify(state));
  }

  function restoreFormState() {
    let state;
    try {
      state = JSON.parse(localStorage.getItem('grsai_form_state'));
    } catch { state = null; }
    if (!state) {
      // First visit defaults
      $('#quality').value = 'high';
      return;
    }
    if (state.model) modelSelect.value = state.model;
    updateSizeControl();
    const activeSize = getActiveSizeSelect();
    if (activeSize && state.size !== undefined) activeSize.value = state.size;
    if (state.quality) $('#quality').value = state.quality;
    if (state.count) $('#count').value = state.count;
    if (state.parallel !== undefined) $('#parallel').checked = state.parallel;
  }

  function getActiveSizeSelect() {
    const model = modelSelect.value;
    if (model === 'gpt-image-2') return sizeGpt;
    if (model === 'gpt-image-2-vip') return sizeGptVip;
    return sizeSelect;
  }

  // ---- View Switching (Generate / Prompt Library) ----

  function switchView(view) {
    currentView = view;
    const genView = $('#viewGenerate');
    const libView = $('#viewPrompts');
    const tabGen = $('#tabGenerate');
    const tabLib = $('#tabPrompts');
    if (view === 'generate') {
      genView.style.display = 'flex';
      libView.style.display = 'none';
      tabGen.classList.add('active');
      tabLib.classList.remove('active');
      // Restore prompt text
      const promptEl = $('#prompt');
      if (savedPromptText) promptEl.value = savedPromptText;
    } else {
      // Save prompt text before switching away
      savedPromptText = $('#prompt').value;
      genView.style.display = 'none';
      libView.style.display = 'flex';
      tabGen.classList.remove('active');
      tabLib.classList.add('active');
      renderPromptLibrary();
      renderReferenceLibrary();
    }
  }

  function truncate(str, len = 100) {
    return str && str.length > len ? str.slice(0, len) + '...' : str || '';
  }

  function imageUrl(imagePath) {
    if (!imagePath) return '';
    const parts = imagePath.replace(/\\/g, '/').split('/');
    const outIdx = parts.indexOf('output');
    if (outIdx !== -1) return '/' + parts.slice(outIdx).join('/');
    return '';
  }

  function filenameFromPath(path) {
    if (!path) return 'reference image';
    return path.replace(/\\/g, '/').split('/').pop() || 'reference image';
  }

  function isLibraryReferencePath(path) {
    return /[\\/]data[\\/]reference_images[\\/]/.test(path || '');
  }

  // ---- Health Check ----

  async function checkHealth() {
    try {
      const res = await fetch('/api/health');
      if (res.ok) {
        healthDot.classList.add('ok');
        healthText.textContent = 'Connected';
      } else {
        healthDot.classList.remove('ok');
        healthText.textContent = 'Error';
      }
    } catch {
      healthDot.classList.remove('ok');
      healthText.textContent = 'Offline';
    }
  }

  // ---- Model / Size toggle ----

  function updateSizeControl() {
    const model = modelSelect.value;
    const isGpt = model.startsWith('gpt-image');
    // Hide ratio for gpt-image models (they use pixel dimensions)
    ratioGroup.style.display = isGpt ? 'none' : 'flex';
    if (model === 'gpt-image-2') {
      sizeSelect.style.display = 'none';
      sizeGpt.style.display = 'block';
      sizeGptVip.style.display = 'none';
    } else if (model === 'gpt-image-2-vip') {
      sizeSelect.style.display = 'none';
      sizeGpt.style.display = 'none';
      sizeGptVip.style.display = 'block';
    } else {
      sizeSelect.style.display = 'block';
      sizeGpt.style.display = 'none';
      sizeGptVip.style.display = 'none';
    }
  }

  modelSelect.addEventListener('change', () => { updateSizeControl(); saveFormState(); });
  // Save form state on any relevant field change
  [sizeSelect, sizeGpt, sizeGptVip, $('#quality')].forEach((el) => {
    el.addEventListener('change', saveFormState);
  });
  $('#count').addEventListener('input', saveFormState);
  $('#parallel').addEventListener('change', saveFormState);

  // ---- File Upload ----

  let selectedFiles = [];

  uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('drag-over');
  });

  uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('drag-over');
  });

  uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('drag-over');
    addFiles(e.dataTransfer.files);
  });

  uploadInput.addEventListener('change', () => {
    addFiles(uploadInput.files);
    uploadInput.value = '';
  });

  if (referenceLibraryInput) {
    referenceLibraryInput.addEventListener('change', async () => {
      try {
        if (referenceLibraryUploadBtn) {
          referenceLibraryUploadBtn.classList.add('is-uploading');
          referenceLibraryUploadBtn.firstChild.textContent = 'Uploading';
        }
        await uploadReferenceLibraryFiles(referenceLibraryInput.files);
      } catch (err) {
        alert('Error: ' + err.message);
      } finally {
        if (referenceLibraryUploadBtn) {
          referenceLibraryUploadBtn.classList.remove('is-uploading');
          referenceLibraryUploadBtn.firstChild.textContent = 'Upload';
        }
        referenceLibraryInput.value = '';
      }
    });
  }

  $('#refreshReferenceBtn').addEventListener('click', loadReferenceImages);

  function addFiles(fileList) {
    for (const f of fileList) {
      if (f.type.startsWith('image/')) {
        selectedFiles.push(f);
      }
    }
    renderPreviews();
  }

  function removeFile(index) {
    selectedFiles.splice(index, 1);
    renderPreviews();
  }

  function removeReusedReferencePath(index) {
    reusedReferencePaths.splice(index, 1);
    renderPreviews();
  }

  function renderPreviews() {
    uploadPreview.innerHTML = '';
    reusedReferencePaths.forEach((path, i) => {
      const div = document.createElement('div');
      div.className = 'upload-thumb upload-thumb-reused';
      div.title = path;
      const label = document.createElement('span');
      label.textContent = filenameFromPath(path);
      const btn = document.createElement('button');
      btn.className = 'upload-thumb-remove';
      btn.textContent = '×';
      btn.onclick = (e) => { e.preventDefault(); removeReusedReferencePath(i); };
      div.appendChild(label);
      div.appendChild(btn);
      uploadPreview.appendChild(div);
    });
    selectedFiles.forEach((file, i) => {
      const div = document.createElement('div');
      div.className = 'upload-thumb';
      const img = document.createElement('img');
      img.src = URL.createObjectURL(file);
      img.onload = () => URL.revokeObjectURL(img.src);
      const btn = document.createElement('button');
      btn.className = 'upload-thumb-remove';
      btn.textContent = '×';
      btn.onclick = (e) => { e.preventDefault(); removeFile(i); };
      div.appendChild(img);
      div.appendChild(btn);
      uploadPreview.appendChild(div);
    });
  }

  function clipboardFiles(event) {
    const items = Array.from(event.clipboardData?.items || []);
    return items
      .filter((item) => item.kind === 'file' && item.type.startsWith('image/'))
      .map((item, index) => {
        const file = item.getAsFile();
        if (!file) return null;
        if (file.name && file.name !== 'image.png') return file;
        const ext = (file.type.split('/')[1] || 'png').replace('jpeg', 'jpg');
        return new File([file], `clipboard-${Date.now()}-${index}.${ext}`, { type: file.type });
      })
      .filter(Boolean);
  }

  document.addEventListener('paste', (e) => {
    const files = clipboardFiles(e);
    if (files.length === 0) return;
    e.preventDefault();
    if (currentView !== 'generate') switchView('generate');
    selectedFiles.push(...files);
    renderPreviews();
    uploadZone.classList.add('paste-added');
    setTimeout(() => uploadZone.classList.remove('paste-added'), 900);
  });

  // ---- Form Submit ----

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Submitting...';

    try {
      const model = modelSelect.value;
      let size = null;
      if (model === 'gpt-image-2') {
        size = sizeGpt.value || null;
      } else if (model === 'gpt-image-2-vip') {
        size = sizeGptVip.value || null;
      } else {
        size = sizeSelect.value || null;
      }
      const params = {
        prompt: $('#prompt').value.trim(),
        model: model,
        ratio: $('#ratio').value || null,
        size: size,
        quality: $('#quality').value || null,
        count: parseInt($('#count').value, 10) || 1,
        parallel: $('#parallel').checked,
      };

      let res;
      if (selectedFiles.length > 0) {
        // Multipart upload
        const fd = new FormData();
        fd.append('prompt', params.prompt);
        fd.append('model', params.model);
        if (params.ratio) fd.append('ratio', params.ratio);
        if (params.size) fd.append('size', params.size);
        if (params.quality) fd.append('quality', params.quality);
        fd.append('count', params.count);
        fd.append('parallel', params.parallel);
        for (const id of selectedReferenceIds) {
          fd.append('reference_image_ids', id);
        }
        for (const path of reusedReferencePaths) {
          fd.append('ref_image_paths', path);
        }
        for (const f of selectedFiles) {
          fd.append('ref_images', f);
        }
        res = await fetch('/api/tasks/upload', { method: 'POST', body: fd });
      } else {
        // JSON
        if (selectedReferenceIds.size > 0) {
          params.reference_image_ids = Array.from(selectedReferenceIds).map((id) => parseInt(id, 10));
        }
        if (reusedReferencePaths.length > 0) {
          params.ref_image_paths = [...reusedReferencePaths];
        }
        res = await fetch('/api/tasks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(params),
        });
      }

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'Request failed');
      }

      const data = await res.json();

      // Clear prompt and uploads only — preserve model/size/quality/count/parallel
      $('#prompt').value = '';
      savedPromptText = '';
      selectedFiles = [];
      selectedReferenceIds.clear();
      reusedReferencePaths = [];
      renderPreviews();
      renderReferencePicker();
      renderReferenceLibrary();

      // Poll immediately to show new task
      await pollTasks();

      // Scroll to and highlight the new task card
      const newCard = taskList.querySelector(`.task-card[data-id="${data.id}"]`);
      if (newCard) {
        newCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        newCard.classList.add('task-card-new');
        setTimeout(() => newCard.classList.remove('task-card-new'), 3000);
      }
    } catch (err) {
      alert('Error: ' + err.message);
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="btn-icon"><polygon points="5 3 19 12 5 21 5 3"/></svg> Generate`;
    }
  });

  // ---- Polling ----

  async function pollTasks() {
    try {
      const res = await fetch('/api/tasks');
      if (!res.ok) return;
      tasks = await res.json();
      renderTasks();
    } catch {
      // Silently ignore polling errors
    }
  }

  function startPolling() {
    pollTasks();
    pollTimer = setInterval(pollTasks, 5000);
  }

  function applyTaskToForm(task) {
    const params = task.params || {};
    switchView('generate');

    $('#prompt').value = task.prompt || '';
    modelSelect.value = task.model || modelSelect.value;
    updateSizeControl();
    $('#ratio').value = params.ratio || '';
    const activeSize = getActiveSizeSelect();
    if (activeSize) activeSize.value = params.size || '';
    $('#quality').value = params.quality || '';
    $('#count').value = params.count || 1;
    $('#parallel').checked = Boolean(params.parallel);

    selectedFiles = [];
    selectedReferenceIds.clear();
    (params.reference_image_ids || []).forEach((id) => selectedReferenceIds.add(String(id)));

    const hasLibraryIds = selectedReferenceIds.size > 0;
    reusedReferencePaths = (params.ref_image_paths || [])
      .filter((path) => path && !(hasLibraryIds && isLibraryReferencePath(path)));

    savedPromptText = $('#prompt').value;
    saveFormState();
    renderPreviews();
    renderReferencePicker();
    renderReferenceLibrary();
    form.scrollIntoView({ behavior: 'smooth', block: 'start' });
    $('#prompt').focus();
  }

  // ---- Filters ----

  $$('.filter-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      $$('.filter-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.filter;
      renderTasks();
    });
  });

  // ---- Render Tasks ----

  function renderTasks() {
    const filtered = currentFilter === 'all'
      ? tasks
      : tasks.filter((t) => t.status === currentFilter);

    if (filtered.length === 0) {
      taskEmpty.style.display = 'flex';
      // Remove all cards but keep empty state
      taskList.querySelectorAll('.task-card').forEach((el) => el.remove());
      return;
    }

    taskEmpty.style.display = 'none';

    // Build a set of existing card IDs for efficient update
    const existingCards = new Map();
    taskList.querySelectorAll('.task-card').forEach((el) => {
      existingCards.set(el.dataset.id, el);
    });

    const seenIds = new Set();

    // Keep DOM order identical to the filtered task order.
    let nextCardSlot = taskEmpty.nextSibling;
    for (const task of filtered) {
      const id = String(task.id);
      seenIds.add(id);

      let card;
      if (existingCards.has(id)) {
        // Update existing card in place
        card = existingCards.get(id);
        updateCard(card, task);
      } else {
        // Create new card
        card = buildCard(task);
      }

      if (card !== nextCardSlot) {
        taskList.insertBefore(card, nextCardSlot);
      }
      nextCardSlot = card.nextSibling;
    }

    // Remove cards that are no longer in the filtered list
    for (const [id, el] of existingCards) {
      if (!seenIds.has(id)) {
        el.remove();
      }
    }
  }

  function buildCard(task) {
    const card = document.createElement('div');
    card.className = 'task-card';
    card.dataset.id = task.id;
    updateCard(card, task);
    return card;
  }

  function updateCard(card, task) {
    const status = task.status;
    const params = task.params || {};
    const images = task.images || [];

    // Build detail chips
    let detailsHtml = '';
    if (params.ratio) detailsHtml += `<span class="task-detail"><strong>Ratio:</strong> ${esc(params.ratio)}</span>`;
    if (params.size) detailsHtml += `<span class="task-detail"><strong>Size:</strong> ${esc(params.size)}</span>`;
    if (params.quality) detailsHtml += `<span class="task-detail"><strong>Quality:</strong> ${esc(params.quality)}</span>`;
    if (params.count > 1) detailsHtml += `<span class="task-detail"><strong>Count:</strong> ${params.count}</span>`;
    detailsHtml += `<span class="task-detail"><strong>Created:</strong> ${formatTime(task.created_at)}</span>`;
    if (status === 'running' || status === 'succeeded') {
      const dur = frozenDurations.get(String(task.id)) || elapsed(task.created_at);
      detailsHtml += `<span class="task-detail"><strong>Duration:</strong> <span class="duration-value">${dur}</span></span>`;
    }

    // Status badge
    let badgeHtml = '';
    if (status === 'running') {
      badgeHtml = `<span class="status-badge status-running"><span class="pulse-dot"></span> Running</span>`;
    } else {
      badgeHtml = `<span class="status-badge status-${esc(status)}">${capitalize(status)}</span>`;
    }

    // Progress indicator for running tasks
    const progressHtml = status === 'running'
      ? `<div class="task-progress"><div class="task-progress-bar"><div class="task-progress-fill"></div></div><span class="task-progress-text">Generating...</span></div>`
      : '';

    // Error
    const errorHtml = status === 'failed' && task.error_message
      ? `<div class="task-error">${esc(task.error_message)}</div>`
      : '';

    // Thumbnail for succeeded tasks (first image as compact inline preview)
    let thumbnailHtml = '';
    const renderableImages = images
      .map((img) => ({ ...img, src: imageUrl(img.image_path) }))
      .filter((img) => img.src);

    if (status === 'succeeded' && renderableImages.length > 0) {
      const src = renderableImages[0].src;
      thumbnailHtml = `<div class="task-thumbnail" data-task="${task.id}" data-index="0">
        <img class="task-thumbnail-img" src="${esc(src)}" alt="Preview" loading="lazy">
      </div>`;
    }

    // Full images gallery
    let imagesHtml = '';
    if (renderableImages.length > 0) {
      const imgTags = renderableImages.map((img, i) => {
        const src = img.src;
        return `<div class="task-image-wrapper" data-task="${task.id}" data-index="${i}">
          <img class="task-image" src="${esc(src)}" alt="Generated image ${i + 1}" loading="lazy">
          <div class="task-image-overlay">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
          </div>
        </div>`;
      }).join('');
      imagesHtml = `<div class="task-images">${imgTags}</div>`;
    }

    card.innerHTML = `
      <button class="task-reuse-btn" data-task-id="${task.id}" title="Reuse prompt, settings, and references">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="17 1 21 5 17 9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><polyline points="7 23 3 19 7 15"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/>
        </svg>
      </button>
      <button class="task-copy-btn" data-task-id="${task.id}" title="Copy prompt">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
        </svg>
      </button>
      <button class="task-delete-btn" data-task-id="${task.id}" title="Delete task">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
        </svg>
      </button>
      <div class="task-card-header">
        <div class="task-header-row">
          ${thumbnailHtml}
          <div class="task-meta">
            <div class="task-id">#${task.id}</div>
            <div class="task-prompt">${esc(truncate(task.prompt, 120))}</div>
            <span class="task-model">${esc(task.model)}</span>
          </div>
        </div>
        ${badgeHtml}
      </div>
      <div class="task-details">${detailsHtml}</div>
      ${progressHtml}
      ${errorHtml}
      ${imagesHtml}
    `;

    // Manage duration ticker
    if (status === 'running') {
      startDurationTicker(String(task.id), task.created_at);
    } else if (status === 'succeeded') {
      if (!frozenDurations.has(String(task.id))) {
        frozenDurations.set(String(task.id), elapsed(task.created_at));
      }
      stopDurationTicker(String(task.id));
    } else {
      stopDurationTicker(String(task.id));
    }

    // Attach reuse handler
    const reuseBtn = card.querySelector('.task-reuse-btn');
    reuseBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const id = reuseBtn.dataset.taskId;
      const taskData = tasks.find((t) => String(t.id) === id);
      if (!taskData) return;
      applyTaskToForm(taskData);
      reuseBtn.classList.add('reused');
      setTimeout(() => reuseBtn.classList.remove('reused'), 1200);
    });

    // Attach delete handler
    const deleteBtn = card.querySelector('.task-delete-btn');
    deleteBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const id = deleteBtn.dataset.taskId;
      if (!confirm(`Delete task #${id}?`)) return;
      try {
        const res = await fetch(`/api/tasks/${id}`, { method: 'DELETE' });
        if (res.ok || res.status === 204) {
          tasks = tasks.filter((t) => String(t.id) !== id);
          card.remove();
        }
      } catch {}
    });

    // Attach copy prompt handler
    const copyBtn = card.querySelector('.task-copy-btn');
    copyBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const id = copyBtn.dataset.taskId;
      const taskData = tasks.find((t) => String(t.id) === id);
      if (!taskData) return;
      try {
        await navigator.clipboard.writeText(taskData.prompt);
        copyBtn.classList.add('copied');
        copyBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>`;
        setTimeout(() => {
          copyBtn.classList.remove('copied');
          copyBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`;
        }, 1500);
      } catch {}
    });

    // Attach lightbox click handlers (images gallery + thumbnail)
    card.querySelectorAll('.task-image-wrapper, .task-thumbnail').forEach((wrapper) => {
      wrapper.addEventListener('click', () => {
        const taskId = wrapper.dataset.task;
        const taskData = tasks.find((t) => String(t.id) === taskId);
        if (!taskData) return;
        const renderable = (taskData.images || []).filter((img) => imageUrl(img.image_path));
        openLightbox(renderable, parseInt(wrapper.dataset.index, 10));
      });
    });
  }

  function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function capitalize(s) {
    return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
  }

  // ---- Lightbox ----

  function openLightbox(images, index) {
    lightboxImages = images
      .map((img) => ({
        src: imageUrl(img.image_path),
        id: img.id,
      }))
      .filter((img) => img.src);
    if (lightboxImages.length === 0) return;
    lightboxIndex = index;
    renderLightbox();
    lightbox.classList.add('open');
    document.body.style.overflow = 'hidden';
  }

  function closeLightbox() {
    lightbox.classList.remove('open');
    document.body.style.overflow = '';
  }

  function renderLightbox() {
    const img = lightboxImages[lightboxIndex];
    if (!img) return;
    lightboxImg.src = img.src;
    lightboxInfo.textContent = `Image ${lightboxIndex + 1} of ${lightboxImages.length}`;
    lightboxDownload.href = img.src;
    lightboxDownload.download = img.src.split('/').pop() || 'image.jpeg';
  }

  function lightboxPrev() {
    if (lightboxImages.length <= 1) return;
    lightboxIndex = (lightboxIndex - 1 + lightboxImages.length) % lightboxImages.length;
    renderLightbox();
  }

  function lightboxNext() {
    if (lightboxImages.length <= 1) return;
    lightboxIndex = (lightboxIndex + 1) % lightboxImages.length;
    renderLightbox();
  }

  $('#lightboxClose').addEventListener('click', closeLightbox);
  $('#lightboxBackdrop').addEventListener('click', closeLightbox);
  $('#lightboxPrev').addEventListener('click', lightboxPrev);
  $('#lightboxNext').addEventListener('click', lightboxNext);

  document.addEventListener('keydown', (e) => {
    if (!lightbox.classList.contains('open')) return;
    if (e.key === 'Escape') closeLightbox();
    if (e.key === 'ArrowLeft') lightboxPrev();
    if (e.key === 'ArrowRight') lightboxNext();
  });

  // ---- Tab Switching ----
  $('#tabGenerate').addEventListener('click', () => switchView('generate'));
  $('#tabPrompts').addEventListener('click', () => switchView('prompts'));
  $('#savePromptBtn').addEventListener('click', () => {
    const ta = $('#savePromptText');
    addPrompt(ta.value);
    ta.value = '';
  });

  // ---- Init ----
  loadPromptLibrary();
  loadReferenceImages();
  restoreFormState();
  updateSizeControl();
  checkHealth();
  setInterval(checkHealth, 15000);
  startPolling();

})();
