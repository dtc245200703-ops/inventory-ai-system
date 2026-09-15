(() => {
    const form = document.getElementById('aiChatForm');
    if (!form) return;
    const input = document.getElementById('aiChatInput');
    const messages = document.getElementById('aiChatMessages');
    const status = document.getElementById('aiChatStatus');
    const send = document.getElementById('aiChatSend');
    const clear = document.getElementById('aiChatClear');
    const welcome = document.getElementById('aiChatWelcome');
    const drawer = document.getElementById('ai');
    const toggle = document.getElementById('aiChatToggle');
    const close = document.getElementById('aiChatClose');
    let history = [];
    let busy = false;
    function setOpen(open) {
        drawer.hidden = !open;
        toggle.setAttribute('aria-expanded', String(open));
        toggle.setAttribute('aria-label', open ? 'Đóng trợ lý AI' : 'Mở trợ lý AI');
        if (open) {
            toggle.removeAttribute('data-unread');
            const last = messages.lastElementChild;
            if (last && last !== welcome) messages.scrollTop += last.getBoundingClientRect().top - messages.getBoundingClientRect().top - 24;
            (busy ? close : input).focus();
        } else toggle.focus();
    }
    toggle.addEventListener('click', () => setOpen(drawer.hidden));
    close.addEventListener('click', () => setOpen(false));
    drawer.addEventListener('keydown', event => {
        if (event.key === 'Escape') { event.preventDefault(); setOpen(false); }
    });
    // Build a small Markdown subset with DOM nodes only; never interpret HTML.
    function inline(parent, text) {
        for (const part of text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)) {
            if (part.startsWith('**') && part.endsWith('**')) parent.append(node('strong', part.slice(2, -2)));
            else if (part.startsWith('`') && part.endsWith('`')) parent.append(node('code', part.slice(1, -1)));
            else parent.append(document.createTextNode(part));
        }
    }
    function formatted(text) {
        const body = node('div', undefined, 'ai-chat-body');
        let list = null;
        for (const line of text.split(/\r?\n/)) {
            const item = line.match(/^\s*(?:([-*])|\d+[.)])\s+(.+)$/);
            if (item) {
                const type = item[1] ? 'ul' : 'ol';
                if (!list || list.tagName.toLowerCase() !== type) {
                    list = node(type); body.append(list);
                }
                const li = node('li'); inline(li, item[2]); list.append(li);
            } else {
                list = null;
                if (!line.trim()) continue;
                const p = node('p'); inline(p, line.replace(/^#{1,6}\s+/, '')); body.append(p);
            }
        }
        return body;
    }
    function addMessage(role, content) {
        const bubble = node('div', undefined, `ai-chat-message ${role}`);
        bubble.append(node('strong', role === 'user' ? 'BẠN' : '✦ TRỢ LÝ KHO'),
            role === 'assistant' ? formatted(content) : node('div', content, 'ai-chat-body'));
        messages.append(bubble);
        messages.scrollTop += bubble.getBoundingClientRect().top - messages.getBoundingClientRect().top - 24;
        return bubble;
    }
    form.addEventListener('submit', async event => {
        event.preventDefault();
        const message = input.value.trim();
        if (busy || !message || !form.reportValidity()) return;
        busy = true;
        welcome.hidden = true;
        send.disabled = clear.disabled = input.disabled = true;
        status.textContent = 'AI đang trả lời…';
        const pending = addMessage('user', message);
        try {
            const response = await api('/ai/chat', {
                method: 'POST', body: JSON.stringify({message, history}),
            });
            addMessage('assistant', response.result);
            if (drawer.hidden) toggle.setAttribute('data-unread', 'true');
            history = [...history, {role: 'user', content: message},
                {role: 'assistant', content: response.result.slice(0, 20000)}].slice(-10);
            input.value = '';
            status.textContent = '';
        } catch (error) {
            pending.remove();
            if (!history.length) welcome.hidden = false;
            status.textContent = `${error.message} Câu hỏi được giữ lại để bạn gửi lại.`;
        } finally {
            busy = false;
            send.disabled = clear.disabled = input.disabled = false;
            if (!drawer.hidden) input.focus();
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
        messages.replaceChildren(welcome);
        welcome.hidden = false;
        status.textContent = '';
        input.value = '';
        input.focus();
    });
    document.querySelectorAll('[data-chat-question]').forEach(button => {
        button.addEventListener('click', () => {
            if (busy) return;
            input.value = button.dataset.chatQuestion;
            form.requestSubmit();
        });
    });
})();
