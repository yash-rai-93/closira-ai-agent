const API_BASE = '';

let currentSessionId = localStorage.getItem('closira_session_id') || null;

// UI Elements
const chatContainer = document.getElementById('chat-container');
const chatInput = document.getElementById('chat-input');
const btnSend = document.getElementById('btn-send');
const btnNewSession = document.getElementById('btn-new-session');
const btnReset = document.getElementById('btn-reset');
const btnSummary = document.getElementById('btn-summary');
const leadDataJson = document.getElementById('lead-data-json');
const stageBadge = document.getElementById('stage-badge');
const sessionStatusText = document.getElementById('session-status-text');
const summaryModal = document.getElementById('summary-modal');
const summaryJsonContent = document.getElementById('summary-json-content');
const btnCloseModal = document.getElementById('btn-close-modal');

// Init
async function init() {
    if (currentSessionId) {
        await fetchSessionState();
    } else {
        sessionStatusText.textContent = 'Disconnected • No active session';
    }
}

// Fetch session state
async function fetchSessionState() {
    try {
        const res = await fetch(`${API_BASE}/session/${currentSessionId}`);
        if (!res.ok) {
            if (res.status === 404) {
                // Session expired or deleted on server
                currentSessionId = null;
                localStorage.removeItem('closira_session_id');
                sessionStatusText.textContent = 'Disconnected • Session expired';
                return;
            }
            throw new Error('Failed to fetch session');
        }
        const data = await res.json();
        updateUI(data);
    } catch (err) {
        console.error(err);
        sessionStatusText.textContent = `Error • ${err.message}`;
    }
}

// Update UI based on session data
function updateUI(data) {
    sessionStatusText.textContent = `Connected • Session: ${data.session_id.substring(0, 8)}...`;
    stageBadge.innerHTML = `<span class="dot-small"></span> [${data.current_stage.toUpperCase()}]`;
    
    // Update Lead Data Payload
    const payload = {
        session_id: data.session_id,
        intent: data.current_stage === 'lead_qualification' ? 'booking_inquiry' : 'pending',
        service: data.lead_data?.interested_service || 'pending',
        consultation: data.lead_data?.wants_consultation || false,
        urgency: data.is_escalated ? 'high' : 'low'
    };
    leadDataJson.textContent = JSON.stringify(payload, null, 2);

    if (data.is_escalated) {
        appendHandoffTag(`ESCALATED: ${data.escalation_reason}`);
        chatInput.disabled = true;
        chatInput.placeholder = "Session locked due to escalation.";
        btnSend.disabled = true;
    }
}

// Send Message
async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    // Append user message
    appendUserMessage(text);
    chatInput.value = '';

    // Optimistic ID creation if new
    const sessionIdToUse = currentSessionId || crypto.randomUUID();

    try {
        const res = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: sessionIdToUse,
                message: text
            })
        });

        if (!res.ok) throw new Error('API Error');

        const data = await res.json();
        
        // Save session id if it was new
        if (!currentSessionId) {
            currentSessionId = data.session_id;
            localStorage.setItem('closira_session_id', currentSessionId);
        }

        // Append agent message
        appendAgentMessage(data.response);

        // Fetch latest state to update matrix & payload
        await fetchSessionState();

    } catch (err) {
        console.error(err);
        appendHandoffTag("System Error: Could not reach backend.");
    }
}

// UI Append Helpers
function appendUserMessage(text) {
    const div = document.createElement('div');
    div.className = 'chat-bubble user';
    div.textContent = text;
    chatContainer.appendChild(div);
    scrollToBottom();
}

function appendAgentMessage(text) {
    const div = document.createElement('div');
    div.className = 'chat-bubble agent';
    div.innerHTML = `
        <div class="agent-icon"><i class="ph-fill ph-sparkle"></i></div>
        <div class="agent-text">${escapeHtml(text)}</div>
    `;
    chatContainer.appendChild(div);
    scrollToBottom();
}

function appendHandoffTag(text) {
    const div = document.createElement('div');
    div.className = 'handoff-tag';
    div.innerHTML = `<i class="ph ph-check-circle"></i> ${text}`;
    chatContainer.appendChild(div);
    scrollToBottom();
}

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function escapeHtml(unsafe) {
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

// Actions
btnSend.addEventListener('click', sendMessage);
chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

btnNewSession.addEventListener('click', () => {
    currentSessionId = null;
    localStorage.removeItem('closira_session_id');
    chatContainer.innerHTML = `<div class="timestamp"><span>${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span></div>`;
    chatInput.disabled = false;
    chatInput.placeholder = "Type a message or command to intercept...";
    btnSend.disabled = false;
    leadDataJson.textContent = '{\n  "status": "Ready for new session"\n}';
    sessionStatusText.textContent = 'Disconnected • No active session';
    stageBadge.innerHTML = `<span class="dot-small"></span> [FAQ]`;
});

btnReset.addEventListener('click', async () => {
    if (!currentSessionId) return;
    try {
        await fetch(`${API_BASE}/session/${currentSessionId}`, { method: 'DELETE' });
    } catch(e) {}
    btnNewSession.click();
});

btnSummary.addEventListener('click', async () => {
    if (!currentSessionId) {
        alert('No active session to summarize.');
        return;
    }
    btnSummary.textContent = "Generating...";
    try {
        const res = await fetch(`${API_BASE}/summary`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: currentSessionId })
        });
        if (!res.ok) throw new Error('Failed to generate summary');
        const data = await res.json();
        
        summaryJsonContent.textContent = JSON.stringify(data, null, 2);
        summaryModal.classList.add('active');
    } catch(e) {
        alert(e.message);
    } finally {
        btnSummary.innerHTML = `<i class="ph ph-file-text"></i> Generate CRM Summary`;
    }
});

btnCloseModal.addEventListener('click', () => {
    summaryModal.classList.remove('active');
});

// Run Init
init();
