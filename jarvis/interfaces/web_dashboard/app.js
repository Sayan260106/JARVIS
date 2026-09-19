// JARVIS Web HUD Client Application

async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) return;
    const data = await res.json();
    renderState(data);
  } catch (err) {
    console.debug('Status poll error:', err);
  }
}

function renderState(data) {
  // 1. Header & Agent State
  document.getElementById('sys-status-text').textContent = `SYSTEM STATUS: ${data.system_status}`;
  document.getElementById('agent-state').textContent = data.agent_state;
  document.getElementById('speech-quote').textContent = data.speech_quote;

  // 2. Active Task
  const task = data.active_task;
  document.getElementById('task-name').textContent = task.name;
  document.getElementById('task-step').textContent = task.step_label;
  document.getElementById('progress-bar').style.width = `${task.progress_pct}%`;
  document.getElementById('progress-pct').textContent = `${task.progress_pct}% Completed`;

  // 2b. Task Step Checklist
  const checklistEl = document.getElementById('step-checklist');
  if (checklistEl && data.task_steps) {
    checklistEl.innerHTML = '';
    data.task_steps.forEach(step => {
      const row = document.createElement('div');
      row.className = `step-row step-${step.status.toLowerCase()}`;
      row.innerHTML = `<span class="step-icon">${step.icon}</span><span class="step-label">${escapeHTML(step.label)}</span>`;
      checklistEl.appendChild(row);
    });
  }

  // 3. System Telemetry
  const metrics = data.system_metrics;
  document.getElementById('cpu-val').textContent = `${metrics.cpu}%`;
  document.getElementById('cpu-bar').style.width = `${metrics.cpu}%`;
  document.getElementById('ram-val').textContent = `${metrics.ram}%`;
  document.getElementById('ram-bar').style.width = `${metrics.ram}%`;
  document.getElementById('ollama-status').textContent = metrics.ollama;
  document.getElementById('browser-status').textContent = metrics.browser;
  document.getElementById('network-status').textContent = metrics.network;

  // 4. Conversation Stream
  const stream = document.getElementById('messages-stream');
  stream.innerHTML = '';
  data.messages.forEach(msg => {
    const div = document.createElement('div');
    div.className = `msg ${msg.sender.toLowerCase() === 'you' ? 'user-msg' : 'jarvis-msg'}`;
    div.innerHTML = `<span class="sender-tag">${msg.sender}:</span><span class="msg-content">${escapeHTML(msg.text)}</span>`;
    stream.appendChild(div);
  });
  stream.scrollTop = stream.scrollHeight;

  // 5. Footer Telemetry
  const footerEl = document.getElementById('footer-telemetry');
  if (footerEl) {
    const tasks = data.active_task_count || 1;
    const ollamaIcon = metrics.ollama && metrics.ollama.includes('ONLINE') ? '●' : '○';
    footerEl.textContent = `CPU ${metrics.cpu}% │ RAM ${metrics.ram}% │ Tasks ${tasks} │ Ollama ${ollamaIcon}`;
  }
}

function escapeHTML(str) {
  return str.replace(/[&<>'"]/g, tag => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;'
  }[tag] || tag));
}

// Handle message submission
document.getElementById('chat-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const input = document.getElementById('user-input');
  const text = input.value.trim();
  if (!text) return;

  input.value = '';
  document.getElementById('agent-state').textContent = 'THINKING...';
  document.getElementById('speech-quote').textContent = '"Analyzing request..."';

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    });
    const data = await res.json();
    renderState(data);
  } catch (err) {
    console.error('Chat transmit error:', err);
  }
});

// Periodic polling every 1.5 seconds
fetchStatus();
setInterval(fetchStatus, 1500);
