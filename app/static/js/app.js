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
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
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

  function truncate(str, len = 100) {
    return str && str.length > len ? str.slice(0, len) + '...' : str || '';
  }

  function imageUrl(imagePath) {
    if (!imagePath) return '';
    // Strip absolute path prefix, keep only relative part from "output/"
    const idx = imagePath.indexOf('output/');
    if (idx !== -1) return '/' + imagePath.slice(idx);
    // Fallback: use the filename under the assumption of output/{task_id}/{gen_index}/file
    const parts = imagePath.replace(/\\/g, '/').split('/');
    const outIdx = parts.indexOf('output');
    if (outIdx !== -1) return '/' + parts.slice(outIdx).join('/');
    return imagePath;
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

  modelSelect.addEventListener('change', updateSizeControl);
  updateSizeControl();

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

  function renderPreviews() {
    uploadPreview.innerHTML = '';
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
        for (const f of selectedFiles) {
          fd.append('ref_images', f);
        }
        res = await fetch('/api/tasks/upload', { method: 'POST', body: fd });
      } else {
        // JSON
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

      // Reset form
      form.reset();
      selectedFiles = [];
      renderPreviews();
      updateSizeControl();

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
    pollTimer = setInterval(pollTasks, 2500);
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

    // Render from top (newest first since tasks are sorted desc)
    for (const task of filtered) {
      const id = String(task.id);
      seenIds.add(id);

      if (existingCards.has(id)) {
        // Update existing card in place
        updateCard(existingCards.get(id), task);
      } else {
        // Create new card
        const card = buildCard(task);
        // Insert after empty state or at the top
        if (taskList.firstElementChild === taskEmpty || taskList.children.length === 0) {
          taskList.appendChild(card);
        } else {
          taskList.insertBefore(card, taskList.firstElementChild);
        }
      }
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
      detailsHtml += `<span class="task-detail"><strong>Duration:</strong> ${elapsed(task.created_at)}</span>`;
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
    if (status === 'succeeded' && images.length > 0) {
      const src = imageUrl(images[0].image_path);
      thumbnailHtml = `<div class="task-thumbnail" data-task="${task.id}" data-index="0">
        <img class="task-thumbnail-img" src="${esc(src)}" alt="Preview" loading="lazy">
      </div>`;
    }

    // Full images gallery
    let imagesHtml = '';
    if (images.length > 0) {
      const imgTags = images.map((img, i) => {
        const src = imageUrl(img.image_path);
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
        openLightbox(taskData.images, parseInt(wrapper.dataset.index, 10));
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
    lightboxImages = images.map((img) => ({
      src: imageUrl(img.image_path),
      id: img.id,
    }));
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

  // ---- Init ----
  checkHealth();
  setInterval(checkHealth, 15000);
  startPolling();

})();
