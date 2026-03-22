let currentConversationId = null;
let isGenerating = false;
let eventSource = null;
let currentImages = [];
let streamingContent = '';
let currentConfig = { 
    max_context_turns: 5,
    speech_recognition_lang: 'zh-CN',
    speech_synthesis_lang: 'zh-CN',
    max_recording_time: 30
};

let currentModel = 'qwen3.5:9b';

let recognition = null;
let isRecording = false;
let isTakingScreenshot = false;
let recordingTimer = null;
let maxRecordingTime = 30;

let synth = window.speechSynthesis;
let ttsEnabled = false;
let isSpeaking = false;
let currentUtterance = null;
let ttsVoice = null;

function init() {
    loadConversations();
    loadConfig();
    initSpeechRecognition();
    initTTS();
    startStatusPolling();
    document.addEventListener('keydown', handleGlobalKeydown);
    initDragAndDrop();
}

function handleGlobalKeydown(event) {
    if (event.altKey && event.key === 'a') {
        event.preventDefault();
        takeScreenshot();
    }
}

function startStatusPolling() {
    setInterval(() => {
        fetch('/api/status')
            .then(response => response.json())
            .then(data => {
                const isGenerating = data.is_generating;
                const sendBtn = document.getElementById('sendBtn');
                const stopBtn = document.getElementById('stopBtn');
                const messageInput = document.getElementById('messageInput');
                const statusText = document.getElementById('statusText');
                
                if (sendBtn && stopBtn && messageInput) {
                    sendBtn.disabled = isGenerating;
                    stopBtn.disabled = !isGenerating;
                    messageInput.disabled = isGenerating;
                }
                if (statusText) {
                    statusText.textContent = isGenerating ? '生成中...' : '就绪';
                }
            })
            .catch(error => console.error('获取状态失败:', error));
    }, 500);
}

function checkSpeechSupport() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        alert('您的浏览器不支持语音识别功能，请使用 Chrome 或 Edge 浏览器');
        document.getElementById('voiceBtn').style.display = 'none';
        return false;
    }
    return true;
}

function initSpeechRecognition() {
    if (!checkSpeechSupport()) {
        return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'zh-CN';

    recognition.onstart = function() {
        isRecording = true;
        document.getElementById('voiceBtn').classList.add('recording');
        document.getElementById('voiceIcon').textContent = '⏹️';
        document.getElementById('voiceBtnText').textContent = '停止录音';
        document.getElementById('messageInput').disabled = true;
        document.getElementById('sendBtn').disabled = true;

        recordingTimer = setTimeout(() => {
            stopRecording();
            alert(`录音时间已达到${maxRecordingTime}秒限制`);
        }, maxRecordingTime * 1000);
    };

    recognition.onresult = function(event) {
        const transcript = event.results[0][0].transcript;
        const messageInput = document.getElementById('messageInput');
        messageInput.value = transcript;
    };

    recognition.onerror = function(event) {
        console.error('语音识别错误:', event.error);
        let errorMessage = '语音识别失败';
        
        switch(event.error) {
            case 'no-speech':
                errorMessage = '未检测到语音，请重试';
                break;
            case 'audio-capture':
                errorMessage = '无法访问麦克风，请检查权限设置';
                break;
            case 'not-allowed':
                errorMessage = '麦克风权限被拒绝，请在浏览器设置中允许';
                break;
            case 'network':
                errorMessage = '网络连接失败，请检查网络或使用离线模式';
                break;
            default:
                errorMessage = `语音识别错误: ${event.error}`;
        }
        
        alert(errorMessage);
        resetVoiceUI();
    };

    recognition.onend = function() {
        if (isRecording) {
            resetVoiceUI();
        }
    };
}

function toggleVoiceRecognition() {
    if (!recognition) {
        initSpeechRecognition();
        if (!recognition) {
            return;
        }
    }

    if (isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
}

function startRecording() {
    try {
        recognition.start();
    } catch (error) {
        console.error('启动录音失败:', error);
        alert('启动录音失败，请重试');
    }
}

function stopRecording() {
    if (recognition && isRecording) {
        recognition.stop();
    }
}

function resetVoiceUI() {
    isRecording = false;
    if (recordingTimer) {
        clearTimeout(recordingTimer);
        recordingTimer = null;
    }
    
    document.getElementById('voiceBtn').classList.remove('recording');
    document.getElementById('voiceIcon').textContent = '🎤';
    document.getElementById('voiceBtnText').textContent = '开始语音输入';
    document.getElementById('messageInput').disabled = isGenerating;
    document.getElementById('sendBtn').disabled = isGenerating;
}

function checkTTSSupport() {
    if (!('speechSynthesis' in window)) {
        alert('您的浏览器不支持语音合成功能，请使用 Chrome 或 Edge 浏览器');
        document.getElementById('ttsBtn').style.display = 'none';
        return false;
    }
    return true;
}

function initTTS() {
    if (!checkTTSSupport()) {
        return;
    }

    const voices = synth.getVoices();
    
    synth.onvoiceschanged = function() {
        const updatedVoices = synth.getVoices();
        selectBestVoice(updatedVoices, currentConfig.speech_synthesis_lang || 'zh-CN');
    };

    selectBestVoice(voices, currentConfig.speech_synthesis_lang || 'zh-CN');
}

function toggleTTS() {
    if (isSpeaking) {
        stopSpeaking();
    } else {
        startSpeaking();
    }
}

function startSpeaking() {
    const messagesContainer = document.getElementById('messagesContainer');
    const lastAssistantMessage = messagesContainer.querySelector('.message.assistant:last-child');
    
    if (!lastAssistantMessage) {
        alert('没有可朗读的内容');
        return;
    }

    const content = lastAssistantMessage.querySelector('.content').textContent;
    if (!content || content.trim() === '') {
        alert('没有可朗读的内容');
        return;
    }

    synth.cancel();
    
    const utterance = new SpeechSynthesisUtterance(content);
    currentUtterance = utterance;

    if (ttsVoice) {
        utterance.voice = ttsVoice;
    }

    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;

    utterance.onstart = function() {
        isSpeaking = true;
        document.getElementById('ttsBtn').classList.add('active');
        document.getElementById('ttsIcon').textContent = '🔊';
        document.getElementById('ttsBtnText').textContent = '停止朗读';
    };

    utterance.onend = function() {
        isSpeaking = false;
        document.getElementById('ttsBtn').classList.remove('active');
        document.getElementById('ttsIcon').textContent = '🔇';
        document.getElementById('ttsBtnText').textContent = '语音朗读';
    };

    utterance.onerror = function(event) {
        console.error('语音合成错误:', event.error);
        isSpeaking = false;
        document.getElementById('ttsBtn').classList.remove('active');
        document.getElementById('ttsIcon').textContent = '🔇';
        document.getElementById('ttsBtnText').textContent = '语音朗读';
        
        if (event.error !== 'interrupted' && event.error !== 'canceled') {
            alert('语音朗读失败');
        }
    };

    synth.speak(utterance);
}

function stopSpeaking() {
    synth.cancel();
    isSpeaking = false;
    document.getElementById('ttsBtn').classList.remove('active');
    document.getElementById('ttsIcon').textContent = '🔇';
    document.getElementById('ttsBtnText').textContent = '语音朗读';
}

function loadConversations() {
    fetch('/api/conversations')
        .then(response => response.json())
        .then(data => {
            renderConversationList(data.conversations, data.current_id);
            if (data.current_id && !currentConversationId) {
                switchConversation(data.current_id);
            }
        })
        .catch(error => console.error('加载对话列表失败:', error));
}

function updateConversationList() {
    fetch('/api/conversations')
        .then(response => response.json())
        .then(data => {
            renderConversationList(data.conversations, data.current_id);
        })
        .catch(error => console.error('更新对话列表失败:', error));
}

function renderConversationList(conversations, currentId) {
    const list = document.getElementById('conversationList');
    list.innerHTML = '';

    conversations.forEach(conv => {
        const item = document.createElement('div');
        item.className = `conversation-item ${conv.id === currentId ? 'active' : ''}`;
        item.onclick = (e) => {
            if (!e.target.classList.contains('action-btn')) {
                switchConversation(conv.id);
            }
        };

        const date = new Date(conv.updated_at);
        const timeStr = date.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });

        item.innerHTML = `
            <div class="name">${conv.name}</div>
            <div class="meta">
                <span>${conv.message_count} 条消息</span>
                <span>${timeStr}</span>
            </div>
            <div class="actions">
                <button class="action-btn fork" onclick="forkConversationById('${conv.id}', event)">🔄</button>
                <button class="action-btn delete" onclick="deleteConversationById('${conv.id}', event)">🗑️</button>
            </div>
        `;

        list.appendChild(item);
    });
}

function switchConversation(conversationId) {
    fetch(`/api/conversations/${conversationId}/switch`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            currentConversationId = conversationId;
            document.getElementById('chatTitle').textContent = data.conversation.name;
            loadMessages(conversationId);
            loadConversations();
            updateDocumentInfo(data.conversation.document_file);
            updateImageInfo(data.conversation.images);
            updateModelForImages();
        })
        .catch(error => console.error('切换对话失败:', error));
}

function loadMessages(conversationId) {
    fetch(`/api/conversations/${conversationId}/messages`)
        .then(response => response.json())
        .then(data => {
            renderMessages(data.messages);
            updateDocumentInfo(data.document_file);
        })
        .catch(error => console.error('加载消息失败:', error));
}

function renderMessages(messages) {
    const container = document.getElementById('messagesContainer');
    container.innerHTML = '';

    messages.forEach(msg => {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${msg.role}`;
        
        let avatar = '🤖';
        if (msg.role === 'user') avatar = '👤';
        else if (msg.role === 'system') avatar = 'ℹ️';
        
        const date = new Date(msg.timestamp);
        const timeStr = date.toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' });

        let content = msg.content || '';
        if (msg.role === 'assistant') {
            content = marked.parse(content);
        } else if (msg.role === 'system') {
            content = `<span class="system-message">${escapeHtml(content)}</span>`;
        } else {
            content = escapeHtml(content);
        }

        messageDiv.innerHTML = `
            <div class="avatar">${avatar}</div>
            <div>
                <div class="content">${content}</div>
                <div class="timestamp">${timeStr}</div>
            </div>
        `;

        container.appendChild(messageDiv);
    });

    container.scrollTop = container.scrollHeight;
}

function createNewConversation() {
    fetch('/api/conversations', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            switchConversation(data.conversation.id);
            loadConversations();
        })
        .catch(error => console.error('创建对话失败:', error));
}

function forkConversation() {
    if (!currentConversationId) return;
    forkConversationById(currentConversationId);
}

function forkConversationById(conversationId, event) {
    if (event) event.stopPropagation();

    fetch(`/api/conversations/${conversationId}/fork`, { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            switchConversation(data.conversation.id);
            loadConversations();
        })
        .catch(error => console.error('Fork 对话失败:', error));
}

function deleteConversation() {
    if (!currentConversationId) return;
    deleteConversationById(currentConversationId);
}

function deleteConversationById(conversationId, event) {
    if (event) event.stopPropagation();

    if (!confirm('确定要删除这个对话吗？')) return;

    fetch(`/api/conversations/${conversationId}`, { method: 'DELETE' })
        .then(response => response.json())
        .then(data => {
            if (data.current_id) {
                switchConversation(data.current_id);
            }
            loadConversations();
        })
        .catch(error => console.error('删除对话失败:', error));
}

function sendMessage() {
    const input = document.getElementById('messageInput');
    const query = input.value.trim();

    if (!query) return;
    if (isGenerating) return;

    const container = document.getElementById('messagesContainer');
    
    const userMessage = document.createElement('div');
    userMessage.className = 'message user';
    const now = new Date();
    const timeStr = now.toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    
    userMessage.innerHTML = `
        <div class="avatar">👤</div>
        <div>
            <div class="content">${escapeHtml(query)}</div>
            <div class="timestamp">${timeStr}</div>
        </div>
    `;
    container.appendChild(userMessage);
    container.scrollTop = container.scrollHeight;

    fetch('/api/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            query, 
            model: currentModel,
            mode: document.getElementById('modeSelect').value
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (data.conversation_id && data.conversation_id !== currentConversationId) {
                    currentConversationId = data.conversation_id;
                    updateConversationList();
                }
                startStreaming();
            } else {
                alert(data.error);
            }
        })
        .catch(error => console.error('发送消息失败:', error));

    input.value = '';
    input.style.height = 'auto';
}

function startStreaming() {
    isGenerating = true;
    streamingContent = '';
    updateUIState();

    const container = document.getElementById('messagesContainer');
    
    const assistantMessage = document.createElement('div');
    assistantMessage.className = 'message assistant streaming';
    assistantMessage.id = 'streaming-message';
    const now = new Date();
    const timeStr = now.toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    assistantMessage.innerHTML = `
        <div class="avatar">🤖</div>
        <div>
            <div class="content"></div>
            <div class="timestamp">${timeStr}</div>
        </div>
    `;
    container.appendChild(assistantMessage);
    container.scrollTop = container.scrollHeight;

    eventSource = new EventSource('/api/stream');

    eventSource.onmessage = function(event) {
        const data = event.data;

        if (data.startsWith('[DONE]')) {
            stopStreaming();
            loadConversations();
            updateConversationTitle();
            if (currentConversationId) {
                loadMessages(currentConversationId);
            }
        } else if (data.startsWith('[ERROR]')) {
            const errorMsg = data.substring(7);
            alert(errorMsg);
            stopStreaming();
        } else if (data.startsWith('[chunk]')) {
            const content = data.substring(7);
            appendStreamingMessage(content);
        } else if (data.startsWith('[PROGRESS]')) {
            const progressMsg = data.substring(10);
            console.log('Progress:', progressMsg);
        }
    };

    eventSource.onerror = function(error) {
        console.error('流式响应错误:', error);
        stopStreaming();
    };
}

function stopStreaming() {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    
    const streamingMessage = document.getElementById('streaming-message');
    if (streamingMessage) {
        const contentDiv = streamingMessage.querySelector('.content');
        try {
            if (streamingContent) {
                contentDiv.innerHTML = marked.parse(streamingContent);
            }
        } catch (e) {
            console.error('Markdown渲染失败:', e);
            contentDiv.textContent = streamingContent;
        }
        streamingMessage.classList.remove('streaming');
        streamingMessage.removeAttribute('id');
    }
    
    isGenerating = false;
    updateUIState();
    
    setTimeout(() => {
        if (currentConversationId) {
            loadMessages(currentConversationId);
        }
    }, 100);
}

function appendStreamingMessage(content) {
    const streamingMessage = document.getElementById('streaming-message');
    if (!streamingMessage) return;

    streamingContent += content;
    
    const contentDiv = streamingMessage.querySelector('.content');
    contentDiv.textContent = streamingContent;

    const container = document.getElementById('messagesContainer');
    container.scrollTop = container.scrollHeight;
}


function stopGeneration() {
    fetch('/api/stop', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                document.getElementById('statusText').textContent = '正在停止...';
            }
        })
        .catch(error => console.error('停止生成失败:', error));
}

function updateUIState() {
    const sendBtn = document.getElementById('sendBtn');
    const stopBtn = document.getElementById('stopBtn');
    const messageInput = document.getElementById('messageInput');
    const voiceBtn = document.getElementById('voiceBtn');
    const statusText = document.getElementById('statusText');

    sendBtn.disabled = isGenerating;
    stopBtn.disabled = !isGenerating;
    messageInput.disabled = isGenerating;
    voiceBtn.disabled = isGenerating;
    statusText.textContent = isGenerating ? '生成中...' : '就绪';
}

function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function uploadFile(event) {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    
    const filename = file.name;

    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const progressFill = document.getElementById('progressFill');
    const uploadBtn = document.getElementById('uploadBtn');
    
    progressBar.classList.remove('hidden');
    progressText.textContent = '正在上传文档...';
    progressFill.style.width = '10%';
    uploadBtn.disabled = true;

    fetch('/api/documents/upload', {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                startDocumentProcessing(progressBar, progressText, progressFill, uploadBtn, filename);
            } else {
                progressBar.classList.add('hidden');
                uploadBtn.disabled = false;
                alert(data.error);
            }
        })
        .catch(error => {
            console.error('上传文件失败:', error);
            progressBar.classList.add('hidden');
            uploadBtn.disabled = false;
            alert('上传文件失败');
        });

    event.target.value = '';
}

function startDocumentProcessing(progressBar, progressText, progressFill, uploadBtn, filename) {
    const eventSource = new EventSource('/api/stream');
    let streamingContent = '';
    let streamingMessageElement = null;
    let userMessageElement = null;
    
    function showUserMessage() {
        if (!userMessageElement) {
            const container = document.getElementById('messagesContainer');
            userMessageElement = document.createElement('div');
            userMessageElement.className = 'message user';
            userMessageElement.innerHTML = `
                <div class="avatar">👤</div>
                <div class="content">${escapeHtml(`上传文档《${filename}》，请总结`)}</div>
            `;
            container.appendChild(userMessageElement);
            container.scrollTop = container.scrollHeight;
        }
    }
    
    function appendChunk(text) {
        showUserMessage();
        if (!streamingMessageElement) {
            const container = document.getElementById('messagesContainer');
            streamingMessageElement = document.createElement('div');
            streamingMessageElement.className = 'message assistant streaming';
            streamingMessageElement.innerHTML = `
                <div class="avatar">🤖</div>
                <div class="content"></div>
            `;
            container.appendChild(streamingMessageElement);
        }
        streamingContent += text;
        const contentDiv = streamingMessageElement.querySelector('.content');
        try {
            contentDiv.innerHTML = marked.parse(streamingContent);
        } catch (e) {
            contentDiv.textContent = streamingContent;
        }
        container.scrollTop = container.scrollHeight;
    }
    
    eventSource.onmessage = function(e) {
        const data = e.data;
        
        if (data.startsWith('[PROGRESS]')) {
            const message = data.replace('[PROGRESS]', '');
            progressText.textContent = message;
            
            if (message.includes('解析')) {
                progressFill.style.width = '30%';
            } else if (message.includes('分块')) {
                progressFill.style.width = '50%';
            } else if (message.includes('索引')) {
                progressFill.style.width = '70%';
            } else if (message.includes('摘要')) {
                progressFill.style.width = '90%';
            }
        } else if (data.startsWith('[chunk]')) {
            const chunk = data.substring(7);
            appendChunk(chunk);
        } else if (data.startsWith('[DONE]')) {
            eventSource.close();
            progressFill.style.width = '100%';
            isGenerating = false;
            
            if (streamingMessageElement) {
                streamingMessageElement.classList.remove('streaming');
            }
            
            setTimeout(() => {
                progressBar.classList.add('hidden');
                progressFill.style.width = '0%';
                uploadBtn.disabled = false;
            }, 1000);
            
            loadMessages(currentConversationId);
            updateUIState();
        } else if (data.startsWith('[stopped]')) {
            eventSource.close();
            
            if (userMessageElement) {
                userMessageElement.remove();
            }
            if (streamingMessageElement) {
                streamingMessageElement.remove();
            }
            
            progressBar.classList.add('hidden');
            progressFill.style.width = '0%';
            uploadBtn.disabled = false;
            isGenerating = false;
            updateUIState();
            
            loadMessages(currentConversationId);
            updateStatus();
            
            const message = data.replace('[stopped]', '');
            alert(message);
        } else if (data.startsWith('[ERROR]')) {
            const errorMsg = data.replace('[ERROR]', '');
            eventSource.close();
            
            if (userMessageElement) {
                userMessageElement.remove();
            }
            if (streamingMessageElement) {
                streamingMessageElement.remove();
            }
            
            progressBar.classList.add('hidden');
            progressFill.style.width = '0%';
            uploadBtn.disabled = false;
            isGenerating = false;
            updateUIState();
            
            alert(errorMsg);
        }
    };
    
    eventSource.onerror = function() {
        eventSource.close();
        
        if (userMessageElement) {
            userMessageElement.remove();
        }
        if (streamingMessageElement) {
            streamingMessageElement.remove();
        }
        
        progressBar.classList.add('hidden');
        progressFill.style.width = '0%';
        uploadBtn.disabled = false;
        isGenerating = false;
        updateUIState();
    };
}

function removeDocument() {
    fetch('/api/documents/remove', { method: 'DELETE' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateDocumentInfo(null);
                alert(data.message);
            }
        })
        .catch(error => console.error('移除文档失败:', error));
}

function updateDocumentInfo(fileName) {
    const documentBar = document.getElementById('documentBar');
    const documentName = document.getElementById('documentName');

    if (fileName) {
        documentBar.classList.remove('hidden');
        documentName.textContent = fileName;
    } else {
        documentBar.classList.add('hidden');
    }
}

function updateConversationTitle() {
    if (!currentConversationId) return;
    
    fetch(`/api/conversations/${currentConversationId}/messages`)
        .then(response => response.json())
        .then(data => {
            fetch('/api/conversations')
                .then(response => response.json())
                .then(convData => {
                    const currentConv = convData.conversations.find(c => c.id === currentConversationId);
                    if (currentConv) {
                        document.getElementById('chatTitle').textContent = currentConv.name;
                    }
                });
        })
        .catch(error => console.error('更新对话标题失败:', error));
}

function loadConfig() {
    fetch('/api/config')
        .then(response => response.json())
        .then(data => {
            currentConfig = data;
            document.getElementById('llmProvider').value = data.llm_provider || 'ollama';
            document.getElementById('ollamaBaseUrl').value = data.ollama_base_url || 'http://localhost:11434';

            loadOpenaiEndpoints(data);
            loadAnthropicEndpoints(data);

            document.getElementById('maxContextTurns').value = data.max_context_turns;
            document.getElementById('speechRecognitionLang').value = data.speech_recognition_lang || 'zh-CN';
            document.getElementById('speechSynthesisLang').value = data.speech_synthesis_lang || 'zh-CN';
            document.getElementById('maxRecordingTime').value = data.max_recording_time || 30;

            updateSpeechRecognitionLang(data.speech_recognition_lang || 'zh-CN');
            updateSpeechSynthesisLang(data.speech_synthesis_lang || 'zh-CN');
            maxRecordingTime = data.max_recording_time || 30;

            onProviderChange();
            updateModelSelectForProvider();
        })
        .catch(error => console.error('加载配置失败:', error));
}

function loadOpenaiEndpoints(data) {
    const endpoints = data.openai_endpoints || [];
    const currentEndpoint = data.openai_current_endpoint || '';
    const select = document.getElementById('openaiEndpointSelect');
    const currentModel = data.openai_current_model || '';

    select.innerHTML = '<option value="">-- 选择或添加端点 --</option>';

    endpoints.forEach(ep => {
        const option = document.createElement('option');
        option.value = ep.name;
        option.textContent = ep.name;
        if (ep.name === currentEndpoint) {
            option.selected = true;
        }
        select.appendChild(option);
    });

    if (currentEndpoint) {
        const ep = endpoints.find(e => e.name === currentEndpoint);
        if (ep) {
            document.getElementById('openaiEndpointName').value = ep.name;
            document.getElementById('openaiEndpointUrl').value = ep.base_url || '';
            document.getElementById('openaiEndpointKey').value = ep.api_key || '';
            document.getElementById('openaiEndpointModels').value = (ep.models || []).join(', ');
        }
    }
}

function onOpenaiEndpointChange() {
    const select = document.getElementById('openaiEndpointSelect');
    const selectedName = select.value;

    hideOpenaiEndpointForm();

    if (!selectedName) {
        return;
    }

    const endpoints = currentConfig.openai_endpoints || [];
    const ep = endpoints.find(e => e.name === selectedName);
    if (ep) {
        document.getElementById('openaiEndpointName').value = ep.name;
        document.getElementById('openaiEndpointUrl').value = ep.base_url || '';
        document.getElementById('openaiEndpointKey').value = ep.api_key || '';
        document.getElementById('openaiEndpointModels').value = (ep.models || []).join(', ');
        showEditOpenaiEndpointForm();
    }
}

function showAddOpenaiEndpointForm() {
    document.getElementById('openaiEndpointForm').style.display = 'block';
    document.getElementById('openaiEndpointName').value = '';
    document.getElementById('openaiEndpointUrl').value = '';
    document.getElementById('openaiEndpointKey').value = '';
    document.getElementById('openaiEndpointModels').value = '';
    document.getElementById('deleteOpenaiEndpointBtn').style.display = 'none';
}

function showEditOpenaiEndpointForm() {
    document.getElementById('openaiEndpointForm').style.display = 'block';
    document.getElementById('deleteOpenaiEndpointBtn').style.display = 'inline-block';
}

function hideOpenaiEndpointForm() {
    document.getElementById('openaiEndpointForm').style.display = 'none';
}

function saveOpenaiEndpoint() {
    const name = document.getElementById('openaiEndpointName').value.trim();
    const base_url = document.getElementById('openaiEndpointUrl').value.trim();
    const api_key = document.getElementById('openaiEndpointKey').value.trim();
    const modelsStr = document.getElementById('openaiEndpointModels').value.trim();
    const models = modelsStr ? modelsStr.split(',').map(m => m.trim()).filter(m => m) : [];

    if (!name) {
        alert('请输入端点名称');
        return;
    }
    if (!base_url) {
        alert('请输入 API 地址');
        return;
    }

    const endpoints = currentConfig.openai_endpoints || [];
    const existingIndex = endpoints.findIndex(e => e.name === name);

    const endpoint = {
        name: name,
        base_url: base_url,
        api_key: api_key,
        models: models
    };

    if (existingIndex >= 0) {
        fetch(`/api/openai/endpoints/${encodeURIComponent(name)}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(endpoint)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                currentConfig.openai_endpoints[existingIndex] = data.endpoint;
                loadOpenaiEndpoints(currentConfig);
                hideOpenaiEndpointForm();
                updateModelSelectForProvider();
            } else {
                alert('更新失败: ' + data.error);
            }
        })
        .catch(error => {
            console.error('更新端点失败:', error);
            alert('更新端点失败');
        });
    } else {
        fetch('/api/openai/endpoints', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(endpoint)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (!currentConfig.openai_endpoints) {
                    currentConfig.openai_endpoints = [];
                }
                currentConfig.openai_endpoints.push(data.endpoint);
                currentConfig.openai_current_endpoint = name;
                if (models.length > 0) {
                    currentConfig.openai_current_model = models[0];
                }
                fetch('/api/openai/switch', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        endpoint_name: name,
                        model: models.length > 0 ? models[0] : ''
                    })
                })
                .then(response => response.json())
                .then(data => {
                    loadOpenaiEndpoints(currentConfig);
                    hideOpenaiEndpointForm();
                    updateModelSelectForProvider();
                });
            } else {
                alert('添加失败: ' + data.error);
            }
        })
        .catch(error => {
            console.error('添加端点失败:', error);
            alert('添加端点失败');
        });
    }
}

function deleteOpenaiEndpoint() {
    const name = document.getElementById('openaiEndpointName').value.trim();
    if (!name) {
        return;
    }
    if (!confirm(`确定要删除端点 "${name}" 吗？`)) {
        return;
    }

    fetch(`/api/openai/endpoints/${encodeURIComponent(name)}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            currentConfig.openai_endpoints = currentConfig.openai_endpoints.filter(e => e.name !== name);
            loadOpenaiEndpoints(currentConfig);
            hideOpenaiEndpointForm();
            updateModelSelectForProvider();
        } else {
            alert('删除失败: ' + data.error);
        }
    })
    .catch(error => {
        console.error('删除端点失败:', error);
        alert('删除端点失败');
    });
}

function loadAnthropicEndpoints(data) {
    const endpoints = data.anthropic_endpoints || [];
    const currentEndpoint = data.anthropic_current_endpoint || '';
    const select = document.getElementById('anthropicEndpointSelect');
    const currentModel = data.anthropic_current_model || '';

    select.innerHTML = '<option value="">-- 选择或添加端点 --</option>';

    endpoints.forEach(ep => {
        const option = document.createElement('option');
        option.value = ep.name;
        option.textContent = ep.name;
        if (ep.name === currentEndpoint) {
            option.selected = true;
        }
        select.appendChild(option);
    });

    if (currentEndpoint) {
        const ep = endpoints.find(e => e.name === currentEndpoint);
        if (ep) {
            document.getElementById('anthropicEndpointName').value = ep.name;
            document.getElementById('anthropicEndpointUrl').value = ep.base_url || '';
            document.getElementById('anthropicEndpointKey').value = ep.api_key || '';
            document.getElementById('anthropicEndpointModels').value = (ep.models || []).join(', ');
        }
    }
}

function onAnthropicEndpointChange() {
    const select = document.getElementById('anthropicEndpointSelect');
    const selectedName = select.value;

    hideEndpointForm();

    if (!selectedName) {
        return;
    }

    const endpoints = currentConfig.anthropic_endpoints || [];
    const ep = endpoints.find(e => e.name === selectedName);
    if (ep) {
        document.getElementById('anthropicEndpointName').value = ep.name;
        document.getElementById('anthropicEndpointUrl').value = ep.base_url || '';
        document.getElementById('anthropicEndpointKey').value = ep.api_key || '';
        document.getElementById('anthropicEndpointModels').value = (ep.models || []).join(', ');
        showEditEndpointForm();
    }
}

function showAddEndpointForm() {
    document.getElementById('anthropicEndpointName').value = '';
    document.getElementById('anthropicEndpointUrl').value = '';
    document.getElementById('anthropicEndpointKey').value = '';
    document.getElementById('anthropicEndpointModels').value = '';
    document.getElementById('deleteEndpointBtn').style.display = 'none';
    document.getElementById('anthropicEndpointForm').style.display = 'block';
    document.getElementById('anthropicEndpointName').focus();
}

function showEditEndpointForm() {
    document.getElementById('deleteEndpointBtn').style.display = 'inline-block';
    document.getElementById('anthropicEndpointForm').style.display = 'block';
}

function hideEndpointForm() {
    document.getElementById('anthropicEndpointForm').style.display = 'none';
}

function saveAnthropicEndpoint() {
    const name = document.getElementById('anthropicEndpointName').value.trim();
    const base_url = document.getElementById('anthropicEndpointUrl').value.trim();
    const api_key = document.getElementById('anthropicEndpointKey').value.trim();
    const modelsStr = document.getElementById('anthropicEndpointModels').value.trim();
    const models = modelsStr ? modelsStr.split(',').map(m => m.trim()).filter(m => m) : [];

    if (!name) {
        alert('请输入端点名称');
        return;
    }
    if (!base_url) {
        alert('请输入API地址');
        return;
    }

    const select = document.getElementById('anthropicEndpointSelect');
    const existingNames = Array.from(select.options).map(o => o.value).filter(v => v);
    const isNewEndpoint = !existingNames.includes(name);

    const endpointData = {
        name: name,
        base_url: base_url,
        api_key: api_key,
        models: models
    };

    if (isNewEndpoint) {
        fetch('/api/anthropic/endpoints', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(endpointData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                switchToAnthropicEndpoint(name, models[0] || '');
                reloadConfig();
            } else {
                alert(data.error || '添加端点失败');
            }
        })
        .catch(error => {
            console.error('添加端点失败:', error);
            alert('添加端点失败');
        });
    } else {
        fetch(`/api/anthropic/endpoints/${encodeURIComponent(name)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(endpointData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                reloadConfig();
            } else {
                alert(data.error || '更新端点失败');
            }
        })
        .catch(error => {
            console.error('更新端点失败:', error);
            alert('更新端点失败');
        });
    }
}

function deleteAnthropicEndpoint() {
    const name = document.getElementById('anthropicEndpointName').value.trim();
    if (!name) {
        return;
    }

    if (!confirm(`确定要删除端点"${name}"吗？`)) {
        return;
    }

    fetch(`/api/anthropic/endpoints/${encodeURIComponent(name)}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            hideEndpointForm();
            reloadConfig();
        } else {
            alert(data.error || '删除端点失败');
        }
    })
    .catch(error => {
        console.error('删除端点失败:', error);
        alert('删除端点失败');
    });
}

function switchToAnthropicEndpoint(endpointName, model) {
    fetch('/api/anthropic/switch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            endpoint_name: endpointName,
            model: model
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            reloadConfig();
        }
    })
    .catch(error => console.error('切换端点失败:', error));
}

function reloadConfig() {
    fetch('/api/config')
        .then(response => response.json())
        .then(data => {
            currentConfig = data;
            loadAnthropicEndpoints(data);
            updateModelSelectForProvider();
        })
        .catch(error => console.error('重新加载配置失败:', error));
}

function openConfigModal() {
    document.getElementById('configModal').classList.add('show');
    loadSkills();
}

function closeConfigModal() {
    document.getElementById('configModal').classList.remove('show');
}

function onProviderChange() {
    const provider = document.getElementById('llmProvider').value;

    document.getElementById('ollamaGroup').style.display = provider === 'ollama' ? 'block' : 'none';

    const apiGroups = document.querySelectorAll('.api-config');
    apiGroups.forEach(group => {
        if (group.id !== 'anthropicGroup' && group.classList.contains('api-config')) {
            group.style.display = provider === 'ollama' ? 'none' : 'block';
        }
    });

    const openaiGroups = ['openaiGroup', 'openaiEndpointForm'];
    openaiGroups.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = provider === 'openai' ? 'block' : 'none';
    });

    document.getElementById('anthropicGroup').style.display = provider === 'anthropic' ? 'block' : 'none';
    if (provider !== 'anthropic') {
        hideEndpointForm();
    }
    if (provider !== 'openai') {
        hideOpenaiEndpointForm();
    }

    updateModelSelectForProvider();
}

function updateModelSelectForProvider() {
    const provider = document.getElementById('llmProvider').value;
    const modelSelect = document.getElementById('modelSelect');

    modelSelect.innerHTML = '';

    if (provider === 'ollama') {
        const ollamaModels = [
            { value: 'qwen3:8b', text: 'qwen3:8b (文本)' },
            { value: 'qwen3:14b', text: 'qwen3:14b (文本)' },
            { value: 'deepseek-r1:8b', text: 'deepseek-r1:8b (文本)' },
            { value: 'qwen3-vl:8b', text: 'qwen3-vl:8b (多模态)' },
            { value: 'qwen3.5:0.8b', text: 'qwen3.5:0.8b (多模态)' },
            { value: 'qwen3.5:4b', text: 'qwen3.5:4b (多模态)' },
            { value: 'qwen3.5:9b', text: 'qwen3.5:9b (多模态)' }
        ];
        ollamaModels.forEach(model => {
            const option = document.createElement('option');
            option.value = model.value;
            option.textContent = model.text;
            if (model.value === 'qwen3.5:9b') option.selected = true;
            modelSelect.appendChild(option);
        });
    } else if (provider === 'openai') {
        const currentEndpoint = currentConfig.openai_current_endpoint || '';
        const currentModel = currentConfig.openai_current_model || '';
        const endpoints = currentConfig.openai_endpoints || [];
        const ep = endpoints.find(e => e.name === currentEndpoint);
        const models = ep && ep.models ? ep.models : [];

        if (models.length > 0) {
            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                if (model === currentModel) {
                    option.selected = true;
                }
                modelSelect.appendChild(option);
            });
        } else {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = '-- 请先添加端点和模型 --';
            modelSelect.appendChild(option);
        }
    } else if (provider === 'anthropic') {
        const currentEndpoint = currentConfig.anthropic_current_endpoint || '';
        const currentModel = currentConfig.anthropic_current_model || '';
        const endpoints = currentConfig.anthropic_endpoints || [];
        const ep = endpoints.find(e => e.name === currentEndpoint);
        const models = ep && ep.models ? ep.models : [];

        if (models.length > 0) {
            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model;
                if (model === currentModel) {
                    option.selected = true;
                }
                modelSelect.appendChild(option);
            });
        } else {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = '-- 请先添加端点和模型 --';
            modelSelect.appendChild(option);
        }
    }

    currentModel = modelSelect.value;
}

function saveConfig() {
    const llmProvider = document.getElementById('llmProvider').value;
    const ollamaBaseUrl = document.getElementById('ollamaBaseUrl').value;
    const maxTurns = parseInt(document.getElementById('maxContextTurns').value);
    const speechRecognitionLang = document.getElementById('speechRecognitionLang').value;
    const speechSynthesisLang = document.getElementById('speechSynthesisLang').value;
    const maxRecordingTimeInput = parseInt(document.getElementById('maxRecordingTime').value);

    fetch('/api/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            llm_provider: llmProvider,
            ollama_base_url: ollamaBaseUrl,
            max_context_turns: maxTurns,
            speech_recognition_lang: speechRecognitionLang,
            speech_synthesis_lang: speechSynthesisLang,
            max_recording_time: maxRecordingTimeInput
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                closeConfigModal();
                updateModelSelectForProvider();
                alert('配置已保存');
            } else {
                alert(data.error);
            }
        })
        .catch(error => {
            console.error('保存配置失败:', error);
            alert('保存配置失败');
        });
}

function loadSkills() {
    const skillList = document.getElementById('skillList');
    if (!skillList) return;

    fetch('/api/skills')
        .then(response => response.json())
        .then(data => {
            if (data.skills && data.skills.length > 0) {
                skillList.innerHTML = data.skills.map(skill => `
                    <div class="skill-item">
                        <div class="skill-name">${escapeHtml(skill.name)}</div>
                        <div class="skill-desc">${escapeHtml(skill.description)}</div>
                        <div class="skill-meta">
                            ${skill.has_scripts ? '📜 有脚本' : ''}
                            ${skill.has_references ? '📚 有参考文档' : ''}
                        </div>
                    </div>
                `).join('');
            } else {
                skillList.innerHTML = '<div class="skill-empty">暂无已安装的 Skill<br><small>将 Skill 文件夹放入 skills/ 目录即可自动加载</small></div>';
            }
        })
        .catch(error => {
            console.error('加载 Skill 列表失败:', error);
            skillList.innerHTML = '<div class="skill-empty">加载失败</div>';
        });
}

function reloadSkills() {
    const skillList = document.getElementById('skillList');
    if (skillList) {
        skillList.innerHTML = '<div class="skill-loading">重新加载中...</div>';
    }

    fetch('/api/skills/reload', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                loadSkills();
                alert(data.message);
            } else {
                alert('重新加载失败: ' + data.error);
                loadSkills();
            }
        })
        .catch(error => {
            console.error('重新加载 Skill 失败:', error);
            alert('重新加载失败');
            loadSkills();
        });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function updateSpeechRecognitionLang(lang) {
    if (recognition) {
        recognition.lang = lang;
    }
}

function updateSpeechSynthesisLang(lang) {
    const voices = synth.getVoices();
    selectBestVoice(voices, lang);
}

function selectBestVoice(voices, lang) {
    if (!voices || voices.length === 0) return;

    const langCode = lang.split('-')[0];
    
    let bestVoice = voices.find(voice => voice.lang === lang);
    if (!bestVoice) {
        bestVoice = voices.find(voice => voice.lang.startsWith(langCode));
    }
    if (!bestVoice) {
        bestVoice = voices.find(voice => voice.lang.startsWith('en'));
    }
    if (!bestVoice) {
        bestVoice = voices[0];
    }

    ttsVoice = bestVoice;
}

function onModelChange() {
    const modelSelect = document.getElementById('modelSelect');
    currentModel = modelSelect.value;

    const provider = document.getElementById('llmProvider').value;
    if (provider === 'anthropic' && currentModel) {
        switchToAnthropicEndpoint(currentConfig.anthropic_current_endpoint, currentModel);
    }
}

function handleImageUpload(event) {
    const files = event.target.files;
    
    for (let file of files) {
        if (!file.type.startsWith('image/')) {
            alert('请选择图片文件');
            continue;
        }
        
        const reader = new FileReader();
        reader.onload = function(e) {
            fetch('/api/images/upload', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: e.target.result })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateImageInfo(data.images);
                    updateModelForImages();
                } else {
                    alert(data.error);
                }
            })
            .catch(error => {
                console.error('上传图片失败:', error);
                alert('上传图片失败');
            });
        };
        reader.readAsDataURL(file);
    }
    
    event.target.value = '';
}

function takeScreenshot() {
    if (isTakingScreenshot) return;
    isTakingScreenshot = true;
    
    document.getElementById('statusText').textContent = '正在截图...';
    
    fetch('/api/screenshot', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            document.getElementById('statusText').textContent = '就绪';
            
            if (data.success) {
                updateImageInfo(data.images);
                updateModelForImages();
            } else {
                if (data.error !== '截图已取消') {
                    alert(data.error);
                }
            }
        })
        .catch(error => {
            document.getElementById('statusText').textContent = '就绪';
            console.error('截图失败:', error);
            alert('截图失败');
        })
        .finally(() => {
            isTakingScreenshot = false;
        });
}

function updateImageInfo(images) {
    currentImages = images || [];
    const imageBar = document.getElementById('imageBar');
    const imagePreviewList = document.getElementById('imagePreviewList');
    
    if (currentImages.length > 0) {
        imageBar.classList.remove('hidden');
        imagePreviewList.innerHTML = '';
        
        currentImages.forEach((img, index) => {
            const imgWrapper = document.createElement('div');
            imgWrapper.className = 'image-preview-item';
            
            const imgElement = document.createElement('img');
            imgElement.src = 'data:image/jpeg;base64,' + img.data;
            imgElement.alt = img.name;
            
            const removeBtn = document.createElement('button');
            removeBtn.className = 'image-item-remove-btn';
            removeBtn.textContent = '✕';
            removeBtn.onclick = () => removeSingleImage(index);
            
            imgWrapper.appendChild(imgElement);
            imgWrapper.appendChild(removeBtn);
            imagePreviewList.appendChild(imgWrapper);
        });
    } else {
        imageBar.classList.add('hidden');
        imagePreviewList.innerHTML = '';
    }
}

function removeSingleImage(index) {
    fetch('/api/images/remove/' + index, { method: 'DELETE' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateImageInfo(data.images);
                updateModelForImages();
            }
        })
        .catch(error => console.error('移除图片失败:', error));
}

function removeImages() {
    fetch('/api/images/remove', { method: 'DELETE' })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateImageInfo([]);
                updateModelForImages();
            }
        })
        .catch(error => console.error('移除图片失败:', error));
}

const multimodalModels = ['qwen3-vl:8b', 'qwen3.5:0.8b', 'qwen3.5:4b', 'qwen3.5:9b'];

function updateModelForImages() {
    const imageBar = document.getElementById('imageBar');
    const modelSelect = document.getElementById('modelSelect');
    
    if (!imageBar.classList.contains('hidden')) {
        const multimodalOption = modelSelect.querySelector('option[value="qwen3-vl:8b"]');
        if (multimodalOption) {
            const currentIsMultimodal = multimodalModels.includes(currentModel);
            if (!currentIsMultimodal) {
                modelSelect.value = 'qwen3-vl:8b';
                currentModel = 'qwen3-vl:8b';
            }
            
            Array.from(modelSelect.options).forEach(option => {
                if (!multimodalModels.includes(option.value)) {
                    option.disabled = true;
                }
            });
        }
    } else {
        Array.from(modelSelect.options).forEach(option => {
            option.disabled = false;
        });
    }
}

function initDragAndDrop() {
    const mainContent = document.querySelector('.main-content');
    if (!mainContent) return;

    mainContent.addEventListener('dragover', handleDragOver);
    mainContent.addEventListener('dragenter', handleDragEnter);
    mainContent.addEventListener('dragleave', handleDragLeave);
    mainContent.addEventListener('drop', handleDrop);
}

function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
}

function handleDragEnter(e) {
    e.preventDefault();
    e.stopPropagation();
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        mainContent.classList.add('drag-over');
    }
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    const mainContent = document.querySelector('.main-content');
    if (mainContent && !mainContent.contains(e.relatedTarget)) {
        mainContent.classList.remove('drag-over');
    }
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        mainContent.classList.remove('drag-over');
    }

    const files = e.dataTransfer.files;
    if (!files || files.length === 0) return;

    const imageFiles = [];
    const documentFiles = [];

    for (let file of files) {
        if (file.type.startsWith('image/')) {
            imageFiles.push(file);
        } else if (isDocumentFile(file)) {
            documentFiles.push(file);
        } else {
            console.warn('不支持的文件类型:', file.type, file.name);
        }
    }

    if (imageFiles.length > 0) {
        handleDragImageUpload(imageFiles);
    }

    if (documentFiles.length > 0) {
        handleDragDocumentUpload(documentFiles);
    }
}

function isDocumentFile(file) {
    const docExtensions = ['pdf', 'docx', 'txt'];
    const ext = file.name.split('.').pop().toLowerCase();
    return docExtensions.includes(ext);
}

function handleDragImageUpload(files) {
    for (let file of files) {
        const fakeEvent = {
            target: { files: [file] }
        };
        handleImageUpload(fakeEvent);
    }
}

function handleDragDocumentUpload(files) {
    for (let file of files) {
        const fakeEvent = {
            target: { files: [file] }
        };
        uploadFile(fakeEvent);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

window.onload = init;
