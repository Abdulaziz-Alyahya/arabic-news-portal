/* Shared presentation helpers. API strings are always rendered as text. */
window.NewsUI = (() => {
    function element(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }
    function timestamp(value) {
        if (!value) return -Infinity;
        const result = new Date(value).getTime();
        return Number.isFinite(result) ? result : -Infinity;
    }
    function date(value) {
        return timestamp(value) === -Infinity ? 'التاريخ غير متوفر' : new Date(value).toLocaleString('ar', {
            year: 'numeric', month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit'
        });
    }
    function time(value, className) {
        const node = element('time', className, date(value));
        if (timestamp(value) !== -Infinity) node.dateTime = new Date(value).toISOString();
        return node;
    }
    function state(container, text, retry) {
        const node = element('div', 'state');
        node.setAttribute('role', retry ? 'alert' : 'status');
        node.append(element('p', '', text));
        if (retry) {
            const button = element('button', '', 'إعادة المحاولة');
            button.type = 'button';
            button.addEventListener('click', retry);
            node.append(button);
        }
        container.replaceChildren(node);
    }
    function entrance(card, index) {
        card.style.setProperty('--delay', `${Math.min(index, 5) * 45}ms`);
    }
    function reconcile(container, items, key, render, initial) {
        const previous = new Map([...container.children].filter(node => node.dataset.key)
            .map(node => [node.dataset.key, node]));
        const active = document.activeElement;
        const focusedHref = container.contains(active) ? active.getAttribute('href') : null;
        const position = { left: window.scrollX, top: window.scrollY };
        const fragment = document.createDocumentFragment();
        items.forEach((item, index) => {
            const id = String(key(item));
            const signature = JSON.stringify(item);
            let node = previous.get(id);
            if (!node || node.dataset.signature !== signature) {
                node = render(item, index);
                node.dataset.key = id;
                node.dataset.signature = signature;
                if (!initial) node.style.animation = 'none';
            }
            fragment.append(node);
        });
        container.replaceChildren(fragment);
        if (focusedHref) {
            [...container.querySelectorAll('a')].find(link => link.getAttribute('href') === focusedHref)
                ?.focus({ preventScroll: true });
        }
        if (!initial) window.scrollTo(position);
    }

    function poll(load, interval = 60000) {
        let timer, controller, inFlight = false, stopped = false;
        async function refresh() {
            if (inFlight || stopped || document.hidden) return;
            clearTimeout(timer);
            inFlight = true;
            controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 20000);
            try { await load(controller.signal); }
            finally {
                clearTimeout(timeout);
                inFlight = false;
                if (!stopped && !document.hidden) timer = setTimeout(refresh, interval);
            }
        }
        document.addEventListener('visibilitychange', () => {
            clearTimeout(timer);
            if (!document.hidden) void refresh();
        });
        window.addEventListener('pagehide', () => {
            stopped = true;
            clearTimeout(timer);
            controller?.abort();
        });
        window.addEventListener('pageshow', () => {
            if (stopped) { stopped = false; void refresh(); }
        });
        void refresh();
        return refresh;
    }

    function updateStatus() {
        const node = element('p', 'refresh-status');
        node.setAttribute('role', 'status');
        node.hidden = true;
        document.querySelector('.page-heading').after(node);
        return message => { node.textContent = message; node.hidden = !message; };
    }
    return { element, timestamp, date, time, state, entrance, reconcile, poll, updateStatus };
})();
