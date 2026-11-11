/**
 * PantryMate – script.js
 * All frontend logic: API calls, rendering, modals, toasts, navigation.
 */

'use strict';

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  currentView: 'dashboard',
  editingId:   null,
  confirmCallback: null,
  searchTimer: null,
};

// ── API helpers ───────────────────────────────────────────────────────────────
const BASE = '';   // same origin

async function apiFetch(path, options = {}) {
  const defaults = {
    headers: { 'Content-Type': 'application/json' },
  };
  const res = await fetch(BASE + path, { ...defaults, ...options });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = body.error || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return body;
}

// ── Navigation ────────────────────────────────────────────────────────────────
function showView(view) {
  // deactivate all views and nav links
  document.querySelectorAll('.view').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

  document.getElementById(`view-${view}`).classList.add('active');
  document.getElementById(`nav-${view}`)?.classList.add('active');
  document.getElementById('topbar-title').textContent = {
    dashboard: 'Dashboard',
    pantry:    'My Pantry',
    expiring:  'Expiring Soon',
    expired:   'Expired Items',
  }[view] || 'PantryMate';

  state.currentView = view;
  closeSidebarOnMobile();

  // load data for the view
  if (view === 'dashboard') loadDashboard();
  else if (view === 'pantry') loadItems();
  else if (view === 'expiring') loadFilteredItems('expiring-grid', 'expiring_soon');
  else if (view === 'expired')  loadFilteredItems('expired-grid',  'expired');

  return false;
}

// ── Sidebar (mobile) ──────────────────────────────────────────────────────────
function toggleSidebar() {
  const sidebar  = document.getElementById('sidebar');
  const overlay  = getOrCreateSidebarOverlay();
  sidebar.classList.toggle('open');
  overlay.classList.toggle('show');
}

function closeSidebarOnMobile() {
  if (window.innerWidth <= 700) {
    document.getElementById('sidebar').classList.remove('open');
    const overlay = document.querySelector('.sidebar-overlay');
    if (overlay) overlay.classList.remove('show');
  }
}

function getOrCreateSidebarOverlay() {
  let o = document.querySelector('.sidebar-overlay');
  if (!o) {
    o = document.createElement('div');
    o.className = 'sidebar-overlay';
    o.onclick = () => {
      document.getElementById('sidebar').classList.remove('open');
      o.classList.remove('show');
    };
    document.body.appendChild(o);
  }
  return o;
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
async function loadDashboard() {
  try {
    const data = await apiFetch('/api/dashboard');
    document.getElementById('stat-val-total').textContent    = data.total;
    document.getElementById('stat-val-fresh').textContent    = data.fresh;
    document.getElementById('stat-val-expiring').textContent = data.expiring_soon;
    document.getElementById('stat-val-today').textContent    = data.expires_today;
    document.getElementById('stat-val-expired').textContent  = data.expired;

    // Update sidebar badges
    document.getElementById('expiring-badge').textContent = data.expiring_soon + data.expires_today;
    document.getElementById('expired-badge').textContent  = data.expired;

    // Load attention items (expiring + expired + today)
    const attentionRes = await apiFetch('/api/items');
    const attention = attentionRes.items.filter(i =>
      i.status === 'expiring_soon' || i.status === 'expired' || i.status === 'expires_today'
    ).slice(0, 8);

    renderItemsGrid('dashboard-attention-grid', attention, {
      emptyIcon: '🎉',
      emptyMsg: 'All pantry items are fresh — great job!',
    });
  } catch (err) {
    showToast('Failed to load dashboard: ' + err.message, 'error');
  }
}

// ── Pantry Items ──────────────────────────────────────────────────────────────
async function loadItems() {
  const search   = document.getElementById('search-input').value.trim();
  const category = document.getElementById('filter-category').value;
  const status   = document.getElementById('filter-status').value;

  const params = new URLSearchParams();
  if (search)              params.set('search', search);
  if (category !== 'all')  params.set('category', category);
  if (status   !== 'all')  params.set('status', status);

  try {
    const data = await apiFetch('/api/items?' + params.toString());
    renderItemsGrid('pantry-grid', data.items, {
      emptyIcon: '🧺',
      emptyMsg:  'No items found. Add some pantry items!',
    });
  } catch (err) {
    showToast('Failed to load items: ' + err.message, 'error');
  }
}

async function loadFilteredItems(gridId, statusFilter) {
  try {
    const data = await apiFetch('/api/items?status=' + statusFilter);
    const emptyTexts = {
      expiring_soon: { icon: '✅', msg: 'No items expiring within 7 days — well stocked!' },
      expired:       { icon: '🎉', msg: 'No expired items — pantry is clean!' },
    };
    const e = emptyTexts[statusFilter] || { icon: '📦', msg: 'No items found.' };
    renderItemsGrid(gridId, data.items, { emptyIcon: e.icon, emptyMsg: e.msg });
  } catch (err) {
    showToast('Failed to load items: ' + err.message, 'error');
  }
}

// ── Render helpers ────────────────────────────────────────────────────────────
const CATEGORY_ICONS = {
  'Dairy':           '🥛',
  'Meat & Seafood':  '🥩',
  'Fruits':          '🍎',
  'Vegetables':      '🥦',
  'Grains & Bread':  '🍞',
  'Beverages':       '🥤',
  'Snacks':          '🍿',
  'Condiments':      '🧂',
  'Frozen':          '🧊',
  'Canned Goods':    '🥫',
  'Spices & Herbs':  '🌿',
  'Bakery':          '🥐',
  'Other':           '📦',
};

const STATUS_LABELS = {
  fresh:         { label: '✅ Fresh',          cls: 'badge-fresh' },
  expiring_soon: { label: '⚠️ Expiring Soon',  cls: 'badge-expiring_soon' },
  expires_today: { label: '📅 Expires Today',  cls: 'badge-expires_today' },
  expired:       { label: '🚫 Expired',         cls: 'badge-expired' },
};

function formatDate(dateStr) {
  if (!dateStr) return '—';
  const [y, m, d] = dateStr.split('-');
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${d} ${months[+m-1]} ${y}`;
}

function daysLabel(item) {
  const d = item.days_remaining;
  if (d === null || d === undefined) return '';
  if (d < 0) return `${Math.abs(d)} day${Math.abs(d)!==1?'s':''} ago`;
  if (d === 0) return 'Today';
  return `${d} day${d!==1?'s':''} left`;
}

function buildItemCard(item) {
  const statusInfo = STATUS_LABELS[item.status] || { label: item.status, cls: '' };
  const catIcon    = CATEGORY_ICONS[item.category] || '📦';
  const daysText   = daysLabel(item);

  return `
    <div class="item-card ${item.status}" data-id="${item.id}">
      <div class="card-body">
        <div class="card-top">
          <div class="card-name">${escHtml(item.item_name)}</div>
          <span class="status-badge ${statusInfo.cls}">${statusInfo.label}</span>
        </div>
        <div class="card-meta">
          <span class="meta-chip">${catIcon} ${escHtml(item.category || 'Other')}</span>
          <span class="meta-chip">📏 ${item.quantity} ${escHtml(item.unit || 'pcs')}</span>
        </div>
        <div class="card-dates">
          ${item.purchase_date ? `
          <div class="date-row">
            <span>Purchased</span>
            <strong>${formatDate(item.purchase_date)}</strong>
          </div>` : ''}
          <div class="date-row">
            <span>Expires</span>
            <strong>${formatDate(item.expiry_date)}</strong>
            ${daysText ? `<span class="days-pill days-${item.status}">${daysText}</span>` : ''}
          </div>
        </div>
      </div>
      <div class="card-actions">
        <button class="action-btn btn-consume"
          onclick="confirmConsume(${item.id}, '${escAttr(item.item_name)}')"
          title="Mark as consumed">
          ✅ Consumed
        </button>
        <button class="action-btn btn-edit"
          onclick="openEditModal(${item.id})"
          title="Edit item">
          ✏️ Edit
        </button>
        <button class="action-btn btn-delete"
          onclick="confirmDelete(${item.id}, '${escAttr(item.item_name)}')"
          title="Delete item">
          🗑️ Delete
        </button>
      </div>
    </div>`;
}

function renderItemsGrid(gridId, items, { emptyIcon = '📦', emptyMsg = 'No items.' } = {}) {
  const grid = document.getElementById(gridId);
  if (!grid) return;

  if (!items || items.length === 0) {
    grid.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">${emptyIcon}</div>
        <p>${emptyMsg}</p>
      </div>`;
    return;
  }
  grid.innerHTML = items.map(buildItemCard).join('');
}

// ── Search ────────────────────────────────────────────────────────────────────
function handleSearch() {
  const val = document.getElementById('search-input').value;
  document.getElementById('clear-search').style.display = val ? 'flex' : 'none';

  clearTimeout(state.searchTimer);
  state.searchTimer = setTimeout(loadItems, 300);
}

function clearSearch() {
  document.getElementById('search-input').value = '';
  document.getElementById('clear-search').style.display = 'none';
  loadItems();
}

// ── Modal ─────────────────────────────────────────────────────────────────────
function openAddModal() {
  state.editingId = null;
  document.getElementById('modal-title').textContent = 'Add New Item';
  document.getElementById('form-submit-btn').textContent = 'Add Item';
  resetForm();
  openModal('modal-overlay');
}

async function openEditModal(id) {
  try {
    // Fetch single item by getting all and finding by id (simple approach)
    const data = await apiFetch('/api/items');
    const item = data.items.find(i => i.id === id);
    if (!item) { showToast('Item not found.', 'error'); return; }

    state.editingId = id;
    document.getElementById('modal-title').textContent = 'Edit Item';
    document.getElementById('form-submit-btn').textContent = 'Save Changes';
    resetForm();

    document.getElementById('f-item-name').value    = item.item_name || '';
    document.getElementById('f-category').value     = item.category || 'Other';
    document.getElementById('f-quantity').value     = item.quantity ?? 1;
    document.getElementById('f-unit').value         = item.unit || 'pcs';
    document.getElementById('f-purchase-date').value= item.purchase_date || '';
    document.getElementById('f-expiry-date').value  = item.expiry_date || '';

    openModal('modal-overlay');
  } catch (err) {
    showToast('Failed to load item: ' + err.message, 'error');
  }
}

function openModal(overlayId) {
  document.getElementById(overlayId).classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('open');
  document.body.style.overflow = '';
  resetForm();
}

function closeModalOnOverlay(event) {
  if (event.target === document.getElementById('modal-overlay')) closeModal();
}

function resetForm() {
  document.getElementById('item-form').reset();
  document.querySelectorAll('.field-error').forEach(el => el.textContent = '');
  document.querySelectorAll('.form-group input, .form-group select')
    .forEach(el => el.classList.remove('error'));
}

// ── Form submission ───────────────────────────────────────────────────────────
async function submitItemForm(event) {
  event.preventDefault();

  const itemName   = document.getElementById('f-item-name').value.trim();
  const category   = document.getElementById('f-category').value;
  const quantity   = parseFloat(document.getElementById('f-quantity').value);
  const unit       = document.getElementById('f-unit').value;
  const purchDate  = document.getElementById('f-purchase-date').value;
  const expiryDate = document.getElementById('f-expiry-date').value;

  // Client-side validation
  let valid = true;

  if (!itemName) {
    setFieldError('f-item-name', 'err-item-name', 'Item name is required.');
    valid = false;
  } else {
    clearFieldError('f-item-name', 'err-item-name');
  }

  if (!quantity || quantity <= 0 || isNaN(quantity)) {
    setFieldError('f-quantity', 'err-quantity', 'Enter a valid positive quantity.');
    valid = false;
  } else {
    clearFieldError('f-quantity', 'err-quantity');
  }

  if (!expiryDate) {
    setFieldError('f-expiry-date', 'err-expiry-date', 'Expiry date is required.');
    valid = false;
  } else {
    clearFieldError('f-expiry-date', 'err-expiry-date');
  }

  if (!valid) return;

  const payload = {
    item_name:     itemName,
    category,
    quantity,
    unit,
    purchase_date: purchDate || null,
    expiry_date:   expiryDate,
  };

  const submitBtn = document.getElementById('form-submit-btn');
  submitBtn.disabled = true;
  submitBtn.textContent = 'Saving…';

  try {
    if (state.editingId) {
      await apiFetch(`/api/items/${state.editingId}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      showToast('Item updated successfully! ✏️');
    } else {
      await apiFetch('/api/items', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      showToast('Item added to pantry! ✅');
    }

    closeModal();
    // Refresh current view
    if (state.currentView === 'dashboard') loadDashboard();
    else if (state.currentView === 'pantry') loadItems();
    else if (state.currentView === 'expiring') { loadFilteredItems('expiring-grid', 'expiring_soon'); loadDashboard(); }
    else if (state.currentView === 'expired')  { loadFilteredItems('expired-grid', 'expired'); loadDashboard(); }

    // Always keep dashboard stats fresh
    loadDashboard();
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = state.editingId ? 'Save Changes' : 'Add Item';
  }
}

function setFieldError(inputId, errId, msg) {
  document.getElementById(inputId)?.classList.add('error');
  const e = document.getElementById(errId);
  if (e) e.textContent = msg;
}

function clearFieldError(inputId, errId) {
  document.getElementById(inputId)?.classList.remove('error');
  const e = document.getElementById(errId);
  if (e) e.textContent = '';
}

// ── Confirm dialog ────────────────────────────────────────────────────────────
function showConfirm(title, message, okLabel, okClass, callback) {
  document.getElementById('confirm-title').textContent   = title;
  document.getElementById('confirm-message').textContent = message;
  const btn = document.getElementById('confirm-ok-btn');
  btn.textContent = okLabel;
  btn.className   = `btn-${okClass}`;
  state.confirmCallback = callback;
  openModal('confirm-overlay');
}

function executeConfirm() {
  cancelConfirm();
  if (typeof state.confirmCallback === 'function') state.confirmCallback();
  state.confirmCallback = null;
}

function cancelConfirm() {
  document.getElementById('confirm-overlay').classList.remove('open');
  document.body.style.overflow = '';
}

function confirmDelete(id, name) {
  showConfirm(
    'Delete Item',
    `Are you sure you want to permanently delete "${name}"? This cannot be undone.`,
    'Delete',
    'danger',
    () => deleteItem(id)
  );
}

function confirmConsume(id, name) {
  showConfirm(
    'Mark as Consumed',
    `Mark "${name}" as consumed and remove it from your pantry?`,
    'Mark Consumed',
    'primary',
    () => consumeItem(id)
  );
}

// ── API actions ───────────────────────────────────────────────────────────────
async function deleteItem(id) {
  try {
    await apiFetch(`/api/items/${id}`, { method: 'DELETE' });
    showToast('Item deleted. 🗑️', 'warning');
    refreshCurrentView();
    loadDashboard();
  } catch (err) {
    showToast('Delete failed: ' + err.message, 'error');
  }
}

async function consumeItem(id) {
  try {
    await apiFetch(`/api/items/${id}/consume`, { method: 'PATCH' });
    showToast('Item marked as consumed! 🍽️');
    refreshCurrentView();
    loadDashboard();
  } catch (err) {
    showToast('Action failed: ' + err.message, 'error');
  }
}

function refreshCurrentView() {
  const v = state.currentView;
  if (v === 'dashboard') loadDashboard();
  else if (v === 'pantry')    loadItems();
  else if (v === 'expiring') loadFilteredItems('expiring-grid', 'expiring_soon');
  else if (v === 'expired')  loadFilteredItems('expired-grid',  'expired');
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, type = 'success') {
  const container = document.getElementById('toast-container');
  const toast     = document.createElement('div');
  toast.className = `toast${type !== 'success' ? ' ' + type : ''}`;
  const icons     = { success: '✅', error: '❌', warning: '⚠️' };
  toast.innerHTML = `<span>${icons[type] || '✅'}</span><span>${escHtml(msg)}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.classList.add('removing');
    setTimeout(() => toast.remove(), 280);
  }, 3500);
}

// ── Escape helpers ────────────────────────────────────────────────────────────
function escHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escAttr(str) {
  return String(str || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  showView('dashboard');

  // Close sidebar on resize to desktop
  window.addEventListener('resize', () => {
    if (window.innerWidth > 700) {
      document.getElementById('sidebar').classList.remove('open');
      const overlay = document.querySelector('.sidebar-overlay');
      if (overlay) overlay.classList.remove('show');
    }
  });
});
