/* Market Mega Mini App — 3-tab SPA */
(function () {
    'use strict';

    const tg = window.Telegram?.WebApp;

    function extractInitData() {
        if (tg && tg.initData) return tg.initData;
        try {
            const hash = (window.location.hash || "").replace(/^#/, "");
            const params = new URLSearchParams(hash);
            const tgData = params.get("tgWebAppData");
            if (tgData) return tgData;
        } catch (_) {}
        return "";
    }

    function showError(text, opts = {}) {
        document.getElementById('error-text').textContent = text;
        const r = document.getElementById('btn-reload');
        const c = document.getElementById('btn-close');
        if (r) r.style.display = (opts.showReload !== false) ? '' : 'none';
        if (c) c.style.display = (opts.showClose) ? '' : 'none';
        ['loader', 'tab-home', 'tab-cart', 'tab-chat', 'bottom-nav'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.add('hidden');
        });
        document.getElementById('error-screen').classList.remove('hidden');
    }

    window.closeWebApp = function () {
        if (window.Telegram?.WebApp) window.Telegram.WebApp.close();
    };

    if (!tg) {
        document.getElementById('loader').classList.add('hidden');
        const dbg = `[debug] hash=${(window.location.hash||"").substring(0,40)} ua=${navigator.userAgent.substring(0,30)}`;
        showError("Telegram WebApp topilmadi. Bu sahifani Telegram ichidan oching.\n\n" + dbg,
                  { showReload: true });
        return;
    }

    const initData = extractInitData();
    if (!initData) {
        document.getElementById('loader').classList.add('hidden');
        const dbg =
            `\n\n[debug]\n` +
            `tg.initData length: ${(tg.initData||"").length}\n` +
            `tg.version: ${tg.version || "?"}\n` +
            `tg.platform: ${tg.platform || "?"}\n` +
            `hash: ${(window.location.hash||"EMPTY").substring(0, 60)}\n` +
            `URL: ${window.location.href.substring(0, 80)}`;
        showError("initData topilmadi. Mini app'ni yoping va Telegram'dan qayta oching." + dbg,
                  { showReload: false, showClose: true });
        return;
    }

    tg.ready();
    tg.expand();
    tg.setHeaderColor('secondary_bg_color');

    // ---------------------- State ----------------------
    const state = {
        user: null,
        categories: [],
        products: {},          // {categoryId: [...]}
        productsById: {},      // {productId: product}
        currentCategoryId: null,
        cart: {},              // {productId: {product, quantity}}
        currentTab: 'home',
        homeView: 'categories', // 'categories' | 'products'
        messages: [],
        lastMessageId: 0,
        chatPollTimer: null,
    };

    // ---------------------- API ----------------------
    async function api(path, opts = {}) {
        const headers = {
            'X-Telegram-Init-Data': initData,
            ...(opts.headers || {}),
        };
        if (opts.body && typeof opts.body === 'object') {
            headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(opts.body);
        }
        const res = await fetch(path, { ...opts, headers });
        if (!res.ok) {
            let m = `Xato: ${res.status}`;
            try { const e = await res.json(); if (e.detail) m = e.detail; } catch (_) {}
            throw new Error(m);
        }
        return res.json();
    }

    // ---------------------- Init ----------------------
    async function init() {
        try {
            state.user = await api('/api/me');
            state.categories = await api('/api/categories');
            document.getElementById('user-name').textContent = state.user.full_name || 'Mijoz';
            renderCategories();
            document.getElementById('loader').classList.add('hidden');
            document.getElementById('tab-home').classList.remove('hidden');
            document.getElementById('bottom-nav').classList.remove('hidden');
            // Chatni fonda yuklab qo'yamiz
            loadMessages().catch(() => {});
        } catch (e) {
            document.getElementById('loader').classList.add('hidden');
            showError(e.message || 'Yuklashda xato');
        }
    }

    // ---------------------- Tab switching ----------------------
    function switchTab(tabName) {
        state.currentTab = tabName;
        ['home', 'cart', 'chat'].forEach(t => {
            document.getElementById('tab-' + t).classList.add('hidden');
        });
        document.getElementById('tab-' + tabName).classList.remove('hidden');
        document.querySelectorAll('.nav-item').forEach(b => {
            b.classList.toggle('active', b.dataset.tab === tabName);
        });
        if (tg.HapticFeedback) tg.HapticFeedback.selectionChanged();

        if (tabName === 'cart') renderCart();
        if (tabName === 'chat') {
            renderMessages();
            scrollChatToBottom();
            startChatPolling();
            // O'qilmagan badgeni tozalash
            const badge = document.getElementById('nav-chat-badge');
            badge.classList.add('hidden');
        } else {
            stopChatPolling();
        }
    }

    function showCategories() {
        state.homeView = 'categories';
        document.getElementById('categories-screen').classList.remove('hidden');
        document.getElementById('products-screen').classList.add('hidden');
    }

    function showProductsView() {
        state.homeView = 'products';
        document.getElementById('categories-screen').classList.add('hidden');
        document.getElementById('products-screen').classList.remove('hidden');
    }

    // ---------------------- Categories ----------------------
    function renderCategories() {
        const grid = document.getElementById('categories-grid');
        if (!state.categories.length) {
            grid.innerHTML = `<div class="empty" style="grid-column:1/-1">
                <div class="empty-icon">🗂</div>Hozircha kategoriyalar yo'q</div>`;
            return;
        }
        grid.innerHTML = state.categories.map(c => `
            <div class="category-card" onclick="App.openCategory(${c.id}, ${JSON.stringify(c.name).replace(/"/g,'&quot;')})">
                <div class="category-image">
                    ${c.image ? `<img src="${c.image}" alt="">`
                              : `<div class="category-image-placeholder">🗂</div>`}
                </div>
                <div class="category-name">${escapeHtml(c.name)}</div>
            </div>
        `).join('');
    }

    async function openCategory(id, name) {
        state.currentCategoryId = id;
        document.getElementById('products-title').textContent = name;
        document.getElementById('products-list').innerHTML =
            `<div class="empty"><div class="empty-icon">⏳</div>Yuklanmoqda...</div>`;
        showProductsView();
        try {
            if (!state.products[id]) {
                state.products[id] = await api(`/api/categories/${id}/products`);
                state.products[id].forEach(p => { state.productsById[p.id] = p; });
            }
            renderProducts(state.products[id]);
        } catch (e) {
            document.getElementById('products-list').innerHTML =
                `<div class="empty"><div class="empty-icon">⚠️</div>${escapeHtml(e.message)}</div>`;
        }
    }

    // ---------------------- Products ----------------------
    function renderProducts(products) {
        const list = document.getElementById('products-list');
        if (!products.length) {
            list.innerHTML = `<div class="empty">
                <div class="empty-icon">📭</div>Bu kategoriyada mahsulot yo'q</div>`;
            return;
        }
        list.innerHTML = products.map(p => productCardHtml(p)).join('');
    }

    function productCardHtml(p) {
        const qty = state.cart[p.id]?.quantity || 0;
        return `
        <div class="product-card" data-pid="${p.id}">
            <div class="product-image">
                ${p.image ? `<img src="${p.image}" alt="">`
                          : `<div class="product-image-placeholder">📦</div>`}
            </div>
            <div class="product-body">
                <h3 class="product-name">${escapeHtml(p.name)}</h3>
                ${p.description ? `<p class="product-desc">${escapeHtml(p.description)}</p>` : ''}
                <div class="product-footer">
                    <div class="product-price">${formatPrice(p.price)} so'm</div>
                    <div class="counter">
                        <button class="counter-btn minus" ${qty === 0 ? 'disabled' : ''}
                                onclick="App.changeQty(${p.id}, -1)">−</button>
                        <div class="counter-value" id="qty-${p.id}">${qty}</div>
                        <button class="counter-btn plus" onclick="App.changeQty(${p.id}, 1)">+</button>
                    </div>
                </div>
            </div>
        </div>`;
    }

    function changeQty(productId, delta) {
        const product = state.productsById[productId];
        if (!product) return;
        const current = state.cart[productId]?.quantity || 0;
        const next = Math.max(0, Math.min(999, current + delta));

        if (next === 0) delete state.cart[productId];
        else state.cart[productId] = { product, quantity: next };

        // Mahsulot kartasi UI'ni yangilash (agar ko'rinib turgan bo'lsa)
        const qtyEl = document.getElementById(`qty-${productId}`);
        if (qtyEl) qtyEl.textContent = next;
        const card = document.querySelector(`.product-card[data-pid="${productId}"]`);
        if (card) {
            const minusBtn = card.querySelector('.counter-btn.minus');
            if (minusBtn) minusBtn.disabled = next === 0;
        }

        updateCartBadge();
        if (state.currentTab === 'cart') renderCart();
        if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
    }

    // ---------------------- Cart ----------------------
    function cartTotals() {
        let count = 0, total = 0;
        for (const { product, quantity } of Object.values(state.cart)) {
            count += quantity;
            total += Number(product.price) * quantity;
        }
        return { count, total };
    }

    function updateCartBadge() {
        const { count } = cartTotals();
        const badge = document.getElementById('nav-cart-badge');
        if (count > 0) {
            badge.textContent = count;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    }

    function renderCart() {
        const list = document.getElementById('cart-list');
        const summary = document.getElementById('cart-summary-card');
        const sub = document.getElementById('cart-sub');
        const items = Object.values(state.cart);

        if (!items.length) {
            list.innerHTML = `<div class="empty">
                <div class="empty-icon">🛒</div>
                <div>Savat bo'sh</div>
                <button class="btn-secondary" style="margin-top:14px" onclick="App.switchTab('home')">Mahsulot qo'shish</button>
            </div>`;
            summary.classList.add('hidden');
            sub.textContent = "Savat hozircha bo'sh";
            return;
        }

        const { count, total } = cartTotals();
        sub.textContent = `Jami ${count} ta mahsulot`;

        list.innerHTML = items.map(({ product, quantity }) => `
            <div class="cart-item" data-pid="${product.id}">
                <div class="cart-item-image">
                    ${product.image ? `<img src="${product.image}" alt="">`
                                    : `<div class="product-image-placeholder">📦</div>`}
                </div>
                <div class="cart-item-body">
                    <div class="cart-item-name">${escapeHtml(product.name)}</div>
                    <div class="cart-item-price">${formatPrice(product.price)} so'm</div>
                    <div class="counter cart-counter">
                        <button class="counter-btn minus" onclick="App.changeQty(${product.id}, -1)">−</button>
                        <div class="counter-value">${quantity}</div>
                        <button class="counter-btn plus" onclick="App.changeQty(${product.id}, 1)">+</button>
                    </div>
                </div>
                <div class="cart-item-total">${formatPrice(product.price * quantity)} so'm</div>
            </div>
        `).join('');

        document.getElementById('cart-sum-items').textContent = `${count} ta`;
        document.getElementById('cart-sum-total').textContent = `${formatPrice(total)} so'm`;
        summary.classList.remove('hidden');
    }

    // ---------------------- Submit order ----------------------
    async function submitOrder() {
        const { count } = cartTotals();
        if (count === 0) return;
        const items = Object.values(state.cart).map(({ product, quantity }) => ({
            product_id: product.id, quantity,
        }));
        const btn = document.querySelector('.btn-order-large');
        btn.disabled = true;
        document.getElementById('order-btn-text').textContent = 'Yuborilmoqda...';
        try {
            const res = await api('/api/orders', { method: 'POST', body: { items } });
            if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
            tg.sendData(JSON.stringify({ order_id: res.order_id }));
            setTimeout(() => tg.close(), 300);
        } catch (e) {
            showToast(e.message || 'Xato yuz berdi');
            btn.disabled = false;
            document.getElementById('order-btn-text').textContent = 'Buyurtma berish';
        }
    }

    // ---------------------- Chat ----------------------
    async function loadMessages() {
        try {
            const msgs = await api('/api/messages');
            state.messages = msgs;
            state.lastMessageId = msgs.length ? Math.max(...msgs.map(m => m.id)) : 0;
            renderMessages();
        } catch (e) {}
    }

    function renderMessages() {
        const win = document.getElementById('chat-window');
        if (!state.messages.length) {
            win.innerHTML = `<div class="empty">
                <div class="empty-icon">💬</div>
                <div>Hali xabar yo'q. Birinchi siz yozing!</div>
            </div>`;
            return;
        }
        win.innerHTML = state.messages.map(m => {
            const t = new Date(m.created_at);
            const hh = String(t.getHours()).padStart(2,'0');
            const mm = String(t.getMinutes()).padStart(2,'0');
            return `<div class="chat-bubble bubble-${m.sender}" data-id="${m.id}">
                <div class="bubble-text">${escapeHtml(m.text)}</div>
                <div class="bubble-time">${hh}:${mm}</div>
            </div>`;
        }).join('');
    }

    function scrollChatToBottom() {
        const win = document.getElementById('chat-window');
        setTimeout(() => { win.scrollTop = win.scrollHeight; }, 50);
    }

    async function sendMessage(ev) {
        ev.preventDefault();
        const inp = document.getElementById('chat-input');
        const text = inp.value.trim();
        if (!text) return;
        inp.disabled = true;
        try {
            const msg = await api('/api/messages', { method: 'POST', body: { text } });
            state.messages.push(msg);
            state.lastMessageId = Math.max(state.lastMessageId, msg.id);
            renderMessages();
            scrollChatToBottom();
            inp.value = '';
        } catch (e) {
            showToast(e.message || 'Xabar yuborilmadi');
        } finally {
            inp.disabled = false;
            inp.focus();
        }
    }

    function startChatPolling() {
        stopChatPolling();
        state.chatPollTimer = setInterval(async () => {
            try {
                const msgs = await api('/api/messages');
                if (msgs.length !== state.messages.length ||
                    (msgs.length && msgs[msgs.length-1].id !== state.lastMessageId)) {
                    state.messages = msgs;
                    state.lastMessageId = msgs.length ? Math.max(...msgs.map(m => m.id)) : 0;
                    renderMessages();
                    scrollChatToBottom();
                }
            } catch (_) {}
        }, 4000);
    }

    function stopChatPolling() {
        if (state.chatPollTimer) {
            clearInterval(state.chatPollTimer);
            state.chatPollTimer = null;
        }
    }

    // ---------------------- Utils ----------------------
    function showToast(text, ms = 3000) {
        const el = document.getElementById('toast');
        el.textContent = text;
        el.classList.remove('hidden');
        clearTimeout(showToast._t);
        showToast._t = setTimeout(() => el.classList.add('hidden'), ms);
    }

    function escapeHtml(s) {
        if (s == null) return '';
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
                        .replace(/"/g,'&quot;').replace(/'/g,'&#039;');
    }

    function formatPrice(n) {
        return new Intl.NumberFormat('uz-UZ').format(Math.round(Number(n) || 0));
    }

    // ---------------------- Public API ----------------------
    window.App = {
        switchTab, showCategories, openCategory, changeQty,
        submitOrder, sendMessage,
    };

    init();
})();
