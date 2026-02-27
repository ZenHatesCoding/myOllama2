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

let currentModel = 'qwen3:8b';

let recognition = null;
let isRecording = false;
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
        })
        .catch(error => console.error('加载消息失败:', error));
}

function renderMessages(messages) {
    const container = document.getElementById('messagesContainer');
    container.innerHTML = '';

    messages.forEach(msg => {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${msg.role}`;
        
        const avatar = msg.role === 'user' ? '👤' : '🤖';
        const date = new Date(msg.timestamp);
        const timeStr = date.toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' });

        let content;
        if (msg.role === 'assistant') {
            content = marked.parse(msg.content);
        } else {
            content = escapeHtml(msg.content);
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
            model: currentModel
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

        if (data === '[DONE]') {
            stopStreaming();
            loadConversations();
            updateConversationTitle();
        } else if (data.startsWith('[ERROR]')) {
            const errorMsg = data.substring(7);
            alert(errorMsg);
            stopStreaming();
        } else {
            appendStreamingMessage(data);
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

    fetch('/api/documents/upload', {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert(data.message);
                updateDocumentInfo(data.document_file);
            } else {
                alert(data.error);
            }
        })
        .catch(error => {
            console.error('上传文件失败:', error);
            alert('上传文件失败');
        });

    event.target.value = '';
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
            document.getElementById('maxContextTurns').value = data.max_context_turns;
            document.getElementById('speechRecognitionLang').value = data.speech_recognition_lang || 'zh-CN';
            document.getElementById('speechSynthesisLang').value = data.speech_synthesis_lang || 'zh-CN';
            document.getElementById('maxRecordingTime').value = data.max_recording_time || 30;
            
            updateSpeechRecognitionLang(data.speech_recognition_lang || 'zh-CN');
            updateSpeechSynthesisLang(data.speech_synthesis_lang || 'zh-CN');
            maxRecordingTime = data.max_recording_time || 30;
        })
        .catch(error => console.error('加载配置失败:', error));
}

function openConfigModal() {
    document.getElementById('configModal').classList.add('show');
}

function closeConfigModal() {
    document.getElementById('configModal').classList.remove('show');
}

function saveConfig() {
    const maxTurns = parseInt(document.getElementById('maxContextTurns').value);
    const speechRecognitionLang = document.getElementById('speechRecognitionLang').value;
    const speechSynthesisLang = document.getElementById('speechSynthesisLang').value;
    const maxRecordingTimeInput = parseInt(document.getElementById('maxRecordingTime').value);

    fetch('/api/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            max_context_turns: maxTurns,
            speech_recognition_lang: speechRecognitionLang,
            speech_synthesis_lang: speechSynthesisLang,
            max_recording_time: maxRecordingTimeInput
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                currentConfig = data;
                updateSpeechRecognitionLang(speechRecognitionLang);
                updateSpeechSynthesisLang(speechSynthesisLang);
                maxRecordingTime = data.max_recording_time || 30;
                closeConfigModal();
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
    currentModel = document.getElementById('modelSelect').value;
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

function updateModelForImages() {
    const imageBar = document.getElementById('imageBar');
    const modelSelect = document.getElementById('modelSelect');
    
    if (!imageBar.classList.contains('hidden')) {
        const multimodalOption = modelSelect.querySelector('option[value="qwen3-vl:8b"]');
        if (multimodalOption) {
            modelSelect.value = 'qwen3-vl:8b';
            currentModel = 'qwen3-vl:8b';
            
            Array.from(modelSelect.options).forEach(option => {
                if (option.value !== 'qwen3-vl:8b') {
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

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

window.onload = init;
