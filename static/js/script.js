document.addEventListener('DOMContentLoaded', () => {
    
    // --- ROUTING (Single Page App) ---
    const navItems = document.querySelectorAll('.nav-item');
    const views = document.querySelectorAll('.view');
    
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            // Update actives
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');
            
            // Switch view
            const targetId = item.getAttribute('data-target');
            views.forEach(v => {
                if(v.id === targetId) {
                    v.classList.add('active-view');
                    v.classList.remove('hidden-view');
                } else {
                    v.classList.remove('active-view');
                    v.classList.add('hidden-view');
                }
            });

            // If switching to KB View, trigger a refresh of data
            if (targetId === 'kb-view') fetchDashboardStats();
        });
    });

    // --- KNOWLEDGE BASE / DASHBOARD ---
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const uploadProgress = document.getElementById('upload-progress');
    const clearDbBtn = document.getElementById('clear-db-btn');

    async function fetchDashboardStats() {
        try {
            const res = await fetch('/api/stats');
            const data = await res.json();
            
            document.getElementById('stat-vectors').innerText = data.total_vectors;
            document.getElementById('stat-files').innerText = data.files.length;

            const tbody = document.getElementById('db-table-body');
            tbody.innerHTML = '';

            if(data.files.length === 0) {
                tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding:2rem; color:var(--text-secondary);">No documents ingested yet.</td></tr>`;
                return;
            }

            data.files.forEach(f => {
                const tr = document.createElement('tr');
                const sizeKB = (f.size / 1024).toFixed(1) + ' KB';
                tr.innerHTML = `
                    <td>${escapeHTML(f.name)}</td>
                    <td><span class="type-badge">${f.type}</span></td>
                    <td>${sizeKB}</td>
                    <td><span style="color:var(--success)"><i class="fa-solid fa-check-circle"></i> Indexed</span></td>
                `;
                tbody.appendChild(tr);
            });
        } catch (e) {
            console.error('Failed to load stats', e);
        }
    }

    // Call on load
    fetchDashboardStats();

    /* File Drag & Drop */
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(e => dropZone.addEventListener(e, prev, false));
    function prev(e) { e.preventDefault(); e.stopPropagation(); }

    ['dragenter', 'dragover'].forEach(e => dropZone.addEventListener(e, () => dropZone.classList.add('dragover'), false));
    ['dragleave', 'drop'].forEach(e => dropZone.addEventListener(e, () => dropZone.classList.remove('dragover'), false));

    dropZone.addEventListener('drop', (e) => {
        if(e.dataTransfer.files.length > 0) handleFileUpload(e.dataTransfer.files[0]);
    });

    fileInput.addEventListener('change', () => {
        if(fileInput.files.length > 0) handleFileUpload(fileInput.files[0]);
    });

    async function handleFileUpload(file) {
        uploadProgress.classList.remove('hidden');
        
        const formData = new FormData();
        formData.append('file', file);
        try {
            const res = await fetch('/upload', { method: 'POST', body: formData });
            if(res.ok) {
                await fetchDashboardStats();
            } else {
                alert("Upload failed.");
            }
        } catch (e) {
            alert("Error: " + e);
        } finally {
            uploadProgress.classList.add('hidden');
            fileInput.value = '';
        }
    }

    /* Clear DB */
    clearDbBtn.addEventListener('click', async () => {
        if(!confirm('DANGER: Wipe entire vector store?')) return;
        try {
            await fetch('/clear', {method: 'POST'});
            fetchDashboardStats();
        } catch (e) {
            console.error(e);
        }
    });


    // --- CHAT INTERFACE ---
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');
    const sendBtn = document.getElementById('send-btn');

    chatInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight < 150 ? this.scrollHeight : 150) + 'px';
    });

    chatInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const userInput = chatInput.value.trim();
        if (!userInput) return;

        chatInput.value = '';
        chatInput.style.height = 'auto';
        sendBtn.disabled = true;

        addUserMessage(userInput);
        const msgId = addStreamingAIMessage();
        let accumulatedText = "";

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: userInput, session_id: "default_session" })
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let done = false;
            let buffer = "";

            while (!done) {
                const { value, done: readerDone } = await reader.read();
                done = readerDone;
                if (value) {
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop(); 
                    
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const parsed = JSON.parse(line.substring(6));
                                if (parsed.type === 'thought') {
                                    appendThought(msgId, parsed.data);
                                } else if (parsed.type === 'chunk') {
                                    accumulatedText += parsed.data;
                                    updateMessageHTML(msgId, accumulatedText);
                                }
                            } catch (e) {}
                        }
                    }
                }
            }
        } catch (error) {
            updateMessageHTML(msgId, "Error connecting to AI Server.");
        } finally {
            sendBtn.disabled = false;
            chatInput.focus();
        }
    });

    function addUserMessage(text) {
        const div = document.createElement('div');
        div.className = 'message user-message';
        div.innerHTML = `<div class="message-bubble">${escapeHTML(text)}</div>`;
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function addStreamingAIMessage() {
        const id = 'ai-' + Date.now();
        const div = document.createElement('div');
        div.className = 'message ai-message';
        div.id = id;
        div.innerHTML = `<div class="message-bubble"><div class="spinner"></div></div>`;
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return id;
    }

    function appendThought(id, thought) {
        const el = document.getElementById(id);
        if (!el) return;
        
        // Remove spinner if exists
        const spinner = el.querySelector('.spinner');
        if (spinner) spinner.remove();

        const thoughtId = id + '-thought';
        let container = document.getElementById(thoughtId);
        if (!container) {
            container = document.createElement('div');
            container.id = thoughtId;
            container.className = 'agent-thought';
            el.querySelector('.message-bubble').prepend(container);
        }
        
        container.innerHTML += `<div class="thought-line"><i class="fa-solid fa-bolt"></i> ${escapeHTML(thought)}</div>`;
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function updateMessageHTML(id, text) {
        const el = document.getElementById(id);
        if(!el) return;

        // Remove spinner if exists
        const spinner = el.querySelector('.spinner');
        if (spinner) spinner.remove();

        let targetContent = el.querySelector('.content-body');
        if(!targetContent) {
            targetContent = document.createElement('div');
            targetContent.className = 'content-body';
            el.querySelector('.message-bubble').appendChild(targetContent);
        }

        targetContent.innerHTML = typeof marked !== 'undefined' ? marked.parse(text) : escapeHTML(text);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function escapeHTML(str) {
        return str.replace(/[&<>'"]/g, tag => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'}[tag] || tag));
    }
});
