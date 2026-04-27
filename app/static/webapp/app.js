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

    function hideAllScreens() {
        ['loader', 'error-screen', 'landing-screen', 'tab-home', 'tab-cart', 'tab-chat', 'bottom-nav'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.add('hidden');
        });
    }

    function showError(text, opts = {}) {
        document.getElementById('error-text').textContent = text;
        const r = document.getElementById('btn-reload');
        const c = document.getElementById('btn-close');
        if (r) r.style.display = (opts.showReload !== false) ? '' : 'none';
        if (c) c.style.display = (opts.showClose) ? '' : 'none';
        hideAllScreens();
        document.getElementById('error-screen').classList.remove('hidden');
    }

    function showLanding() {
        hideAllScreens();
        document.getElementById('landing-screen').classList.remove('hidden');
    }

    window.closeWebApp = function () {
        if (window.Telegram?.WebApp) window.Telegram.WebApp.close();
    };

    if (!tg) {
        document.getElementById('loader').classList.add('hidden');
        showLanding();
        return;
    }

    const initData = extractInitData();
    if (!initData) {
        document.getElementById('loader').classList.add('hidden');
        showLanding();
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

            // Server'dan saqlanib qolgan savatni yuklab olish
            await loadCart();

            renderCategories();
            document.getElementById('loader').classList.add('hidden');
            document.getElementById('tab-home').classList.remove('hidden');
            document.getElementById('bottom-nav').classList.remove('hidden');
            updateCartBadge();

            // Chatni fonda yuklab qo'yamiz
            loadMessages().catch(() => {});
        } catch (e) {
            document.getElementById('loader').classList.add('hidden');
            showError(e.message || 'Yuklashda xato');
        }
    }

    async function loadCart() {
        try {
            const items = await api('/api/cart');
            state.cart = {};
            for (const it of items) {
                state.cart[it.product_id] = {
                    product: it.product,
                    quantity: it.quantity,
                };
                state.productsById[it.product.id] = it.product;
            }
        } catch (_) {
            // Savat bo'sh yoki xato — bo'sh holatda davom
            state.cart = {};
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
        if (next === current) return;

        // Optimistic UI update
        if (next === 0) delete state.cart[productId];
        else state.cart[productId] = { product, quantity: next };

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

        // Server'ga sinxronizatsiya
        syncCartItem(productId, next);
    }

    // Bir vaqtda bitta mahsulot uchun bitta so'rov bo'lishi uchun queue
    const _syncQueue = {};
    async function syncCartItem(productId, quantity) {
        // Eskirgan so'rovni almashtirish (eng yangi qiymat saqlanishi uchun)
        _syncQueue[productId] = quantity;
        if (_syncQueue['__busy_' + productId]) return;
        _syncQueue['__busy_' + productId] = true;

        try {
            while (_syncQueue[productId] !== undefined) {
                const target = _syncQueue[productId];
                delete _syncQueue[productId];
                try {
                    await api('/api/cart', {
                        method: 'POST',
                        body: { product_id: productId, quantity: target },
                    });
                } catch (e) {
                    // Xato bo'lsa toast ko'rsatish, lekin UI'ni o'zgartirmaslik
                    showToast('Savat saqlanmadi: ' + (e.message || 'xato'));
                }
            }
        } finally {
            delete _syncQueue['__busy_' + productId];
        }
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

    // ---------------------- Close app ----------------------
    function closeApp() {
        if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');
        tg.close();
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

    // ---------------------- Search ----------------------
    let _searchTimer = null;
    let _searchSeq = 0;

    function onSearchInput(value) {
        const clearBtn = document.getElementById('search-clear');
        if (value && value.length > 0) {
            clearBtn.classList.remove('hidden');
        } else {
            clearBtn.classList.add('hidden');
        }
        clearTimeout(_searchTimer);
        _searchTimer = setTimeout(() => doSearch(value.trim()), 350);
    }

    async function doSearch(query) {
        const grid = document.getElementById('categories-grid');
        const heading = document.getElementById('categories-heading');
        const sub = document.getElementById('categories-sub');
        const results = document.getElementById('search-results');

        if (!query || query.length < 2) {
            // Qidiruv bo'sh — kategoriyalarni qaytaramiz
            grid.classList.remove('hidden');
            results.classList.add('hidden');
            heading.textContent = 'Kategoriyalar';
            sub.textContent = "Kerakli bo'limni tanlang";
            return;
        }

        // Kategoriyalarni yashiramiz, natijalar joyiga loader
        grid.classList.add('hidden');
        heading.textContent = 'Qidiruv natijalari';
        sub.textContent = `«${query}»`;
        results.classList.remove('hidden');
        results.innerHTML = `<div class="empty"><div class="empty-icon">⏳</div>Qidirilmoqda...</div>`;

        const seq = ++_searchSeq;
        try {
            const products = await api(`/api/products/search?q=${encodeURIComponent(query)}`);
            // Eskirgan so'rov javobini e'tiborga olmaymiz
            if (seq !== _searchSeq) return;
            // productsById ga qo'shib qo'yamiz (changeQty ishlashi uchun)
            products.forEach(p => { state.productsById[p.id] = p; });
            renderSearchResults(products, query);
        } catch (e) {
            if (seq !== _searchSeq) return;
            results.innerHTML = `<div class="empty"><div class="empty-icon">⚠️</div>${escapeHtml(e.message)}</div>`;
        }
    }

    function renderSearchResults(products, query) {
        const results = document.getElementById('search-results');
        if (!products.length) {
            results.innerHTML = `<div class="empty">
                <div class="empty-icon">🔎</div>
                <div>«${escapeHtml(query)}» bo'yicha topilmadi</div>
            </div>`;
            return;
        }
        results.innerHTML = products.map(p => productCardHtml(p)).join('');
    }

    function clearSearch() {
        document.getElementById('search-input').value = '';
        document.getElementById('search-clear').classList.add('hidden');
        clearTimeout(_searchTimer);
        _searchSeq++;
        doSearch('');
    }

    // ---------------------- Public API ----------------------
    window.App = {
        switchTab, showCategories, openCategory, changeQty,
        closeApp, sendMessage,
        onSearchInput, clearSearch,
    };

    init();
})();
