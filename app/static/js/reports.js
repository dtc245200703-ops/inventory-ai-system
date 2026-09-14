document.querySelectorAll('[data-ai]').forEach(button => button.addEventListener('click', async () => {
    const box = document.getElementById('aiResult');
    const buttons = document.querySelectorAll('[data-ai]');
    buttons.forEach(item => item.disabled = true);
    box.textContent = 'Đang phân tích dữ liệu kho…';
    try { const result = await api(button.dataset.ai, {method: 'POST'}); box.textContent = result.result; }
    catch (error) { box.textContent = error.message; }
    finally { buttons.forEach(item => item.disabled = false); }
}));
