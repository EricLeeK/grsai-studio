(function () {
  'use strict';

  const $ = (sel) => document.querySelector(sel);

  let selectedStyle = 'minimal';
  let currentHtml = '';
  let coverMediaId = '';
  let coverTaskId = null;
  let coverPollTimer = null;

  const markdownInput = $('#markdownInput');
  const markdownFile = $('#markdownFile');
  const convertBtn = $('#convertBtn');
  const previewFrame = $('#previewFrame');
  const statusText = $('#statusText');
  const coverFile = $('#coverFile');
  const coverPrompt = $('#coverPrompt');
  const generateCoverBtn = $('#generateCoverBtn');
  const coverMedia = $('#coverMediaId');
  const titleInput = $('#titleInput');
  const authorInput = $('#authorInput');
  const digestInput = $('#digestInput');
  const draftBtn = $('#draftBtn');
  const resultLine = $('#resultLine');
  const copyHtmlBtn = $('#copyHtmlBtn');
  const STATE_KEY = 'grsai_publisher_session';

  function setStatus(text, tone) {
    statusText.textContent = text;
    statusText.classList.toggle('ok', tone === 'ok');
    statusText.classList.toggle('error', tone === 'error');
  }

  function setBusy(button, busy, label) {
    if (!button) return;
    if (busy) {
      button.dataset.label = button.textContent;
      button.textContent = label;
      button.disabled = true;
    } else {
      button.textContent = button.dataset.label || button.textContent;
      button.disabled = false;
    }
  }

  function renderPreview(html) {
    const shell = `<!doctype html>
      <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
          body { margin: 0; padding: 28px 18px 56px; background: #f7f4ec; color: #1d1d1b; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
          .wechat-canvas { max-width: 680px; margin: 0 auto; background: #fffdf7; padding: 22px 18px; box-shadow: 0 20px 60px rgba(28, 24, 14, .12); }
          img { max-width: 100%; height: auto; }
        </style>
      </head>
      <body><main class="wechat-canvas">${html || '<p style="color:#777">Converted HTML will appear here.</p>'}</main></body>
      </html>`;
    previewFrame.srcdoc = shell;
  }

  function collectState() {
    return {
      markdown: markdownInput.value,
      style: selectedStyle,
      html: currentHtml,
      coverMediaId,
      coverTaskId,
      coverPrompt: coverPrompt.value,
      title: titleInput.value,
      author: authorInput.value,
      digest: digestInput.value,
      result: resultLine.innerHTML,
    };
  }

  function saveState() {
    sessionStorage.setItem(STATE_KEY, JSON.stringify(collectState()));
  }

  function restoreState() {
    const nav = performance.getEntriesByType('navigation')[0];
    if (nav && nav.type === 'reload') {
      sessionStorage.removeItem(STATE_KEY);
      return;
    }

    let state = null;
    try {
      state = JSON.parse(sessionStorage.getItem(STATE_KEY) || 'null');
    } catch {
      state = null;
    }
    if (!state) return;

    markdownInput.value = state.markdown || '';
    coverPrompt.value = state.coverPrompt || '';
    titleInput.value = state.title || '';
    authorInput.value = state.author || '';
    digestInput.value = state.digest || '';
    currentHtml = state.html || '';
    coverMediaId = state.coverMediaId || '';
    coverTaskId = state.coverTaskId || null;
    resultLine.innerHTML = state.result || '';
    coverMedia.textContent = coverMediaId || (coverTaskId ? `Task #${coverTaskId}` : 'No media_id');

    if (state.style) {
      selectedStyle = state.style;
      document.querySelectorAll('.segment-btn').forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.style === selectedStyle);
      });
    }
    renderPreview(currentHtml);
    if (coverTaskId && !coverMediaId) {
      resumeCoverTask(coverTaskId);
    }
  }

  function inferTitle(markdown) {
    const heading = markdown.split('\n').find((line) => line.trim().startsWith('# '));
    return heading ? heading.replace(/^#\s+/, '').trim() : '';
  }

  async function readError(response) {
    const data = await response.json().catch(() => ({}));
    return data.detail || response.statusText || 'Request failed';
  }

  function clearCoverTaskState() {
    if (coverPollTimer) clearInterval(coverPollTimer);
    coverPollTimer = null;
    coverTaskId = null;
    saveState();
    setBusy(generateCoverBtn, false);
  }

  document.querySelectorAll('.segment-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.segment-btn').forEach((item) => item.classList.remove('active'));
      btn.classList.add('active');
      selectedStyle = btn.dataset.style;
      saveState();
    });
  });

  markdownFile.addEventListener('change', async () => {
    const file = markdownFile.files[0];
    if (!file) return;
    markdownInput.value = await file.text();
    if (!titleInput.value.trim()) titleInput.value = inferTitle(markdownInput.value);
    markdownFile.value = '';
    saveState();
  });

  markdownInput.addEventListener('blur', () => {
    if (!titleInput.value.trim()) titleInput.value = inferTitle(markdownInput.value);
    saveState();
  });

  [markdownInput, coverPrompt, titleInput, authorInput, digestInput].forEach((el) => {
    el.addEventListener('input', saveState);
  });

  convertBtn.addEventListener('click', async () => {
    const markdown = markdownInput.value.trim();
    if (!markdown) {
      setStatus('Markdown required', 'error');
      return;
    }

    setBusy(convertBtn, true, 'Converting...');
    setStatus('Converting', '');
    try {
      const response = await fetch('/api/publisher/convert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ markdown, style: selectedStyle }),
      });
      if (!response.ok) throw new Error(await readError(response));
      const data = await response.json();
      currentHtml = data.html;
      renderPreview(currentHtml);
      if (!titleInput.value.trim()) titleInput.value = inferTitle(markdown);
      setStatus('Converted', 'ok');
      saveState();
    } catch (err) {
      setStatus(err.message, 'error');
    } finally {
      setBusy(convertBtn, false);
    }
  });

  async function uploadCover(formData) {
    const response = await fetch('/api/publisher/upload-cover', { method: 'POST', body: formData });
    if (!response.ok) throw new Error(await readError(response));
    const data = await response.json();
    coverMediaId = data.media_id;
    coverMedia.textContent = coverMediaId;
    saveState();
    return data;
  }

  async function createCoverTask(prompt) {
    const response = await fetch('/api/publisher/generate-cover-task', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt,
        model: 'gpt-image-2-vip',
        size: '2048x1152',
        quality: 'high',
      }),
    });
    if (!response.ok) throw new Error(await readError(response));
    return response.json();
  }

  async function uploadCoverFromTask(taskId) {
    const response = await fetch('/api/publisher/upload-cover-from-task', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: taskId }),
    });
    if (!response.ok) throw new Error(await readError(response));
    const data = await response.json();
    coverMediaId = data.media_id;
    coverMedia.textContent = coverMediaId;
    coverTaskId = null;
    saveState();
    return data;
  }

  function resumeCoverTask(taskId) {
    if (coverPollTimer) clearInterval(coverPollTimer);
    setBusy(generateCoverBtn, true, `Task #${taskId}`);
    setStatus(`Cover task #${taskId}`, '');
    coverMedia.textContent = `Task #${taskId}`;
    coverPollTimer = setInterval(async () => {
      try {
        const response = await fetch(`/api/tasks/${taskId}`);
        if (response.status === 404) {
          clearCoverTaskState();
          coverMedia.textContent = coverMediaId || 'No media_id';
          setStatus('Cover task not found. Start a new one.', 'error');
          return;
        }
        if (!response.ok) throw new Error(await readError(response));
        const task = await response.json();
        if (task.status === 'running' || task.status === 'pending') {
          setStatus(`Cover ${task.status} #${taskId}`, '');
          return;
        }
        clearInterval(coverPollTimer);
        coverPollTimer = null;
        if (task.status === 'succeeded') {
          setStatus('Uploading generated cover', '');
          await uploadCoverFromTask(taskId);
          setStatus('Cover ready', 'ok');
        } else {
          throw new Error(task.error_message || 'Cover task failed');
        }
      } catch (err) {
        clearInterval(coverPollTimer);
        coverPollTimer = null;
        coverTaskId = null;
        saveState();
        setStatus(err.message, 'error');
      } finally {
        if (!coverPollTimer) {
          setBusy(generateCoverBtn, false);
        }
      }
    }, 3000);
  }

  coverFile.addEventListener('change', async () => {
    const file = coverFile.files[0];
    if (!file) return;
    const form = new FormData();
    form.append('cover', file);
    setStatus('Uploading cover', '');
    try {
      await uploadCover(form);
      setStatus('Cover uploaded', 'ok');
      coverTaskId = null;
      saveState();
    } catch (err) {
      setStatus(err.message, 'error');
    } finally {
      coverFile.value = '';
    }
  });

  generateCoverBtn.addEventListener('click', async () => {
    const prompt = coverPrompt.value.trim();
    if (!prompt) {
      setStatus('Cover prompt required', 'error');
      return;
    }
    clearCoverTaskState();
    coverMediaId = '';
    coverMedia.textContent = 'No media_id';
    setBusy(generateCoverBtn, true, 'Creating task...');
    setStatus('Creating cover task', '');
    try {
      const task = await createCoverTask(prompt);
      coverTaskId = task.id;
      coverMediaId = '';
      coverMedia.textContent = `Task #${coverTaskId}`;
      saveState();
      resumeCoverTask(coverTaskId);
    } catch (err) {
      setStatus(err.message, 'error');
      setBusy(generateCoverBtn, false);
    }
  });

  draftBtn.addEventListener('click', async () => {
    if (!currentHtml) {
      setStatus('Convert first', 'error');
      return;
    }
    if (!coverMediaId) {
      setStatus('Cover media_id required', 'error');
      return;
    }
    const title = titleInput.value.trim();
    if (!title) {
      setStatus('Title required', 'error');
      return;
    }

    setBusy(draftBtn, true, 'Publishing...');
    setStatus('Creating draft', '');
    resultLine.textContent = '';
    try {
      const response = await fetch('/api/publisher/draft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title,
          content_html: currentHtml,
          cover_media_id: coverMediaId,
          author: authorInput.value.trim(),
          digest: digestInput.value.trim(),
        }),
      });
      if (!response.ok) throw new Error(await readError(response));
      const data = await response.json();
      resultLine.innerHTML = `Draft media_id: <strong>${data.media_id}</strong> · <a href="${data.draft_url}" target="_blank" rel="noreferrer">Open WeChat backend</a>`;
      setStatus('Draft created', 'ok');
      saveState();
    } catch (err) {
      setStatus(err.message, 'error');
    } finally {
      setBusy(draftBtn, false);
    }
  });

  copyHtmlBtn.addEventListener('click', async () => {
    if (!currentHtml) {
      setStatus('Nothing to copy', 'error');
      return;
    }
    await navigator.clipboard.writeText(currentHtml);
    setStatus('HTML copied', 'ok');
  });

  renderPreview('');
  restoreState();
})();
