(function () {
  'use strict';

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  let project = null;
  let tasks = [];
  let candidates = [];
  let referenceImages = [];
  let selectedReferenceIds = new Set();
  let ipReferenceIds = new Set(JSON.parse(localStorage.getItem('grsai_comic_ip_refs') || '[]'));
  let selectedFiles = [];
  let currentFilter = 'all';
  let currentMode = 'preview';
  let currentPageIndex = 0;
  const candidateIndexByPage = new Map();
  let promptLibrary = JSON.parse(localStorage.getItem('grsai_comic_prompts') || '{"cover":[],"numbered":[],"tail":[]}');
  let autoPromptIds = new Set(JSON.parse(sessionStorage.getItem('grsai_comic_auto_prompt_ids') || '[]'));

  if (performance.getEntriesByType('navigation')[0]?.type === 'reload') {
    sessionStorage.removeItem('grsai_comic_auto_prompt_ids');
    autoPromptIds = new Set();
  }

  const form = $('#comicForm');
  const pageType = $('#pageType');
  const pageNumber = $('#pageNumber');
  const promptEl = $('#prompt');
  const modelSelect = $('#model');
  const ratioSelect = $('#ratio');
  const ratioGroup = $('#ratioGroup');
  const sizeSelect = $('#size');
  const qualitySelect = $('#quality');
  const countInput = $('#count');
  const parallelInput = $('#parallel');
  const ipModeInput = $('#ipMode');
  const uploadZone = $('#uploadZone');
  const uploadInput = $('#refImages');
  const uploadPreview = $('#uploadPreview');
  const submitBtn = $('#submitBtn');
  const referenceSelectGrid = $('#referenceSelectGrid');
  const ipReferenceGrid = $('#ipReferenceGrid');
  const ipReferenceInput = $('#ipReferenceInput');
  const projectName = $('#projectName');
  const previewPane = $('#previewPane');
  const taskPane = $('#taskPane');
  const rightTitle = $('#rightTitle');
  const comicEmpty = $('#comicEmpty');
  const comicCarousel = $('#comicCarousel');
  const currentComicImage = $('#currentComicImage');
  const prevPageBtn = $('#prevPageBtn');
  const nextPageBtn = $('#nextPageBtn');
  const prevCandidateBtn = $('#prevCandidateBtn');
  const nextCandidateBtn = $('#nextCandidateBtn');
  const selectCandidateBtn = $('#selectCandidateBtn');
  const comicPageNav = $('#comicPageNav');
  const taskList = $('#taskList');
  const taskEmpty = $('#taskEmpty');

  function esc(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  }

  function imageUrl(path) {
    if (!path) return '';
    const normalized = path.replace(/\\/g, '/');
    const outIdx = normalized.split('/').indexOf('output');
    if (outIdx !== -1) {
      const parts = normalized.split('/');
      return '/' + parts.slice(outIdx).join('/');
    }
    return '';
  }

  function pageKey(candidate) {
    return candidate.page_type === 'numbered'
      ? `numbered:${candidate.page_number}`
      : candidate.page_type;
  }

  function pageLabel(page) {
    if (!page) return '';
    if (page.type === 'cover') return 'Cover';
    if (page.type === 'tail') return 'Tail';
    return `Page ${page.number}`;
  }

  function pageSortValue(page) {
    if (page.type === 'cover') return 0;
    if (page.type === 'tail') return 999;
    return page.number;
  }

  function candidateSrc(candidate) {
    return candidate.image_url || imageUrl(candidate.image_path);
  }

  function groupedPages() {
    const map = new Map();
    for (const candidate of candidates) {
      const key = pageKey(candidate);
      if (!map.has(key)) {
        map.set(key, {
          key,
          type: candidate.page_type,
          number: candidate.page_number,
          candidates: [],
        });
      }
      map.get(key).candidates.push(candidate);
    }
    return Array.from(map.values())
      .filter((page) => page.candidates.some((c) => candidateSrc(c)))
      .sort((a, b) => pageSortValue(a) - pageSortValue(b));
  }

  function activePage() {
    const pages = groupedPages();
    if (currentPageIndex >= pages.length) currentPageIndex = Math.max(0, pages.length - 1);
    return pages[currentPageIndex] || null;
  }

  function activeCandidate(page) {
    if (!page) return null;
    const selectedIndex = page.candidates.findIndex((c) => c.is_selected);
    const fallback = selectedIndex >= 0 ? selectedIndex : 0;
    const index = candidateIndexByPage.has(page.key)
      ? candidateIndexByPage.get(page.key)
      : fallback;
    return page.candidates[Math.min(index, page.candidates.length - 1)] || null;
  }

  async function checkHealth() {
    try {
      const res = await fetch('/api/health');
      $('#healthDot').classList.toggle('ok', res.ok);
      $('#healthText').textContent = res.ok ? 'Connected' : 'Error';
    } catch {
      $('#healthDot').classList.remove('ok');
      $('#healthText').textContent = 'Offline';
    }
  }

  async function loadProject() {
    const res = await fetch('/api/comic/projects/current');
    project = await res.json();
    projectName.textContent = project.name;
  }

  async function newProject() {
    const name = prompt('Project name?', 'Untitled Comic');
    if (name === null) return;
    const res = await fetch('/api/comic/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.trim() || 'Untitled Comic' }),
    });
    project = await res.json();
    projectName.textContent = project.name;
    candidates = [];
    currentPageIndex = 0;
    renderPreview();
  }

  async function loadCandidates() {
    if (!project) return;
    const res = await fetch(`/api/comic/projects/${project.id}/candidates`);
    candidates = await res.json();
    renderPreview();
  }

  async function loadTasks() {
    const res = await fetch('/api/tasks');
    if (!res.ok) return;
    tasks = await res.json();
    renderTasks();
  }

  async function loadReferenceImages() {
    const res = await fetch('/api/reference-images');
    if (!res.ok) return;
    referenceImages = await res.json();
    renderReferences();
  }

  function renderReferences() {
    const renderCard = (img, selected, extraClass = '') => `
      <button class="reference-select-card ${extraClass}${selected ? ' selected' : ''}" type="button" data-id="${img.id}" title="${esc(img.original_filename)}">
        <img src="${esc(img.image_url)}" alt="${esc(img.original_filename)}" loading="lazy">
        <span>${selected ? 'Selected' : 'Select'}</span>
      </button>
    `;
    referenceSelectGrid.innerHTML = referenceImages.length
      ? referenceImages.map((img) => renderCard(img, selectedReferenceIds.has(String(img.id)))).join('')
      : '<div class="reference-empty">No reference images yet.</div>';
    ipReferenceGrid.innerHTML = referenceImages.length
      ? referenceImages.map((img) => renderCard(img, ipReferenceIds.has(String(img.id)), 'ip-card ')).join('')
      : '<div class="reference-empty">No IP reference images yet.</div>';

    referenceSelectGrid.querySelectorAll('.reference-select-card').forEach((btn) => {
      btn.addEventListener('click', () => toggleSet(selectedReferenceIds, btn.dataset.id, renderReferences));
    });
    ipReferenceGrid.querySelectorAll('.reference-select-card').forEach((btn) => {
      btn.addEventListener('click', () => {
        toggleSet(ipReferenceIds, btn.dataset.id, renderReferences);
        localStorage.setItem('grsai_comic_ip_refs', JSON.stringify(Array.from(ipReferenceIds)));
      });
    });
  }

  function toggleSet(set, id, render) {
    const key = String(id);
    if (set.has(key)) set.delete(key);
    else set.add(key);
    render();
  }

  async function uploadIpReferences(files) {
    for (const file of Array.from(files || []).filter((f) => f.type.startsWith('image/'))) {
      const fd = new FormData();
      fd.append('image', file);
      const res = await fetch('/api/reference-images', { method: 'POST', body: fd });
      if (!res.ok) throw new Error('Upload failed');
      const img = await res.json();
      ipReferenceIds.add(String(img.id));
    }
    localStorage.setItem('grsai_comic_ip_refs', JSON.stringify(Array.from(ipReferenceIds)));
    await loadReferenceImages();
  }

  function renderPreview() {
    const pages = groupedPages();
    if (pages.length === 0) {
      comicEmpty.style.display = 'grid';
      comicCarousel.style.display = 'none';
      comicPageNav.innerHTML = '';
      return;
    }
    comicEmpty.style.display = 'none';
    comicCarousel.style.display = 'grid';

    const page = activePage();
    const candidate = activeCandidate(page);
    currentComicImage.src = candidateSrc(candidate);

    const prevPage = pages[currentPageIndex - 1];
    const nextPage = pages[currentPageIndex + 1];
    paintSide(prevPageBtn, prevPage, -1);
    paintSide(nextPageBtn, nextPage, 1);

    const candidateIndex = page.candidates.indexOf(candidate);
    prevCandidateBtn.disabled = page.candidates.length <= 1;
    nextCandidateBtn.disabled = page.candidates.length <= 1;
    selectCandidateBtn.classList.toggle('selected', Boolean(candidate?.is_selected));
    selectCandidateBtn.textContent = candidate?.is_selected ? 'Selected for this page' : 'Select for this page';

    prevCandidateBtn.onclick = () => {
      const next = (candidateIndex - 1 + page.candidates.length) % page.candidates.length;
      candidateIndexByPage.set(page.key, next);
      renderPreview();
    };
    nextCandidateBtn.onclick = () => {
      const next = (candidateIndex + 1) % page.candidates.length;
      candidateIndexByPage.set(page.key, next);
      renderPreview();
    };
    selectCandidateBtn.onclick = async () => {
      await fetch(`/api/comic/candidates/${candidate.id}/select`, { method: 'POST' });
      await loadCandidates();
    };

    comicPageNav.innerHTML = pages.map((p, i) => `
      <button class="comic-page-pill ${i === currentPageIndex ? 'active' : ''}" type="button" data-index="${i}">
        ${esc(pageLabel(p))}
      </button>
    `).join('');
    comicPageNav.querySelectorAll('.comic-page-pill').forEach((btn) => {
      btn.addEventListener('click', () => {
        currentPageIndex = parseInt(btn.dataset.index, 10);
        renderPreview();
      });
    });
  }

  function paintSide(btn, page, direction) {
    if (!page) {
      btn.disabled = true;
      btn.style.backgroundImage = '';
      btn.textContent = '';
      return;
    }
    btn.disabled = false;
    const candidate = activeCandidate(page);
    btn.style.backgroundImage = `url("${candidateSrc(candidate)}")`;
    btn.textContent = pageLabel(page);
    btn.onclick = () => {
      currentPageIndex += direction;
      currentComicImage.style.transform = `translateX(${direction * -28}px) scale(0.97)`;
      setTimeout(() => {
        currentComicImage.style.transform = '';
        renderPreview();
      }, 120);
    };
  }

  function pagePayload() {
    const type = pageType.value;
    const number = type === 'numbered' ? parseInt(pageNumber.value, 10) : null;
    if (type === 'numbered' && (!number || number < 1 || number > 20)) {
      throw new Error('Numbered pages must be between 1 and 20.');
    }
    return { type, number };
  }

  function activeAutoPrompts(type) {
    return (promptLibrary[type] || []).filter((p) => autoPromptIds.has(String(p.id)));
  }

  function buildPrompt() {
    const base = promptEl.value.trim();
    const extra = activeAutoPrompts(pageType.value).map((p) => p.text.trim()).filter(Boolean);
    return [base, ...extra].filter(Boolean).join('\n\n');
  }

  async function submitTask(e) {
    e.preventDefault();
    try {
      const page = pagePayload();
      submitBtn.disabled = true;
      submitBtn.textContent = 'Submitting...';
      const activeRefs = new Set(selectedReferenceIds);
      if (ipModeInput.checked) {
        for (const id of ipReferenceIds) activeRefs.add(id);
      }
      const body = {
        prompt: buildPrompt(),
        model: modelSelect.value,
        ratio: ratioSelect.value || null,
        size: sizeSelect.value || null,
        quality: qualitySelect.value || null,
        count: parseInt(countInput.value, 10) || 1,
        parallel: parallelInput.checked,
        reference_image_ids: Array.from(activeRefs).map((id) => parseInt(id, 10)),
        comic_project_id: project.id,
        comic_page_type: page.type,
        comic_page_number: page.number,
        comic_ip_mode: ipModeInput.checked,
        comic_auto_prompt_ids: activeAutoPrompts(page.type).map((p) => String(p.id)),
      };

      let res;
      if (selectedFiles.length > 0) {
        const fd = new FormData();
        Object.entries(body).forEach(([key, value]) => {
          if (value === null || value === undefined) return;
          if (Array.isArray(value)) value.forEach((item) => fd.append(key, item));
          else fd.append(key, value);
        });
        selectedFiles.forEach((file) => fd.append('ref_images', file));
        res = await fetch('/api/tasks/upload', { method: 'POST', body: fd });
      } else {
        res = await fetch('/api/tasks', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        });
      }
      if (!res.ok) throw new Error((await res.json()).detail || 'Submit failed');
      selectedFiles = [];
      uploadPreview.innerHTML = '';
      promptEl.value = '';
      await loadTasks();
    } catch (err) {
      alert(err.message);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Generate Comic Page';
    }
  }

  function addFiles(files) {
    selectedFiles.push(...Array.from(files || []).filter((f) => f.type.startsWith('image/')));
    renderUploads();
  }

  function renderUploads() {
    uploadPreview.innerHTML = selectedFiles.map((file, index) => `
      <div class="upload-thumb">
        <img src="${URL.createObjectURL(file)}" alt="${esc(file.name)}">
        <button class="upload-thumb-remove" type="button" data-index="${index}">x</button>
      </div>
    `).join('');
    uploadPreview.querySelectorAll('.upload-thumb-remove').forEach((btn) => {
      btn.addEventListener('click', () => {
        selectedFiles.splice(parseInt(btn.dataset.index, 10), 1);
        renderUploads();
      });
    });
  }

  function clipboardFiles(event) {
    return Array.from(event.clipboardData?.items || [])
      .filter((item) => item.kind === 'file' && item.type.startsWith('image/'))
      .map((item, index) => {
        const file = item.getAsFile();
        if (!file) return null;
        const ext = (file.type.split('/')[1] || 'png').replace('jpeg', 'jpg');
        return new File([file], file.name || `clipboard-${Date.now()}-${index}.${ext}`, { type: file.type });
      })
      .filter(Boolean);
  }

  function renderPromptLibrary() {
    const type = $('#promptPageType').value;
    const prompts = promptLibrary[type] || [];
    $('#comicPromptList').innerHTML = prompts.length ? prompts.map((p) => `
      <div class="prompt-card" data-id="${p.id}">
        <div class="prompt-card-text">${esc(p.text)}</div>
        <div class="prompt-card-actions">
          <button class="prompt-btn prompt-copy" type="button">Copy</button>
          <button class="prompt-btn prompt-use" type="button">Use</button>
          <button class="prompt-btn prompt-auto ${autoPromptIds.has(String(p.id)) ? 'active' : ''}" type="button">Auto tail</button>
          <button class="prompt-btn prompt-delete" type="button">Delete</button>
        </div>
      </div>
    `).join('') : '<div class="prompt-empty">No prompts for this page type.</div>';

    $('#comicPromptList').querySelectorAll('.prompt-card').forEach((card) => {
      const item = prompts.find((p) => String(p.id) === card.dataset.id);
      card.querySelector('.prompt-copy').onclick = () => navigator.clipboard.writeText(item.text);
      card.querySelector('.prompt-use').onclick = () => {
        promptEl.value = item.text;
        switchLeftView('generate');
      };
      card.querySelector('.prompt-auto').onclick = () => {
        const key = String(item.id);
        if (autoPromptIds.has(key)) autoPromptIds.delete(key);
        else autoPromptIds.add(key);
        sessionStorage.setItem('grsai_comic_auto_prompt_ids', JSON.stringify(Array.from(autoPromptIds)));
        renderPromptLibrary();
      };
      card.querySelector('.prompt-delete').onclick = () => {
        promptLibrary[type] = prompts.filter((p) => p.id !== item.id);
        localStorage.setItem('grsai_comic_prompts', JSON.stringify(promptLibrary));
        autoPromptIds.delete(String(item.id));
        renderPromptLibrary();
      };
    });
  }

  function renderTasks() {
    const filtered = currentFilter === 'all' ? tasks : tasks.filter((t) => t.status === currentFilter);
    if (filtered.length === 0) {
      taskEmpty.style.display = 'flex';
      taskList.querySelectorAll('.task-card').forEach((el) => el.remove());
      return;
    }
    taskEmpty.style.display = 'none';
    taskList.querySelectorAll('.task-card').forEach((el) => el.remove());
    for (const task of filtered) {
      const params = task.params || {};
      const card = document.createElement('div');
      card.className = 'task-card';
      card.dataset.id = task.id;
      card.innerHTML = `
        <button class="task-reuse-btn" title="Reuse prompt, settings, and references" type="button">↻</button>
        <div class="task-card-header">
          <div class="task-meta">
            <div class="task-id">#${task.id}</div>
            <div class="task-prompt">${esc(task.prompt.slice(0, 160))}</div>
            <span class="task-model">${esc(task.model)}</span>
          </div>
          <span class="status-badge status-${esc(task.status)}">${esc(task.status)}</span>
        </div>
        <div class="task-details">
          ${params.comic_page_type ? `<span class="task-detail"><strong>Comic:</strong> ${esc(params.comic_page_type)}${params.comic_page_number ? ' ' + params.comic_page_number : ''}</span>` : ''}
          ${params.size ? `<span class="task-detail"><strong>Size:</strong> ${esc(params.size)}</span>` : ''}
          ${params.quality ? `<span class="task-detail"><strong>Quality:</strong> ${esc(params.quality)}</span>` : ''}
        </div>
      `;
      card.querySelector('.task-reuse-btn').onclick = () => applyTaskToForm(task);
      taskList.appendChild(card);
    }
  }

  function applyTaskToForm(task) {
    const params = task.params || {};
    switchLeftView('generate');
    promptEl.value = task.prompt || '';
    modelSelect.value = task.model || modelSelect.value;
    updateModelControls();
    ratioSelect.value = params.ratio || '';
    sizeSelect.value = params.size || '';
    qualitySelect.value = params.quality || '';
    countInput.value = params.count || 1;
    parallelInput.checked = Boolean(params.parallel);
    pageType.value = params.comic_page_type || 'cover';
    pageNumber.value = params.comic_page_number || 1;
    ipModeInput.checked = Boolean(params.comic_ip_mode);
    selectedReferenceIds = new Set((params.reference_image_ids || []).map(String));
    renderReferences();
  }

  function switchLeftView(view) {
    $('#comicGenerateView').style.display = view === 'generate' ? 'flex' : 'none';
    $('#comicLibraryView').style.display = view === 'library' ? 'flex' : 'none';
    $('#tabComicGenerate').classList.toggle('active', view === 'generate');
    $('#tabComicLibrary').classList.toggle('active', view === 'library');
    if (view === 'library') renderPromptLibrary();
  }

  function switchRightMode(mode) {
    currentMode = mode;
    previewPane.style.display = mode === 'preview' ? 'grid' : 'none';
    taskPane.style.display = mode === 'tasks' ? 'flex' : 'none';
    rightTitle.textContent = mode === 'preview' ? 'Comic Preview' : 'Generation List';
    $('#previewModeBtn').classList.toggle('active', mode === 'preview');
    $('#tasksModeBtn').classList.toggle('active', mode === 'tasks');
  }

  function updateModelControls() {
    const isGpt = modelSelect.value.startsWith('gpt-image');
    ratioGroup.style.display = isGpt ? 'none' : 'flex';
  }

  function wireEvents() {
    form.addEventListener('submit', submitTask);
    $('#newProjectBtn').addEventListener('click', newProject);
    $('#tabComicGenerate').addEventListener('click', () => switchLeftView('generate'));
    $('#tabComicLibrary').addEventListener('click', () => switchLeftView('library'));
    $('#previewModeBtn').addEventListener('click', () => switchRightMode('preview'));
    $('#tasksModeBtn').addEventListener('click', () => switchRightMode('tasks'));
    $('#refreshReferenceBtn').addEventListener('click', loadReferenceImages);
    $('#promptPageType').addEventListener('change', renderPromptLibrary);
    $('#savePromptBtn').addEventListener('click', () => {
      const type = $('#promptPageType').value;
      const text = $('#savePromptText').value.trim();
      if (!text) return;
      promptLibrary[type] = promptLibrary[type] || [];
      promptLibrary[type].push({ id: Date.now(), text });
      localStorage.setItem('grsai_comic_prompts', JSON.stringify(promptLibrary));
      $('#savePromptText').value = '';
      renderPromptLibrary();
    });
    modelSelect.addEventListener('change', updateModelControls);
    uploadInput.addEventListener('change', () => {
      addFiles(uploadInput.files);
      uploadInput.value = '';
    });
    uploadZone.addEventListener('drop', (e) => {
      e.preventDefault();
      uploadZone.classList.remove('drag-over');
      addFiles(e.dataTransfer.files);
    });
    uploadZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      uploadZone.classList.add('drag-over');
    });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
    document.addEventListener('paste', (e) => {
      const files = clipboardFiles(e);
      if (files.length === 0) return;
      e.preventDefault();
      addFiles(files);
    });
    ipReferenceInput.addEventListener('change', async () => {
      await uploadIpReferences(ipReferenceInput.files);
      ipReferenceInput.value = '';
    });
    $$('#taskPane .filter-btn[data-filter]').forEach((btn) => {
      btn.addEventListener('click', () => {
        $$('#taskPane .filter-btn[data-filter]').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.dataset.filter;
        renderTasks();
      });
    });
  }

  async function init() {
    wireEvents();
    updateModelControls();
    await loadProject();
    await Promise.all([loadReferenceImages(), loadTasks(), loadCandidates(), checkHealth()]);
    setInterval(loadTasks, 5000);
    setInterval(loadCandidates, 7000);
    setInterval(checkHealth, 15000);
  }

  init();
})();
