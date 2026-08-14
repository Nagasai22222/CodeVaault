/* ─────────────────────────────────────────────────────────────────
   note.js — Note editor (Code-based, 2-step verification)
   Code 1 = note slug (URL), Code 2 = protection PIN (from sessionStorage)
   ───────────────────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', async () => {
  const notePage     = document.getElementById('notePage');
  const NOTE_ID      = notePage.dataset.noteId;
  const IS_PROTECTED = notePage.dataset.isProtected === 'true';

  // Try to retrieve Code 2 from sessionStorage (set by landing page after 2-step verify)
  let noteCode2  = sessionStorage.getItem('cv_code2_' + NOTE_ID) || '';
  let editor     = null;
  let noteData   = null;
  let saveTimeout = null;
  let previewOpen = false;
  let filesOpen   = false;
  let historyOpen = false;

  const MODES = {
    plaintext: null, markdown: 'markdown', python: 'python',
    javascript: 'javascript', java: { name: 'clike', mime: 'text/x-java' },
    clike: 'clike', xml: 'xml', css: 'css', sql: 'sql',
  };

  const LANG_LABELS = {
    plaintext: 'Plain Text', markdown: 'Markdown', python: 'Python',
    javascript: 'JavaScript', java: 'Java', clike: 'C/C++',
    xml: 'HTML/XML', css: 'CSS', sql: 'SQL',
  };

  // ── Helpers ────────────────────────────────────────────────────
  function apiHeaders(extra = {}) {
    const h = { 'Content-Type': 'application/json', ...extra };
    if (noteCode2) h['X-Code2'] = noteCode2;
    return h;
  }

  function escHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function fmtDate(iso) {
    if (!iso) return '';
    const d = new Date(iso), diff = Date.now() - d.getTime();
    if (diff < 60000)    return 'just now';
    if (diff < 3600000)  return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return d.toLocaleDateString();
  }

  function fileEmoji(mime) {
    if (!mime) return '📄';
    if (mime.startsWith('image/'))  return '🖼️';
    if (mime === 'application/pdf') return '📕';
    if (mime.includes('zip') || mime.includes('tar')) return '📦';
    if (mime.startsWith('video/'))  return '🎬';
    if (mime.startsWith('audio/'))  return '🎵';
    if (mime.includes('word'))      return '📝';
    if (mime.includes('excel') || mime.includes('spreadsheet')) return '📊';
    return '📎';
  }

  // ── CodeMirror ─────────────────────────────────────────────────
  function initEditor(content, language) {
    const theme = document.documentElement.getAttribute('data-theme');
    editor = CodeMirror.fromTextArea(document.getElementById('noteEditor'), {
      mode: MODES[language] || null,
      theme: theme === 'dark' ? 'dracula' : 'eclipse',
      lineNumbers: true,
      matchBrackets: true,
      autoCloseBrackets: true,
      lineWrapping: true,
      indentUnit: 2, tabSize: 2,
      autofocus: true,
    });
    // Set the initial value AFTER initialization, since fromTextArea ignores the 'value' option
    editor.setValue(content || '');
    
    editor.on('change', () => { scheduleAutoSave(); updateStatusBar(); });
    const themeBtn = document.getElementById('themeToggle');
    if (themeBtn) {
      themeBtn.addEventListener('click', () => {
        setTimeout(() => {
          const t = document.documentElement.getAttribute('data-theme');
          editor.setOption('theme', t === 'dark' ? 'dracula' : 'eclipse');
        }, 50);
      });
    }
  }

  // ── Populate ───────────────────────────────────────────────────
  function populateUI(data) {
    noteData = data;
    document.getElementById('noteTitle').value = data.title || '';
    document.getElementById('languageSelect').value = data.language || 'plaintext';
    if (editor) {
      editor.setValue(data.content || '');
      editor.setOption('mode', MODES[data.language] || null);
    } else {
      initEditor(data.content || '', data.language || 'plaintext');
    }
    updateStatusBar();
    updateFileBadge(data.file_count || 0);
    setStatusSaved('All changes saved');
  }

  // ── Load note ─────────────────────────────────────────────────
  async function loadNote() {
    const res = await fetch(`/api/notes/${NOTE_ID}`, { headers: apiHeaders() });
    const data = await res.json();

    if (res.status === 401) {
      // Protected and code2 from sessionStorage was wrong / missing → go back home
      showToast('2nd code required. Redirecting…', 'error', 2000);
      sessionStorage.removeItem('cv_code2_' + NOTE_ID);
      setTimeout(() => window.location.href = '/', 2000);
      return null;
    }
    if (res.status === 410) {
      showToast('This note has expired.', 'error', 4000);
      setTimeout(() => window.location.href = '/', 2000);
      return null;
    }
    if (!res.ok) {
      showToast(data.error || 'Failed to load note', 'error');
      return null;
    }
    return data;
  }

  // ── Initial load ───────────────────────────────────────────────
  const data = await loadNote();
  if (data) populateUI(data);
  else if (!IS_PROTECTED) initEditor('', 'plaintext');

  // ── Save ───────────────────────────────────────────────────────
  async function saveNote(showMsg = true) {
    if (!editor) return;
    setStatusSaved('Saving…');

    const payload = {
      title:    document.getElementById('noteTitle').value.trim() || 'Untitled Note',
      content:  editor.getValue(),
      language: document.getElementById('languageSelect').value,
    };

    const res = await fetch(`/api/notes/${NOTE_ID}`, {
      method: 'PUT',
      headers: apiHeaders(),
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      noteData = (await res.json()).note;
      setStatusSaved('All changes saved');
      if (showMsg) showToast('Saved!', 'success', 2000);
    } else {
      setStatusSaved('Save failed');
      showToast('Failed to save', 'error');
    }
  }

  function scheduleAutoSave() {
    setStatusSaved('Unsaved changes…');
    if (saveTimeout) clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => saveNote(false), 1500);
  }

  document.getElementById('saveBtn').addEventListener('click', () => saveNote(true));
  document.getElementById('saveCloseBtn').addEventListener('click', async () => {
    await saveNote(false);
    window.location.href = '/';
  });

  // Ctrl+S
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); saveNote(true); }
  });

  // ── Language ───────────────────────────────────────────────────
  document.getElementById('languageSelect').addEventListener('change', function() {
    if (!editor) return;
    editor.setOption('mode', MODES[this.value] || null);
    document.getElementById('statusLang').textContent = LANG_LABELS[this.value] || this.value;
    scheduleAutoSave();
  });

  // ── Markdown Preview ───────────────────────────────────────────
  document.getElementById('previewToggle').addEventListener('click', () => {
    const cm = document.querySelector('.CodeMirror');
    const pane = document.getElementById('previewPane');
    previewOpen = !previewOpen;
    if (previewOpen) {
      pane.style.display = 'block';
      if (cm) cm.style.display = 'none';
      editor && editor.on('change', updatePreview);
      updatePreview();
      document.getElementById('previewToggle').textContent = '✏ Edit';
    } else {
      pane.style.display = 'none';
      if (cm) cm.style.display = '';
      editor && editor.off('change', updatePreview);
      document.getElementById('previewToggle').innerHTML =
        `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg> Preview`;
    }
  });

  function updatePreview() {
    const pane = document.getElementById('previewPane');
    if (pane.style.display !== 'none' && editor)
      pane.innerHTML = marked.parse(editor.getValue());
  }

  // ── Share ──────────────────────────────────────────────────────
  document.getElementById('shareBtn').addEventListener('click', async () => {
    await copyToClipboard(window.location.href);
    showToast('Link copied!', 'success');
  });

  // ── Delete ─────────────────────────────────────────────────────
  document.getElementById('deleteBtn').addEventListener('click', async () => {
    if (!confirm('Delete this note permanently? This cannot be undone.')) return;
    const res = await fetch(`/api/notes/${NOTE_ID}`, {
      method: 'DELETE',
      headers: apiHeaders(),
      body: JSON.stringify({ code2: noteCode2 }),
    });
    if (res.ok) {
      sessionStorage.removeItem('cv_code2_' + NOTE_ID);
      showToast('Note deleted.', 'success');
      setTimeout(() => window.location.href = '/', 1000);
    } else {
      showToast('Failed to delete note.', 'error');
    }
  });

  // ── 2-Step Protection toggle ────────────────────────────────────
  // Add a "🔐 Protect" button that shows a mini panel
  const protectBtn = document.createElement('button');
  protectBtn.className = 'btn btn-ghost btn-sm toolbar-btn';
  protectBtn.id = 'protectBtn';
  protectBtn.title = 'Enable / manage 2nd-code protection';
  protectBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg> 2-Step`;
  document.getElementById('deleteBtn').before(protectBtn);

  // Mini protection panel (injected dynamically)
  const secPanelHtml = `
    <div class="sec-panel" id="secPanel" style="display:none;">
      <h4>🔐 Two-Step Protection</h4>
      <div id="secCurrentStatus" style="font-size:0.8rem;color:var(--text-secondary);margin-bottom:12px;"></div>
      <div class="form-group">
        <label class="label">Set new 2nd Code</label>
        <input type="password" id="newCode2" class="input" placeholder="New 2nd code…" />
      </div>
      <div style="display:flex;gap:8px;">
        <button class="btn btn-success btn-sm" id="setCode2Btn" style="flex:1;">Save</button>
        <button class="btn btn-danger btn-sm" id="removeCode2Btn">Remove</button>
        <button class="btn btn-ghost btn-sm" id="closeSecPanel">✕</button>
      </div>
    </div>`;
  document.body.insertAdjacentHTML('beforeend', secPanelHtml);

  protectBtn.addEventListener('click', () => {
    const panel = document.getElementById('secPanel');
    const isOpen = panel.style.display !== 'none';
    panel.style.display = isOpen ? 'none' : '';
    if (!isOpen) {
      const status = document.getElementById('secCurrentStatus');
      status.textContent = noteData && noteData.is_password_protected
        ? '✅ Protection is ON. Enter a new 2nd code to change it.'
        : '⚠️ Protection is OFF. Set a 2nd code to enable two-step verification.';
    }
  });

  document.getElementById('closeSecPanel').addEventListener('click', () => {
    document.getElementById('secPanel').style.display = 'none';
  });

  document.getElementById('setCode2Btn').addEventListener('click', async () => {
    const newCode2 = document.getElementById('newCode2').value.trim();
    if (!newCode2) { showToast('Enter a 2nd code first.', 'error'); return; }

    const res = await fetch(`/api/notes/${NOTE_ID}`, {
      method: 'PUT',
      headers: apiHeaders(),
      body: JSON.stringify({ new_code2: newCode2 }),
    });

    if (res.ok) {
      noteCode2 = newCode2;
      sessionStorage.setItem('cv_code2_' + NOTE_ID, newCode2);
      noteData = (await res.json()).note;
      document.getElementById('secPanel').style.display = 'none';
      document.getElementById('newCode2').value = '';
      showToast('2-step protection enabled!', 'success');
    } else {
      showToast('Failed to set 2nd code.', 'error');
    }
  });

  document.getElementById('removeCode2Btn').addEventListener('click', async () => {
    if (!confirm('Remove 2nd-code protection? Anyone with Code 1 can access this note.')) return;
    const res = await fetch(`/api/notes/${NOTE_ID}`, {
      method: 'PUT',
      headers: apiHeaders(),
      body: JSON.stringify({ remove_code2: true }),
    });
    if (res.ok) {
      noteCode2 = '';
      sessionStorage.removeItem('cv_code2_' + NOTE_ID);
      noteData = (await res.json()).note;
      document.getElementById('secPanel').style.display = 'none';
      showToast('Protection removed.', 'info');
    } else {
      showToast('Failed to remove protection.', 'error');
    }
  });

  // ── Files Panel ────────────────────────────────────────────────
  document.getElementById('filesToggle').addEventListener('click', () => {
    filesOpen = !filesOpen;
    document.getElementById('filesPanel').style.display = filesOpen ? '' : 'none';
    if (filesOpen) { historyOpen = false; document.getElementById('historyPanel').style.display = 'none'; loadFiles(); }
  });
  document.getElementById('closeFilesPanel').addEventListener('click', () => {
    filesOpen = false; document.getElementById('filesPanel').style.display = 'none';
  });

  const fileInput  = document.getElementById('fileInput');
  const uploadZone = document.getElementById('uploadZone');
  document.getElementById('browseBtn').addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => handleFiles(fileInput.files));
  uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('dragover'); });
  uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
  uploadZone.addEventListener('drop', e => { e.preventDefault(); uploadZone.classList.remove('dragover'); handleFiles(e.dataTransfer.files); });

  async function handleFiles(files) {
    for (const f of files) await uploadFile(f);
    await loadFiles();
  }

  async function uploadFile(file) {
    const prog = document.getElementById('uploadProgress');
    const fill = document.getElementById('progressFill');
    const stat = document.getElementById('uploadStatus');
    prog.style.display = ''; fill.style.width = '10%';
    stat.textContent = `Uploading ${file.name}…`;
    const fd = new FormData();
    fd.append('file', file);
    try {
      fill.style.width = '60%';
      const h = noteCode2 ? { 'X-Code2': noteCode2 } : {};
      const res = await fetch(`/api/notes/${NOTE_ID}/files`, { method: 'POST', headers: h, body: fd });
      fill.style.width = '100%';
      const d = await res.json();
      res.ok ? showToast(`${file.name} uploaded!`, 'success') : showToast(d.error || 'Upload failed', 'error');
    } catch (e) { showToast('Upload error: ' + e.message, 'error'); }
    setTimeout(() => { prog.style.display = 'none'; fill.style.width = '0%'; }, 800);
  }

  async function loadFiles() {
    const res = await fetch(`/api/notes/${NOTE_ID}/files`, { headers: apiHeaders() });
    if (!res.ok) return;
    const files = await res.json();
    renderFiles(files);
    updateFileBadge(files.length);
  }

  function renderFiles(files) {
    const list = document.getElementById('filesList');
    if (!files.length) {
      list.innerHTML = '<p style="text-align:center;color:var(--text-muted);font-size:0.85rem;padding:16px;">No files attached yet.</p>';
      return;
    }
    const qp = noteCode2 ? `?code2=${encodeURIComponent(noteCode2)}` : '';
    list.innerHTML = files.map(f => `
      <div class="file-item" data-id="${f.id}">
        <div class="file-icon">${fileEmoji(f.mime_type)}</div>
        <div class="file-info">
          <div class="file-name" title="${escHtml(f.filename)}">${escHtml(f.filename)}</div>
          <div class="file-meta">${f.file_size_human} · ${fmtDate(f.uploaded_at)}</div>
        </div>
        <div class="file-actions">
          ${f.is_image ? `<button class="file-action-btn" title="Preview" onclick="previewImg(${f.id})"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button>` : ''}
          <a class="file-action-btn" title="Download" href="/api/files/${f.id}/download${qp}" download="${escHtml(f.filename)}"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg></a>
          <button class="file-action-btn delete" title="Delete" onclick="deleteFile(${f.id})"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg></button>
        </div>
      </div>`).join('');
  }

  window.deleteFile = async function(fileId) {
    if (!confirm('Delete this file?')) return;
    const res = await fetch(`/api/files/${fileId}`, { method: 'DELETE', headers: apiHeaders(), body: JSON.stringify({ code2: noteCode2 }) });
    res.ok ? (showToast('File deleted.', 'success'), await loadFiles()) : showToast('Failed to delete file.', 'error');
  };
  window.previewImg = function(fileId) {
    const qp = noteCode2 ? `?code2=${encodeURIComponent(noteCode2)}` : '';
    window.open(`/api/files/${fileId}/preview${qp}`, '_blank');
  };

  function updateFileBadge(count) {
    const badge = document.getElementById('fileBadge');
    badge.style.display = count > 0 ? '' : 'none';
    badge.textContent = count;
  }

  // ── History ────────────────────────────────────────────────────
  document.getElementById('historyToggle').addEventListener('click', () => {
    historyOpen = !historyOpen;
    document.getElementById('historyPanel').style.display = historyOpen ? '' : 'none';
    if (historyOpen) { filesOpen = false; document.getElementById('filesPanel').style.display = 'none'; loadHistory(); }
  });
  document.getElementById('closeHistoryPanel').addEventListener('click', () => {
    historyOpen = false; document.getElementById('historyPanel').style.display = 'none';
  });

  async function loadHistory() {
    const res = await fetch(`/api/notes/${NOTE_ID}/history`, { headers: apiHeaders() });
    if (!res.ok) return;
    renderHistory(await res.json());
  }

  function renderHistory(history) {
    const list = document.getElementById('historyList');
    if (!history.length) {
      list.innerHTML = '<p style="text-align:center;color:var(--text-muted);font-size:0.85rem;padding:16px;">No history yet.</p>';
      return;
    }
    list.innerHTML = history.map(h => `
      <div class="history-item">
        <div class="history-meta">
          <span class="history-time">${fmtDate(h.saved_at)}</span>
          <button class="history-restore" onclick="restoreHistory(${h.id})">Restore</button>
        </div>
        <div class="history-preview">${escHtml(h.content_preview)}</div>
      </div>`).join('');
  }

  window.restoreHistory = async function(historyId) {
    if (!confirm('Restore this version?')) return;
    const res = await fetch(`/api/notes/${NOTE_ID}/history/${historyId}/restore`, { method: 'POST', headers: apiHeaders(), body: JSON.stringify({ code2: noteCode2 }) });
    if (res.ok) {
      populateUI((await res.json()).note);
      showToast('Version restored!', 'success');
      historyOpen = false;
      document.getElementById('historyPanel').style.display = 'none';
    } else { showToast('Restore failed.', 'error'); }
  };

  // ── Status Bar ─────────────────────────────────────────────────
  function updateStatusBar() {
    const content = editor ? editor.getValue() : '';
    document.getElementById('statusChars').textContent = `${content.length.toLocaleString()} chars`;
    const lang = document.getElementById('languageSelect').value;
    document.getElementById('statusLang').textContent = LANG_LABELS[lang] || lang;
    if (noteData) document.getElementById('statusViews').textContent = `${noteData.views || 0} views`;
  }

  function setStatusSaved(msg) {
    const el = document.getElementById('statusSaved');
    if (!el) return;
    el.textContent = msg;
    el.style.color = msg.includes('saved') ? 'var(--accent-green)' : 'var(--text-muted)';
  }
});
