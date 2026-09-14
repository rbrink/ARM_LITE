const settingsLoading = document.getElementById('settingsLoading');
const settingsForm = document.getElementById('settingsForm');
const settingsMessage = document.getElementById('settingsMessage');
const settingsSaveBtn = document.getElementById('settingsSaveBtn');

const TOOL_STATUS_FIELDS = {
  MAKEMKVCON_PATH: 'makemkv',
  CDPARANOIA_PATH: 'cdparanoia',
  FFMPEG_PATH: 'ffmpeg',
  HANDBRAKE_CLI: 'handbrake',
};

let requiresRestartFields = [];

async function loadSettings() {
  try {
    const [settingsRes, systemRes] = await Promise.all([
      fetch('/settings/api'),
      fetch('/api/system'),
    ]);
    const settingsData = await settingsRes.json();
    const systemData = await systemRes.json();

    if (!settingsRes.ok) throw new Error(settingsData.error || 'Failed to load settings');

    populateForm(settingsData.values);
    requiresRestartFields = settingsData.requires_restart || [];
    requiresRestartFields.forEach(key => {
      const tag = document.getElementById(`restart-${key}`);
      if (tag) tag.hidden = false;
    });

    renderToolStatus(systemData.tooling || {});

    settingsLoading.hidden = true;
    settingsForm.hidden = false;
  } catch (e) {
    settingsLoading.textContent = `Couldn't load settings: ${e.message}`;
  }
}

function populateForm(values) {
  for (const [key, value] of Object.entries(values)) {
    const el = document.getElementById(key);
    if (!el) continue;
    if (el.type === 'checkbox') {
      el.checked = !!value;
    } else if (key === 'DRIVE_LETTERS') {
      el.value = Array.isArray(value) ? value.join(', ') : (value || '');
    } else {
      el.value = value ?? '';
    }
  }
}

function renderToolStatus(tooling) {
  for (const [fieldId, toolKey] of Object.entries(TOOL_STATUS_FIELDS)) {
    const dotEl = document.getElementById(`status-${fieldId}`);
    if (!dotEl) continue;
    const tool = tooling[toolKey];
    if (!tool) {
      dotEl.innerHTML = '';
      continue;
    }
    dotEl.innerHTML = `<span class="stat-dot ${tool.found ? 'ok' : 'bad'}"></span>`;
    dotEl.title = tool.found ? (tool.version || 'found') : 'not found at this path';
  }
}

document.getElementById('toggleOmdbKey').addEventListener('click', () => {
  const input = document.getElementById('OMDB_KEY');
  const btn = document.getElementById('toggleOmdbKey');
  const showing = input.type === 'text';
  input.type = showing ? 'password' : 'text';
  btn.textContent = showing ? 'Show' : 'Hide';
});

function collectFormValues() {
  const values = {};
  for (const el of settingsForm.elements) {
    if (!el.name) continue;
    if (el.type === 'checkbox') {
      values[el.name] = el.checked;
    } else if (el.type === 'number') {
      values[el.name] = el.value === '' ? el.value : Number(el.value);
    } else {
      values[el.name] = el.value;
    }
  }
  return values;
}

function clearFieldErrors() {
  settingsForm.querySelectorAll('.settings-field-error').forEach(el => el.remove());
  settingsForm.querySelectorAll('.field-invalid').forEach(el => el.classList.remove('field-invalid'));
}

function showFieldErrors(fieldErrors) {
  for (const [key, msg] of Object.entries(fieldErrors)) {
    const input = document.getElementById(key);
    if (!input) continue;
    input.classList.add('field-invalid');
    const err = document.createElement('p');
    err.className = 'settings-field-error';
    err.textContent = msg;
    input.closest('.settings-field').appendChild(err);
  }
}

settingsForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  clearFieldErrors();
  settingsMessage.textContent = '';
  settingsMessage.className = 'settings-message';
  settingsSaveBtn.disabled = true;
  settingsSaveBtn.textContent = 'Saving…';

  try {
    const res = await fetch('/settings/api', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(collectFormValues()),
    });
    const data = await res.json();

    if (!res.ok) {
      if (data.field_errors) showFieldErrors(data.field_errors);
      throw new Error(data.error || 'Save failed');
    }

    settingsMessage.textContent = data.requires_restart && data.requires_restart.length
      ? `Saved. Restart runui.py for ${data.requires_restart.join(', ')} to take effect.`
      : (data.saved && data.saved.length ? 'Saved — changes are already live.' : 'No changes to save.');
    settingsMessage.classList.add('ok');

    // Refresh tool-status dots in case a path was just fixed
    const systemRes = await fetch('/api/system');
    const systemData = await systemRes.json();
    renderToolStatus(systemData.tooling || {});
  } catch (e) {
    settingsMessage.textContent = e.message;
    settingsMessage.classList.add('error');
  } finally {
    settingsSaveBtn.disabled = false;
    settingsSaveBtn.textContent = 'Save changes';
  }
});

loadSettings();
