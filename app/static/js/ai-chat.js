(() => {
    const form = document.getElementById('aiChatForm');
    if (!form) return;
    const input = document.getElementById('aiChatInput');
    const messages = document.getElementById('aiChatMessages');
    const status = document.getElementById('aiChatStatus');
    const send = document.getElementById('aiChatSend');
    const clear = document.getElementById('aiChatClear');
    let history = [];
    let busy = false;
    function addMessage(role, content) {
        const bubble = node('div', undefined, `ai-chat-message ${role}`);
        bubble.append(node('strong', role === 'user' ? 'Bạn' : 'AI'), node('p', content));
        messages.append(bubble);
        messages.scrollTop = messages.scrollHeight;
        return bubble;
    }
    form.addEventListener('submit', async event => {
        event.preventDefault();
        const message = input.value.trim();
        if (busy || !message || !form.reportValidity()) return;
        busy = true;
        send.disabled = clear.disabled = input.disabled = true;
        status.textContent = 'AI đang trả lời…';
        const pending = addMessage('user', message);
        try {
            const response = await api('/ai/chat', {
                method: 'POST', body: JSON.stringify({message, history}),
            });
            addMessage('assistant', response.result);
            history = [...history, {role: 'user', content: message},
                {role: 'assistant', content: response.result.slice(0, 20000)}].slice(-10);
            input.value = '';
            status.textContent = '';
        } catch (error) {
            pending.remove();
            status.textContent = `${error.message} Câu hỏi được giữ lại để bạn gửi lại.`;
        } finally {
            busy = false;
            send.disabled = clear.disabled = input.disabled = false;
            input.focus();
        }
    });
    input.addEventListener('keydown', event => {
        if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
            event.preventDefault();
            form.requestSubmit();
        }
    });
    clear.addEventListener('click', () => {
        history = [];
        messages.replaceChildren();
        status.textContent = '';
        input.value = '';
        input.focus();
    });
})();
