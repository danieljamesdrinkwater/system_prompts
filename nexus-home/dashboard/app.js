// Nexus Home Dashboard

const API_KEY = localStorage.getItem('nexus_api_key') || prompt('Enter API Key:');
if (API_KEY) localStorage.setItem('nexus_api_key', API_KEY);

const API = {
    async fetch(path, opts = {}) {
        const resp = await fetch(`/api${path}`, {
            ...opts,
            headers: {
                'X-API-Key': API_KEY,
                'Content-Type': 'application/json',
                ...opts.headers,
            },
        });
        if (!resp.ok) throw new Error(`API error: ${resp.status}`);
        return resp.json();
    },
    get: (path) => API.fetch(path),
    post: (path, body) => API.fetch(path, { method: 'POST', body: JSON.stringify(body) }),
    del: (path) => API.fetch(path, { method: 'DELETE' }),
};

// --- Navigation ---
document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.section).classList.add('active');
        loadSection(btn.dataset.section);
    });
});

function loadSection(section) {
    const loaders = {
        devices: loadDevices,
        cameras: loadCameras,
        automation: loadAutomation,
        energy: loadEnergy,
        storage: loadStorage,
        calendar: loadCalendar,
        mail: loadMail,
        calls: loadCalls,
    };
    if (loaders[section]) loaders[section]();
}

// --- WebSocket ---
let ws = null;
function connectWS() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${proto}//${location.host}/ws?api_key=${API_KEY}`);
    ws.onopen = () => {
        document.getElementById('ws-status').className = 'status-dot online';
    };
    ws.onclose = () => {
        document.getElementById('ws-status').className = 'status-dot offline';
        setTimeout(connectWS, 3000);
    };
    ws.onmessage = (e) => {
        const event = JSON.parse(e.data);
        handleEvent(event);
    };
}

function handleEvent(event) {
    if (event.type === 'device_state') loadDevices();
    if (event.type === 'camera_event') loadCameras();
    if (event.type === 'notification') showNotification(event);
}

function showNotification(event) {
    if (Notification.permission === 'granted') {
        new Notification('Nexus Home', { body: event.body || event.label || 'New event' });
    }
}

// --- Devices ---
async function loadDevices() {
    try {
        const devices = await API.get('/devices/');
        const grid = document.getElementById('device-grid');
        grid.innerHTML = devices.map(d => `
            <div class="card">
                <div class="card-title">${d.name}</div>
                <div class="card-meta">${d.room || 'No room'} &middot; ${d.type} &middot; ${d.protocol}</div>
                <div class="card-state">
                    <span>${d.state ? JSON.stringify(d.state).slice(0, 30) : 'Unknown'}</span>
                    <div class="toggle ${d.state?.on ? 'on' : ''}"
                         onclick="toggleDevice('${d.id}', ${!d.state?.on})"></div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error('Load devices failed:', e);
    }
}

async function toggleDevice(id, state) {
    await API.post(`/devices/${id}/command`, { command: { on: state } });
}

async function discoverDevices() {
    const found = await API.get('/devices/discover/');
    alert(`Found ${found.length} device(s)`);
    loadDevices();
}

// --- Cameras ---
async function loadCameras() {
    try {
        const cameras = await API.get('/cameras/');
        const grid = document.getElementById('camera-grid');
        grid.innerHTML = cameras.map(c => `
            <div class="card">
                <div class="card-title">${c.name}</div>
                <div class="card-meta">${c.type} ${c.active ? '(Live)' : '(Offline)'}</div>
                ${c.active ? `<img src="/api/cameras/${c.id}/snapshot?api_key=${API_KEY}"
                    style="width:100%;margin-top:0.5rem;border-radius:4px"
                    onerror="this.style.display='none'">` : ''}
                <div class="card-state">
                    <button class="btn" onclick="${c.active ? `stopCam('${c.id}')` : `startCam('${c.id}')`}">
                        ${c.active ? 'Stop' : 'Start'}
                    </button>
                </div>
            </div>
        `).join('') || '<p style="color:var(--text-dim)">No cameras configured</p>';
    } catch (e) {
        console.error('Load cameras failed:', e);
    }
}

async function startCam(id) { await API.post(`/cameras/${id}/start`); loadCameras(); }
async function stopCam(id) { await API.post(`/cameras/${id}/stop`); loadCameras(); }
async function discoverCameras() {
    const found = await API.post('/cameras/discover');
    alert(`Found ${found.length} ONVIF camera(s)`);
}

// --- Automation ---
async function loadAutomation() {
    try {
        const rules = await API.get('/automation/rules');
        document.getElementById('rules-list').innerHTML = rules.map(r => `
            <div class="list-item">
                <div>
                    <strong>${r.name}</strong>
                    <span style="color:var(--text-dim);margin-left:0.5rem">${r.trigger_type}</span>
                </div>
                <span style="color:${r.enabled ? 'var(--success)' : 'var(--text-dim)'}">
                    ${r.enabled ? 'Active' : 'Disabled'}
                </span>
            </div>
        `).join('') || '<p style="color:var(--text-dim)">No rules configured</p>';

        const scenes = await API.get('/automation/scenes');
        document.getElementById('scenes-list').innerHTML = scenes.map(s => `
            <div class="card" onclick="activateScene('${s.id}')" style="cursor:pointer">
                <div class="card-title">${s.name}</div>
                <div class="card-meta">${(s.actions || []).length} action(s)</div>
            </div>
        `).join('');
    } catch (e) {
        console.error('Load automation failed:', e);
    }
}

async function activateScene(id) { await API.post(`/automation/scenes/${id}/activate`); }
function showAddRule() { alert('Rule editor coming soon — use the API for now: POST /api/automation/rules'); }

// --- Energy ---
async function loadEnergy() {
    try {
        const hours = document.getElementById('energy-range').value;
        const summary = await API.get(`/energy/summary?hours=${hours}`);
        document.getElementById('energy-summary').innerHTML = `
            <div class="summary-card"><div class="value">${summary.total_kwh}</div><div class="label">kWh Total</div></div>
            <div class="summary-card"><div class="value">${summary.peak_watts}</div><div class="label">Peak Watts</div></div>
            <div class="summary-card"><div class="value">${summary.readings_count}</div><div class="label">Readings</div></div>
        `;
        document.getElementById('energy-chart').textContent =
            summary.device_breakdown.length
                ? summary.device_breakdown.map(d => `${d.device_id}: avg ${Math.round(d.avg_watts)}W`).join(' | ')
                : 'No energy data yet';
    } catch (e) {
        console.error('Load energy failed:', e);
    }
}

// --- Storage ---
let currentPath = '';
async function loadStorage() {
    try {
        const disks = await API.get('/storage/disks');
        document.getElementById('disk-info').innerHTML = disks
            .filter(d => d.mountpoint)
            .map(d => `
                <div class="summary-card">
                    <div class="value">${d.size || '?'}</div>
                    <div class="label">${d.name} (${d.fstype || '?'}) ${d.use_percent || ''}</div>
                </div>
            `).join('');
        loadFiles();
    } catch (e) {
        document.getElementById('disk-info').innerHTML = '';
        loadFiles();
    }
}

async function loadFiles() {
    try {
        const files = await API.get(`/storage/files?path=${encodeURIComponent(currentPath)}`);
        document.getElementById('current-path').textContent = '/' + currentPath;
        document.getElementById('file-list').innerHTML = files.map(f => `
            <div class="list-item" ${f.type === 'directory' ? `onclick="navigateTo('${f.path}')" style="cursor:pointer"` : ''}>
                <span>${f.type === 'directory' ? '📁' : '📄'} ${f.name}</span>
                <span style="color:var(--text-dim)">${f.type === 'file' ? formatSize(f.size) : ''}</span>
            </div>
        `).join('') || '<p style="color:var(--text-dim)">Empty directory</p>';
    } catch (e) {
        console.error('Load files failed:', e);
    }
}

function navigateTo(path) { currentPath = path; loadFiles(); }
function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
    return (bytes / 1073741824).toFixed(1) + ' GB';
}
async function autoMount() {
    const result = await API.post('/storage/auto-mount');
    alert(`Mounted ${result.mounted.length} drive(s)`);
    loadStorage();
}
async function uploadFile() {
    const input = document.getElementById('file-upload');
    if (!input.files.length) return;
    const formData = new FormData();
    formData.append('file', input.files[0]);
    await fetch(`/api/storage/files/upload?path=${encodeURIComponent(currentPath)}`, {
        method: 'POST',
        headers: { 'X-API-Key': API_KEY },
        body: formData,
    });
    loadFiles();
}

// --- Calendar ---
async function loadCalendar() {
    try {
        const events = await API.get('/calendar/events?days_ahead=30');
        document.getElementById('events-list').innerHTML = events.map(e => `
            <div class="list-item">
                <div>
                    <strong>${e.title}</strong>
                    <div style="color:var(--text-dim);font-size:0.8rem">
                        ${new Date(e.start_time).toLocaleString()} ${e.location ? '@ ' + e.location : ''}
                    </div>
                </div>
                <span class="badge" style="background:var(--accent)">${e.source}</span>
            </div>
        `).join('') || '<p style="color:var(--text-dim)">No upcoming events</p>';
    } catch (e) {
        console.error('Load calendar failed:', e);
    }
}
async function syncCalendar() { await API.post('/calendar/sync'); loadCalendar(); }

// --- Mail ---
async function loadMail() {
    try {
        const [messages, unread] = await Promise.all([
            API.get('/mail/inbox?limit=30'),
            API.get('/mail/unread'),
        ]);
        const badge = document.getElementById('unread-badge');
        if (unread.unread > 0) {
            badge.textContent = unread.unread;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
        document.getElementById('mail-list').innerHTML = messages.map(m => `
            <div class="list-item" style="${m.is_read ? '' : 'border-left:3px solid var(--accent)'}">
                <div>
                    <strong>${m.subject || '(no subject)'}</strong>
                    <div style="color:var(--text-dim);font-size:0.8rem">${m.from_addr || ''}</div>
                    <div style="color:var(--text-dim);font-size:0.75rem">${(m.body_preview || '').slice(0, 80)}</div>
                </div>
                <span style="color:var(--text-dim);font-size:0.75rem">${m.received_at || ''}</span>
            </div>
        `).join('') || '<p style="color:var(--text-dim)">No messages</p>';
    } catch (e) {
        console.error('Load mail failed:', e);
    }
}
async function syncMail() { await API.post('/mail/sync'); loadMail(); }

// --- Calls ---
async function loadCalls() {
    try {
        const [status, history] = await Promise.all([
            API.get('/telephony/status'),
            API.get('/telephony/history'),
        ]);
        document.getElementById('sip-status').innerHTML =
            `SIP: <span style="color:${status.registered ? 'var(--success)' : 'var(--danger)'}">
            ${status.registered ? 'Registered' : 'Not registered'}</span>`;
        document.getElementById('call-history').innerHTML = history.map(c => `
            <div class="list-item">
                <div>
                    <strong>${c.remote_number || 'Unknown'}</strong>
                    <span style="color:var(--text-dim);margin-left:0.5rem">${c.direction}</span>
                </div>
                <span style="color:var(--text-dim)">${c.status} ${c.duration_seconds ? c.duration_seconds + 's' : ''}</span>
            </div>
        `).join('') || '<p style="color:var(--text-dim)">No call history</p>';
    } catch (e) {
        console.error('Load calls failed:', e);
    }
}

async function dialNumber() {
    const number = document.getElementById('dial-number').value.trim();
    if (!number) return;
    await API.post('/telephony/dial', { number });
    loadCalls();
}
async function hangUp() { await API.post('/telephony/hangup'); loadCalls(); }

// --- AI Chat ---
async function sendChat() {
    const input = document.getElementById('chat-input');
    const msg = input.value.trim();
    if (!msg) return;
    input.value = '';

    const area = document.getElementById('chat-messages');
    area.innerHTML += `<div class="chat-msg user">${msg}</div>`;
    area.scrollTop = area.scrollHeight;

    try {
        const resp = await API.post('/ai/command', { message: msg });
        area.innerHTML += `<div class="chat-msg ai">${resp.response}${resp.executed ? '<br><small style="color:var(--success)">Command executed</small>' : ''}</div>`;
    } catch (e) {
        area.innerHTML += `<div class="chat-msg ai" style="color:var(--danger)">Error: ${e.message}</div>`;
    }
    area.scrollTop = area.scrollHeight;
}

async function voiceCommand() {
    // Simple microphone recording using MediaRecorder API
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const recorder = new MediaRecorder(stream);
        const chunks = [];

        recorder.ondataavailable = (e) => chunks.push(e.data);
        recorder.onstop = async () => {
            stream.getTracks().forEach(t => t.stop());
            const blob = new Blob(chunks, { type: 'audio/webm' });
            const formData = new FormData();
            formData.append('file', blob, 'recording.webm');

            const resp = await fetch('/api/voice/transcribe', {
                method: 'POST',
                headers: { 'X-API-Key': API_KEY },
                body: formData,
            });
            const result = await resp.json();
            if (result.text) {
                document.getElementById('chat-input').value = result.text;
                sendChat();
            }
        };

        recorder.start();
        setTimeout(() => recorder.stop(), 5000); // 5 second recording
        alert('Recording for 5 seconds...');
    } catch (e) {
        alert('Microphone access denied');
    }
}

// --- Init ---
if (Notification.permission === 'default') Notification.requestPermission();
connectWS();
loadDevices();
