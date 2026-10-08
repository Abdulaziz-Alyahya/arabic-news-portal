(() => {
    const root = document.documentElement;
    const system = window.matchMedia('(prefers-color-scheme: dark)');
    let preference = null;
    try {
        const saved = localStorage.getItem('news-theme');
        if (saved === 'light' || saved === 'dark') preference = saved;
    } catch (_) { /* Theme still works when browser storage is unavailable. */ }

    function apply(theme) {
        root.dataset.theme = theme;
        const button = document.getElementById('theme-toggle');
        if (button) {
            button.setAttribute('aria-pressed', String(theme === 'dark'));
            button.setAttribute('aria-label', theme === 'dark' ? 'تفعيل الوضع الفاتح' : 'تفعيل الوضع الداكن');
            button.title = button.getAttribute('aria-label');
        }
    }
    apply(preference || (system.matches ? 'dark' : 'light'));
    system.addEventListener('change', () => {
        if (!preference) apply(system.matches ? 'dark' : 'light');
    });
    window.addEventListener('storage', event => {
        if (event.key !== 'news-theme') return;
        preference = ['light', 'dark'].includes(event.newValue) ? event.newValue : null;
        apply(preference || (system.matches ? 'dark' : 'light'));
    });
    document.addEventListener('DOMContentLoaded', () => {
        apply(root.dataset.theme);
        document.getElementById('theme-toggle')?.addEventListener('click', () => {
            root.classList.add('theme-changing');
            preference = root.dataset.theme === 'dark' ? 'light' : 'dark';
            apply(preference);
            try { localStorage.setItem('news-theme', preference); } catch (_) {}
            window.setTimeout(() => root.classList.remove('theme-changing'), 300);
        });
    });
})();
