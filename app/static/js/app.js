/**
 * HTML Server & Explorer - Client Logic with XSS Protection
 */

document.addEventListener('DOMContentLoaded', () => {
    // State
    const state = {
        currentPath: '',
        items: [],
        viewMode: localStorage.getItem('html_server_view_mode') || 'grid',
        filter: 'all',
        searchQuery: '',
        activeItemForContext: null,
        activeRenameItem: null,
        currentPreviewItem: null
    };

    // Helper: Robust HTML entity escaping to prevent DOM-based XSS
    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // Helper: Safe URL encoding for paths
    function safeUrlPath(path) {
        return encodeURI(path).replace(/'/g, '%27').replace(/"/g, '%22');
    }

    // DOM Elements
    const elements = {
        breadcrumbBar: document.getElementById('breadcrumb-bar'),
        workspaceItemsArea: document.getElementById('workspace-items-area'),
        sidebarFolderTree: document.getElementById('sidebar-folder-tree'),
        sideNavRoot: document.getElementById('side-nav-root'),
        sideTotalCount: document.getElementById('side-total-count'),
        storageUsedSize: document.getElementById('storage-used-size'),
        statHtmlCount: document.getElementById('stat-html-count'),
        statFoldersCount: document.getElementById('stat-folders-count'),
        statFilesCount: document.getElementById('stat-files-count'),
        dropzoneDirLabel: document.getElementById('dropzone-dir-label'),
        quickDropzone: document.getElementById('quick-dropzone'),
        filePickerInput: document.getElementById('file-picker-input'),
        btnOpenFilePicker: document.getElementById('btn-open-file-dialog'),
        btnUploadTop: document.getElementById('btn-upload'),
        btnNewFolderTop: document.getElementById('btn-new-folder'),
        btnRefresh: document.getElementById('btn-refresh'),
        btnSidebarRefreshTree: document.getElementById('btn-sidebar-refresh-tree'),
        btnMobileSidebarToggle: document.getElementById('btn-mobile-sidebar-toggle'),
        btnCloseSidebar: document.getElementById('btn-close-sidebar'),
        sidebarBackdrop: document.getElementById('sidebar-backdrop'),
        appSidebar: document.getElementById('app-sidebar'),
        filterBtnAll: document.getElementById('filter-btn-all'),
        filterBtnHtml: document.getElementById('filter-btn-html'),
        btnViewGrid: document.getElementById('btn-view-grid'),
        btnViewList: document.getElementById('btn-view-list'),
        globalDragOverlay: document.getElementById('global-drag-overlay'),
        dragOverlayPath: document.getElementById('drag-overlay-path'),
        toastStack: document.getElementById('toast-stack'),

        // Command Palette
        btnCmdTrigger: document.getElementById('btn-cmd-trigger'),
        cmdOverlay: document.getElementById('cmd-overlay'),
        cmdInput: document.getElementById('cmd-input'),
        cmdResults: document.getElementById('cmd-results'),

        // Slide-over Drawer (Preview)
        previewDrawerBackdrop: document.getElementById('preview-drawer-backdrop'),
        drawerFilename: document.getElementById('drawer-filename'),
        drawerUrlChip: document.getElementById('drawer-url-chip'),
        drawerUrlText: document.getElementById('drawer-url-text'),
        drawerExtBadge: document.getElementById('drawer-ext-badge'),
        drawerIframeContainer: document.getElementById('drawer-iframe-container'),
        drawerIframe: document.getElementById('drawer-iframe'),
        drawerCodeContainer: document.getElementById('drawer-code-container'),
        drawerCodeBlock: document.getElementById('drawer-code-block'),
        tabLiveView: document.getElementById('tab-live-view'),
        tabCodeView: document.getElementById('tab-code-view'),
        drawerOpenExternal: document.getElementById('drawer-open-external'),
        drawerCloseBtn: document.getElementById('drawer-close-btn'),
        viewportToggles: document.getElementById('viewport-toggles'),

        // Modals
        modalFolderBackdrop: document.getElementById('modal-folder-backdrop'),
        dialogFolderParentPath: document.getElementById('dialog-folder-parent-path'),
        inputNewFolderName: document.getElementById('input-new-folder-name'),
        btnSubmitFolderDialog: document.getElementById('btn-submit-folder-dialog'),
        btnCancelFolderDialog: document.getElementById('btn-cancel-folder-dialog'),
        btnCloseFolderDialog: document.getElementById('btn-close-folder-dialog'),

        modalRenameBackdrop: document.getElementById('modal-rename-backdrop'),
        inputRenameName: document.getElementById('input-rename-name'),
        btnSubmitRenameDialog: document.getElementById('btn-submit-rename-dialog'),
        btnCancelRenameDialog: document.getElementById('btn-cancel-rename-dialog'),
        btnCloseRenameDialog: document.getElementById('btn-close-rename-dialog'),

        // Context Menu
        customContextMenu: document.getElementById('custom-context-menu'),
        ctxOpen: document.getElementById('ctx-open'),
        ctxPreview: document.getElementById('ctx-preview'),
        ctxCopyUrl: document.getElementById('ctx-copy-url'),
        ctxRename: document.getElementById('ctx-rename'),
        ctxDelete: document.getElementById('ctx-delete')
    };

    // Initialize Lucide Icons
    function refreshIcons() {
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    // ==========================================
    // TOAST NOTIFICATIONS (SAFE ESCAPING)
    // ==========================================
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = 'toast-item';
        
        let iconName = 'info';
        let iconColor = '#3b82f6';
        if (type === 'success') {
            iconName = 'check-circle';
            iconColor = '#10b981';
        } else if (type === 'error') {
            iconName = 'alert-circle';
            iconColor = '#ef4444';
        }

        const iconEl = document.createElement('i');
        iconEl.setAttribute('data-lucide', iconName);
        iconEl.style.color = iconColor;
        iconEl.style.width = '16px';
        iconEl.style.height = '16px';

        const spanEl = document.createElement('span');
        spanEl.textContent = String(message);

        toast.appendChild(iconEl);
        toast.appendChild(spanEl);

        elements.toastStack.appendChild(toast);
        refreshIcons();

        setTimeout(() => {
            toast.style.animation = 'toastOut 0.2s forwards';
            setTimeout(() => toast.remove(), 200);
        }, 3200);
    }

    // ==========================================
    // API CALLS
    // ==========================================
    async function apiFetchList(path = '') {
        try {
            const res = await fetch(`/api/explorer/list?path=${encodeURIComponent(path)}`);
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Error al cargar directorio');
            return data.data;
        } catch (err) {
            showToast(err.message, 'error');
            return null;
        }
    }

    async function apiFetchTree() {
        try {
            const res = await fetch('/api/explorer/tree');
            const data = await res.json();
            if (res.ok) return data.tree;
        } catch (err) {
            console.error('Error tree:', err);
        }
        return [];
    }

    async function apiFetchStats() {
        try {
            const res = await fetch('/api/explorer/stats');
            const data = await res.json();
            if (res.ok && data.stats) {
                elements.storageUsedSize.textContent = data.stats.total_size_formatted;
                elements.statHtmlCount.textContent = data.stats.total_html;
                elements.statFoldersCount.textContent = data.stats.total_folders;
                elements.statFilesCount.textContent = data.stats.total_files;
                elements.sideTotalCount.textContent = data.stats.total_files + data.stats.total_folders;
            }
        } catch (err) {
            console.error('Error stats:', err);
        }
    }

    // ==========================================
    // RENDER FUNCTIONS (XSS-PROTECTED)
    // ==========================================
    function renderBreadcrumbs(breadcrumbs) {
        elements.breadcrumbBar.innerHTML = '';
        breadcrumbs.forEach((crumb, idx) => {
            const isLast = idx === breadcrumbs.length - 1;
            const a = document.createElement('a');
            a.href = 'javascript:void(0)';
            a.className = `crumb-link ${isLast ? 'active' : ''}`;
            
            const icon = idx === 0 ? '<i data-lucide="hard-drive" class="w-3.5 h-3.5"></i>' : '<i data-lucide="folder" class="w-3.5 h-3.5"></i>';
            a.innerHTML = `${icon} <span>${escapeHtml(crumb.name)}</span>`;
            a.addEventListener('click', () => navigateTo(crumb.path));
            elements.breadcrumbBar.appendChild(a);

            if (!isLast) {
                const sep = document.createElement('span');
                sep.className = 'crumb-sep';
                sep.textContent = '/';
                elements.breadcrumbBar.appendChild(sep);
            }
        });
        refreshIcons();
    }

    function renderSidebarTree(treeData, container) {
        container.innerHTML = '';
        if (!treeData || treeData.length === 0) {
            container.innerHTML = '<div style="padding: 0.4rem 0.5rem; color: var(--text-muted); font-size: 0.78rem;">Sin subcarpetas</div>';
            return;
        }

        function createTreeNode(node) {
            const wrap = document.createElement('div');
            wrap.className = 'tree-node';

            const item = document.createElement('div');
            item.className = `tree-node-item ${state.currentPath === node.path ? 'active' : ''}`;
            item.innerHTML = `
                <i data-lucide="folder" class="w-3.5 h-3.5"></i>
                <span class="item-label">${escapeHtml(node.name)}</span>
            `;
            item.addEventListener('click', () => navigateTo(node.path));
            wrap.appendChild(item);

            if (node.children && node.children.length > 0) {
                const sub = document.createElement('div');
                sub.className = 'tree-subfolder';
                node.children.forEach(child => sub.appendChild(createTreeNode(child)));
                wrap.appendChild(sub);
            }

            return wrap;
        }

        treeData.forEach(node => container.appendChild(createTreeNode(node)));
        refreshIcons();
    }

    function renderWorkspaceItems() {
        const filtered = state.items.filter(item => {
            if (state.filter === 'html' && !item.is_html && !item.is_dir) return false;
            if (state.searchQuery) {
                return item.name.toLowerCase().includes(state.searchQuery.toLowerCase());
            }
            return true;
        });

        if (filtered.length === 0) {
            elements.workspaceItemsArea.innerHTML = `
                <div class="empty-placeholder">
                    <div class="empty-icon-wrap">
                        <i data-lucide="folder-open" class="w-6 h-6"></i>
                    </div>
                    <div class="empty-title">Esta carpeta está vacía</div>
                    <p class="empty-sub">Crea una subcarpeta o arrastra archivos HTML para comenzar a servirlos inmediatamente.</p>
                </div>
            `;
            refreshIcons();
            return;
        }

        if (state.viewMode === 'grid') {
            renderGridView(filtered);
        } else {
            renderListView(filtered);
        }
        refreshIcons();
    }

    function renderGridView(items) {
        const grid = document.createElement('div');
        grid.className = 'items-grid-container';

        items.forEach(item => {
            const card = document.createElement('div');
            card.className = 'explorer-card';

            const isDir = item.is_dir;
            const isHtml = item.is_html;

            let iconClass = 'file';
            let iconName = 'file-text';
            if (isDir) {
                iconClass = 'folder';
                iconName = 'folder';
            } else if (isHtml) {
                iconClass = 'html';
                iconName = 'code';
            }

            const safeName = escapeHtml(item.name);
            const safeUrl = escapeHtml(item.url);
            const safeHref = safeUrlPath(item.url);
            const safeSize = escapeHtml(item.size_formatted);
            const safeMod = escapeHtml(item.modified);

            card.innerHTML = `
                <div class="card-top-row">
                    <div class="card-icon-box ${iconClass}">
                        <i data-lucide="${iconName}" class="w-5 h-5"></i>
                    </div>
                    <div class="card-info">
                        <div class="card-title-text" title="${safeName}">${safeName}</div>
                        <div class="card-url-chip" title="${safeUrl}">${safeUrl}</div>
                    </div>
                </div>
                <div class="card-meta-row">
                    <span>${safeSize}</span>
                    <span>${safeMod}</span>
                </div>
                <div class="card-actions-row ${isDir ? 'folder-actions' : (isHtml ? 'html-actions' : 'other-actions')}">
                    ${isDir ? `
                        <button class="card-action-btn primary btn-open-folder">
                            <i data-lucide="folder-open" class="w-3.5 h-3.5"></i>
                            <span>Abrir</span>
                        </button>
                    ` : (isHtml ? `
                        <a href="${safeHref}" target="_blank" class="card-action-btn primary" title="Abrir URL directa">
                            <i data-lucide="external-link" class="w-3.5 h-3.5"></i>
                            <span>Ver</span>
                        </a>
                        <button class="card-action-btn btn-open-preview" title="Vista previa interactiva">
                            <i data-lucide="eye" class="w-3.5 h-3.5"></i>
                            <span>Preview</span>
                        </button>
                        <button class="card-action-btn icon-only btn-copy-link" title="Copiar enlace directo">
                            <i data-lucide="copy" class="w-3.5 h-3.5"></i>
                        </button>
                    ` : `
                        <a href="${safeHref}" download class="card-action-btn primary">
                            <i data-lucide="download" class="w-3.5 h-3.5"></i>
                            <span>Descargar</span>
                        </a>
                        <button class="card-action-btn icon-only btn-copy-link" title="Copiar URL">
                            <i data-lucide="copy" class="w-3.5 h-3.5"></i>
                        </button>
                    `)}
                    <button class="card-action-btn icon-only btn-more-actions" title="Más opciones">
                        <i data-lucide="more-horizontal" class="w-3.5 h-3.5"></i>
                    </button>
                </div>
            `;

            // Card Event Listeners
            if (isDir) {
                card.querySelector('.btn-open-folder').addEventListener('click', () => navigateTo(item.path));
                card.querySelector('.card-title-text').addEventListener('click', () => navigateTo(item.path));
            } else {
                const previewBtn = card.querySelector('.btn-open-preview');
                if (previewBtn) previewBtn.addEventListener('click', () => openPreviewDrawer(item));
                
                const copyBtn = card.querySelector('.btn-copy-link');
                if (copyBtn) copyBtn.addEventListener('click', () => copyUrlToClipboard(window.location.origin + item.url));
                
                card.querySelector('.card-title-text').addEventListener('click', () => openPreviewDrawer(item));
            }

            const moreBtn = card.querySelector('.btn-more-actions');
            moreBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                showContextMenu(e.clientX, e.clientY, item);
            });

            card.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                showContextMenu(e.clientX, e.clientY, item);
            });

            grid.appendChild(card);
        });

        elements.workspaceItemsArea.innerHTML = '';
        elements.workspaceItemsArea.appendChild(grid);
    }

    function renderListView(items) {
        const wrap = document.createElement('div');
        wrap.className = 'items-table-wrap';
        wrap.innerHTML = `
            <table class="custom-table">
                <thead>
                    <tr>
                        <th>Nombre</th>
                        <th>Ruta URL</th>
                        <th>Tamaño</th>
                        <th>Fecha de Modificación</th>
                        <th style="text-align: right;">Acciones</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
        `;

        const tbody = wrap.querySelector('tbody');

        items.forEach(item => {
            const tr = document.createElement('tr');
            const isDir = item.is_dir;
            const iconName = isDir ? 'folder' : (item.is_html ? 'code' : 'file-text');

            const safeName = escapeHtml(item.name);
            const safeUrl = escapeHtml(item.url);
            const safeHref = safeUrlPath(item.url);
            const safeSize = escapeHtml(item.size_formatted);
            const safeMod = escapeHtml(item.modified);

            tr.innerHTML = `
                <td>
                    <div class="table-title-cell" style="cursor: ${isDir ? 'pointer' : 'default'};">
                        <i data-lucide="${iconName}" class="w-4 h-4" style="color: ${isDir ? '#60a5fa' : (item.is_html ? '#fb923c' : '#a1a1aa')};"></i>
                        <span>${safeName}</span>
                    </div>
                </td>
                <td><code style="font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-muted);">${safeUrl}</code></td>
                <td>${safeSize}</td>
                <td>${safeMod}</td>
                <td style="text-align: right;">
                    <div style="display: inline-flex; gap: 4px;">
                        ${!isDir ? `
                            <a href="${safeHref}" target="_blank" class="btn btn-ghost" title="Abrir URL"><i data-lucide="external-link" class="w-3.5 h-3.5"></i></a>
                            <button class="btn btn-ghost btn-copy-link" title="Copiar URL"><i data-lucide="copy" class="w-3.5 h-3.5"></i></button>
                        ` : ''}
                        <button class="btn btn-ghost btn-more-actions" title="Opciones"><i data-lucide="more-horizontal" class="w-3.5 h-3.5"></i></button>
                    </div>
                </td>
            `;

            if (isDir) {
                tr.querySelector('.table-title-cell').addEventListener('click', () => navigateTo(item.path));
            } else {
                const copyBtn = tr.querySelector('.btn-copy-link');
                if (copyBtn) copyBtn.addEventListener('click', () => copyUrlToClipboard(window.location.origin + item.url));
            }

            const moreBtn = tr.querySelector('.btn-more-actions');
            moreBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                showContextMenu(e.clientX, e.clientY, item);
            });

            tr.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                showContextMenu(e.clientX, e.clientY, item);
            });

            tbody.appendChild(tr);
        });

        elements.workspaceItemsArea.innerHTML = '';
        elements.workspaceItemsArea.appendChild(wrap);
    }

    // ==========================================
    // MOBILE SIDEBAR CONTROLS
    // ==========================================
    function openMobileSidebar() {
        if (elements.appSidebar) elements.appSidebar.classList.add('open');
        if (elements.sidebarBackdrop) elements.sidebarBackdrop.classList.add('active');
    }

    function closeMobileSidebar() {
        if (elements.appSidebar) elements.appSidebar.classList.remove('open');
        if (elements.sidebarBackdrop) elements.sidebarBackdrop.classList.remove('active');
    }

    // ==========================================
    // NAVIGATION & STATE
    // ==========================================
    async function navigateTo(path = '') {
        state.currentPath = path;
        elements.dropzoneDirLabel.textContent = path ? `/${path}` : '/';
        elements.dragOverlayPath.textContent = path ? `/${path}` : '/';

        // Auto close mobile sidebar on navigation
        closeMobileSidebar();

        const data = await apiFetchList(path);
        if (data) {
            state.items = data.items;
            renderBreadcrumbs(data.breadcrumbs);
            renderWorkspaceItems();
        }

        if (path === '') {
            elements.sideNavRoot.classList.add('active');
        } else {
            elements.sideNavRoot.classList.remove('active');
        }

        await refreshTreeAndStats();
    }

    async function refreshTreeAndStats() {
        const tree = await apiFetchTree();
        renderSidebarTree(tree, elements.sidebarFolderTree);
        await apiFetchStats();
    }

    function copyUrlToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            showToast(`URL copiada al portapapeles: ${text}`, 'success');
        }).catch(() => {
            const ta = document.createElement('textarea');
            ta.value = text;
            document.body.appendChild(ta);
            ta.select();
            document.execCommand('copy');
            document.body.removeChild(ta);
            showToast(`URL copiada: ${text}`, 'success');
        });
    }

    // ==========================================
    // UPLOAD FILES
    // ==========================================
    async function uploadFiles(fileList) {
        if (!fileList || fileList.length === 0) return;

        const formData = new FormData();
        formData.append('path', state.currentPath);
        for (let i = 0; i < fileList.length; i++) {
            formData.append('files', fileList[i]);
        }

        showToast(`Subiendo ${fileList.length} archivo(s)...`, 'info');

        try {
            const res = await fetch('/api/explorer/upload', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();

            if (res.ok && data.success) {
                showToast(data.message, 'success');
                await navigateTo(state.currentPath);
            } else {
                showToast(data.message || 'Error en la subida', 'error');
            }
        } catch (err) {
            showToast(`Error al subir: ${err.message}`, 'error');
        }
    }

    // ==========================================
    // CONTEXT MENU
    // ==========================================
    function showContextMenu(x, y, item) {
        state.activeItemForContext = item;
        const menu = elements.customContextMenu;
        menu.style.display = 'flex';

        // Safe positioning within mobile and desktop viewport
        const menuWidth = 190;
        const menuHeight = 220;
        const posX = Math.max(10, Math.min(x, window.innerWidth - menuWidth - 10));
        const posY = Math.max(10, Math.min(y, window.innerHeight - menuHeight - 10));

        menu.style.left = `${posX}px`;
        menu.style.top = `${posY}px`;

        if (item.is_dir) {
            elements.ctxOpen.style.display = 'flex';
            elements.ctxPreview.style.display = 'none';
        } else {
            elements.ctxOpen.style.display = 'flex';
            elements.ctxPreview.style.display = 'flex';
        }
    }

    function hideContextMenu() {
        elements.customContextMenu.style.display = 'none';
    }

    document.addEventListener('click', hideContextMenu);

    elements.ctxOpen.addEventListener('click', () => {
        if (!state.activeItemForContext) return;
        if (state.activeItemForContext.is_dir) {
            navigateTo(state.activeItemForContext.path);
        } else {
            window.open(state.activeItemForContext.url, '_blank');
        }
    });

    elements.ctxPreview.addEventListener('click', () => {
        if (state.activeItemForContext && !state.activeItemForContext.is_dir) {
            openPreviewDrawer(state.activeItemForContext);
        }
    });

    elements.ctxCopyUrl.addEventListener('click', () => {
        if (state.activeItemForContext) {
            copyUrlToClipboard(window.location.origin + state.activeItemForContext.url);
        }
    });

    elements.ctxRename.addEventListener('click', () => {
        if (state.activeItemForContext) {
            openRenameDialog(state.activeItemForContext);
        }
    });

    elements.ctxDelete.addEventListener('click', () => {
        if (state.activeItemForContext) {
            confirmDelete(state.activeItemForContext);
        }
    });

    // ==========================================
    // PREVIEW DRAWER (SAFE)
    // ==========================================
    async function openPreviewDrawer(item) {
        state.currentPreviewItem = item;
        elements.drawerFilename.textContent = item.name;
        elements.drawerUrlText.textContent = item.url;
        elements.drawerExtBadge.textContent = (item.extension || 'HTML').toUpperCase().replace('.', '');
        elements.drawerOpenExternal.href = safeUrlPath(item.url);

        // Reset views
        elements.drawerIframeContainer.style.width = '100%';
        elements.tabLiveView.classList.add('active');
        elements.tabCodeView.classList.remove('active');
        elements.drawerIframeContainer.style.display = 'flex';
        elements.drawerCodeContainer.style.display = 'none';

        // Load iframe securely
        elements.drawerIframe.src = safeUrlPath(item.url);

        // Load code block safely
        try {
            const res = await fetch(`/api/explorer/file-content?path=${encodeURIComponent(item.path)}`);
            const data = await res.json();
            if (res.ok && data.data) {
                elements.drawerCodeBlock.textContent = data.data.content;
                if (window.hljs) {
                    window.hljs.highlightElement(elements.drawerCodeBlock);
                }
            }
        } catch (err) {
            elements.drawerCodeBlock.textContent = '// No se pudo cargar el código fuente.';
        }

        elements.previewDrawerBackdrop.classList.add('active');
        refreshIcons();
    }

    elements.drawerCloseBtn.addEventListener('click', () => {
        elements.previewDrawerBackdrop.classList.remove('active');
        elements.drawerIframe.src = 'about:blank';
    });

    elements.drawerUrlChip.addEventListener('click', () => {
        if (state.currentPreviewItem) {
            copyUrlToClipboard(window.location.origin + state.currentPreviewItem.url);
        }
    });

    elements.tabLiveView.addEventListener('click', () => {
        elements.tabLiveView.classList.add('active');
        elements.tabCodeView.classList.remove('active');
        elements.drawerIframeContainer.style.display = 'flex';
        elements.drawerCodeContainer.style.display = 'none';
    });

    elements.tabCodeView.addEventListener('click', () => {
        elements.tabCodeView.classList.add('active');
        elements.tabLiveView.classList.remove('active');
        elements.drawerIframeContainer.style.display = 'none';
        elements.drawerCodeContainer.style.display = 'block';
    });

    elements.viewportToggles.querySelectorAll('.vp-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            elements.viewportToggles.querySelectorAll('.vp-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            elements.drawerIframeContainer.style.width = btn.dataset.width;
        });
    });

    // ==========================================
    // CREATE FOLDER & RENAME DIALOGS
    // ==========================================
    function openFolderDialog() {
        elements.dialogFolderParentPath.textContent = state.currentPath ? `/${state.currentPath}` : '/';
        elements.inputNewFolderName.value = '';
        elements.modalFolderBackdrop.classList.add('active');
        setTimeout(() => elements.inputNewFolderName.focus(), 50);
    }

    async function submitFolderDialog() {
        const name = elements.inputNewFolderName.value.trim();
        if (!name) {
            showToast('Escribe un nombre para la carpeta', 'error');
            return;
        }

        try {
            const res = await fetch('/api/explorer/folders', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: state.currentPath, name })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Error al crear carpeta');

            showToast(data.data.message, 'success');
            elements.modalFolderBackdrop.classList.remove('active');
            await navigateTo(state.currentPath);
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    function openRenameDialog(item) {
        state.activeRenameItem = item;
        elements.inputRenameName.value = item.name;
        elements.modalRenameBackdrop.classList.add('active');
        setTimeout(() => elements.inputRenameName.focus(), 50);
    }

    async function submitRenameDialog() {
        if (!state.activeRenameItem) return;
        const newName = elements.inputRenameName.value.trim();
        if (!newName) {
            showToast('El nombre no puede estar vacío', 'error');
            return;
        }

        try {
            const res = await fetch('/api/explorer/rename', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: state.activeRenameItem.path, new_name: newName })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Error al renombrar');

            showToast(data.data.message, 'success');
            elements.modalRenameBackdrop.classList.remove('active');
            state.activeRenameItem = null;
            await navigateTo(state.currentPath);
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    async function confirmDelete(item) {
        const msg = item.is_dir 
            ? `¿Eliminar permanentemente la carpeta "${item.name}" y todo su contenido?`
            : `¿Eliminar permanentemente el archivo "${item.name}"?`;

        if (!confirm(msg)) return;

        try {
            const res = await fetch('/api/explorer/items', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: item.path })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Error al eliminar');

            showToast(data.data.message, 'success');
            await navigateTo(state.currentPath);
        } catch (err) {
            showToast(err.message, 'error');
        }
    }

    // ==========================================
    // COMMAND PALETTE (CMD+K)
    // ==========================================
    function openCommandPalette() {
        elements.cmdInput.value = '';
        renderCmdResults('');
        elements.cmdOverlay.classList.add('active');
        setTimeout(() => elements.cmdInput.focus(), 50);
    }

    function closeCommandPalette() {
        elements.cmdOverlay.classList.remove('active');
    }

    function renderCmdResults(query) {
        const results = elements.cmdResults;
        results.innerHTML = '';

        const matched = state.items.filter(item => {
            if (!query) return true;
            return item.name.toLowerCase().includes(query.toLowerCase()) || item.url.toLowerCase().includes(query.toLowerCase());
        });

        if (matched.length === 0) {
            results.innerHTML = '<div style="padding: 1rem; text-align: center; color: var(--text-muted); font-size: 0.82rem;">No se encontraron resultados</div>';
            return;
        }

        matched.forEach(item => {
            const el = document.createElement('div');
            el.className = 'cmd-item';
            const iconName = item.is_dir ? 'folder' : (item.is_html ? 'code' : 'file-text');
            el.innerHTML = `
                <i data-lucide="${iconName}" class="w-4 h-4"></i>
                <span class="cmd-item-label">${escapeHtml(item.name)}</span>
                <span class="cmd-item-path">${escapeHtml(item.url)}</span>
            `;

            el.addEventListener('click', () => {
                closeCommandPalette();
                if (item.is_dir) {
                    navigateTo(item.path);
                } else {
                    openPreviewDrawer(item);
                }
            });

            results.appendChild(el);
        });

        refreshIcons();
    }

    elements.btnCmdTrigger.addEventListener('click', openCommandPalette);
    elements.cmdInput.addEventListener('input', (e) => renderCmdResults(e.target.value));

    // ==========================================
    // EVENT LISTENERS & SHORTCUTS
    // ==========================================
    elements.btnNewFolderTop.addEventListener('click', openFolderDialog);
    elements.btnSubmitFolderDialog.addEventListener('click', submitFolderDialog);
    elements.btnCloseFolderDialog.addEventListener('click', () => elements.modalFolderBackdrop.classList.remove('active'));
    elements.btnCancelFolderDialog.addEventListener('click', () => elements.modalFolderBackdrop.classList.remove('active'));
    elements.inputNewFolderName.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') submitFolderDialog();
    });

    elements.btnSubmitRenameDialog.addEventListener('click', submitRenameDialog);
    elements.btnCloseRenameDialog.addEventListener('click', () => elements.modalRenameBackdrop.classList.remove('active'));
    elements.btnCancelRenameDialog.addEventListener('click', () => elements.modalRenameBackdrop.classList.remove('active'));
    elements.inputRenameName.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') submitRenameDialog();
    });

    elements.btnUploadTop.addEventListener('click', () => elements.filePickerInput.click());
    elements.btnOpenFilePicker.addEventListener('click', () => elements.filePickerInput.click());
    elements.filePickerInput.addEventListener('change', (e) => {
        uploadFiles(e.target.files);
        elements.filePickerInput.value = '';
    });

    elements.btnRefresh.addEventListener('click', () => navigateTo(state.currentPath));
    elements.btnSidebarRefreshTree.addEventListener('click', refreshTreeAndStats);
    elements.sideNavRoot.addEventListener('click', () => navigateTo(''));

    // Mobile Sidebar Drawer Events
    if (elements.btnMobileSidebarToggle) {
        elements.btnMobileSidebarToggle.addEventListener('click', openMobileSidebar);
    }
    if (elements.btnCloseSidebar) {
        elements.btnCloseSidebar.addEventListener('click', closeMobileSidebar);
    }
    if (elements.sidebarBackdrop) {
        elements.sidebarBackdrop.addEventListener('click', closeMobileSidebar);
    }

    // Filter controls
    elements.filterBtnAll.addEventListener('click', () => {
        elements.filterBtnAll.classList.add('active');
        elements.filterBtnHtml.classList.remove('active');
        state.filter = 'all';
        renderWorkspaceItems();
    });

    elements.filterBtnHtml.addEventListener('click', () => {
        elements.filterBtnHtml.classList.add('active');
        elements.filterBtnAll.classList.remove('active');
        state.filter = 'html';
        renderWorkspaceItems();
    });

    // View switcher
    elements.btnViewGrid.addEventListener('click', () => {
        elements.btnViewGrid.classList.add('active');
        elements.btnViewList.classList.remove('active');
        state.viewMode = 'grid';
        localStorage.setItem('html_server_view_mode', 'grid');
        renderWorkspaceItems();
    });

    elements.btnViewList.addEventListener('click', () => {
        elements.btnViewList.classList.add('active');
        elements.btnViewGrid.classList.remove('active');
        state.viewMode = 'list';
        localStorage.setItem('html_server_view_mode', 'list');
        renderWorkspaceItems();
    });

    // Full screen drag and drop
    let dragCounter = 0;
    window.addEventListener('dragenter', (e) => {
        e.preventDefault();
        dragCounter++;
        if (dragCounter === 1) {
            elements.globalDragOverlay.classList.add('active');
        }
    });

    window.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dragCounter--;
        if (dragCounter <= 0) {
            dragCounter = 0;
            elements.globalDragOverlay.classList.remove('active');
        }
    });

    window.addEventListener('dragover', (e) => e.preventDefault());

    window.addEventListener('drop', (e) => {
        e.preventDefault();
        dragCounter = 0;
        elements.globalDragOverlay.classList.remove('active');
        if (e.dataTransfer && e.dataTransfer.files.length > 0) {
            uploadFiles(e.dataTransfer.files);
        }
    });

    // Keyboard Shortcuts
    window.addEventListener('keydown', (e) => {
        const isTyping = e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA';

        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            openCommandPalette();
            return;
        }

        if (e.key === 'Escape') {
            elements.modalFolderBackdrop.classList.remove('active');
            elements.modalRenameBackdrop.classList.remove('active');
            elements.previewDrawerBackdrop.classList.remove('active');
            closeMobileSidebar();
            closeCommandPalette();
            hideContextMenu();
            return;
        }

        if (!isTyping) {
            if (e.key === '/') {
                e.preventDefault();
                openCommandPalette();
            } else if (e.key.toLowerCase() === 'n') {
                e.preventDefault();
                openFolderDialog();
            } else if (e.key.toLowerCase() === 'u') {
                e.preventDefault();
                elements.filePickerInput.click();
            } else if (e.key.toLowerCase() === 'r') {
                e.preventDefault();
                navigateTo(state.currentPath);
            }
        }
    });

    // Init
    if (state.viewMode === 'list') {
        elements.btnViewList.classList.add('active');
        elements.btnViewGrid.classList.remove('active');
    }
    navigateTo('');
});
