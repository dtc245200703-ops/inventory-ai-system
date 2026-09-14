(() => {
    const notice = document.getElementById('navigationNotice');
    const title = document.getElementById('navigationNoticeTitle');
    const storageKey = 'inventory.navigation';
    const links = document.querySelectorAll('.menu-item');
    const icons = {dashboard: '◫', products: '▣', inventory: '▤', receipts: '↓', issues: '↑', history: '◷', reports: '▥', users: '♙', categories: '◇', units: '⊞', suppliers: '▱'};
    function show(label) {
        notice.hidden = false;
        title.textContent = `Đã mở ${label}`;
    }
    links.forEach(link => {
        const label = link.textContent.trim();
        const icon = document.createElement('span');
        icon.className = 'menu-icon';
        icon.setAttribute('aria-hidden', 'true');
        icon.textContent = icons[link.pathname.split('/').pop() || 'dashboard'] || '◇';
        link.prepend(icon);
        if (link.pathname === window.location.pathname) link.setAttribute('aria-current', 'page');
        link.addEventListener('click', event => {
            if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
            if (link.pathname === window.location.pathname) {
                event.preventDefault();
                show(label);
                return;
            }
            try {
                sessionStorage.setItem(storageKey, JSON.stringify({path: link.pathname, label, time: Date.now()}));
            } catch (_) {
                // Navigation still works when browser storage is unavailable.
            }
        });
    });
    try {
        const pending = JSON.parse(sessionStorage.getItem(storageKey) || 'null');
        sessionStorage.removeItem(storageKey);
        if (pending && pending.path === window.location.pathname && Date.now() - pending.time < 30000) show(pending.label);
    } catch (_) { /* Ignore unavailable storage or invalid saved data. */ }
    document.getElementById('dismissNavigationNotice').addEventListener('click', () => {
        notice.hidden = true;
        document.querySelector('.menu-item[aria-current="page"]')?.focus();
    });
})();
