// Camera AI-VMD Manager - Frontend JavaScript

const API_BASE = '/api';

// State
let currentGroups = [];
let currentCameras = [];
let currentUsers = [];
let systemStatus = {};
let availableAIApps = {};
let currentUser = null;

// Initialize application
document.addEventListener('DOMContentLoaded', async () => {
    // Check authentication
    await checkAuth();
    
    // Initialize UI
    loadSystemStatus();
    loadGroups();
    loadCameras();
    loadCredentialsStatus();
    loadAIApps();
    setupForms();
    
    // Load dashboard by default
    loadDashboard();
    
    // Load users if admin
    if (currentUser && currentUser.role === 'admin') {
        loadUsers();
    }
});

// Authentication
async function checkAuth() {
    try {
        const response = await fetch('/api/auth/check');
        const data = await response.json();
        
        if (!data.authenticated) {
            window.location.href = '/login';
            return;
        }
        
        currentUser = data.user;
        updateUserInfo();
        
    } catch (error) {
        console.error('Auth check failed:', error);
        window.location.href = '/login';
    }
}

function updateUserInfo() {
    if (!currentUser) return;
    
    document.getElementById('currentUsername').textContent = currentUser.username;
    document.getElementById('currentUserRole').textContent = currentUser.role;
    
    // Show/hide admin-only elements
    const adminElements = document.querySelectorAll('.admin-only');
    adminElements.forEach(el => {
        el.style.display = currentUser.role === 'admin' ? '' : 'none';
    });
}

async function logout() {
    if (!confirm('Are you sure you want to logout?')) {
        return;
    }
    
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
        window.location.href = '/login';
    } catch (error) {
        console.error('Logout error:', error);
        window.location.href = '/login';
    }
}

// Tab Management
function switchTab(tabName) {
    // Update nav items
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.classList.remove('active');
    });
    const activeNav = document.querySelector(`[data-tab="${tabName}"]`);
    if (activeNav) {
        activeNav.classList.add('active');
    }
    
    // Update content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    const activeTab = document.getElementById(tabName);
    if (activeTab) {
        activeTab.classList.add('active');
    }
    
    // Load tab-specific data
    if (tabName === 'dashboard') {
        loadDashboard();
    } else if (tabName === 'groups') {
        loadGroups();
    } else if (tabName === 'activity') {
        loadActivityLog();
    } else if (tabName === 'cameras') {
        loadCameras();
    } else if (tabName === 'credentials') {
        loadCredentialsStatus();
    } else if (tabName === 'users' && currentUser && currentUser.role === 'admin') {
        loadUsers();
    }
}

// API Calls
async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.message || 'API request failed');
        }
        
        return data;
    } catch (error) {
        console.error('API Error:', error);
        showNotification(error.message, 'error');
        throw error;
    }
}

// System Status
async function loadSystemStatus() {
    try {
        const data = await apiCall('/status');
        systemStatus = data.status;
        updateStatusBar();
    } catch (error) {
        console.error('Error loading status:', error);
    }
}

function updateStatusBar() {
    const statusBar = document.getElementById('statusBar');
    const statusText = document.getElementById('statusText');
    
    if (systemStatus.credentials_configured && systemStatus.cameras_loaded) {
        statusBar.className = 'status-bar success';
        statusText.textContent = `✓ System Ready - ${systemStatus.camera_count} cameras, ${systemStatus.group_count} groups`;
    } else if (!systemStatus.credentials_configured) {
        statusBar.className = 'status-bar warning';
        statusText.textContent = '⚠ Please configure credentials in Settings';
    } else if (!systemStatus.cameras_loaded) {
        statusBar.className = 'status-bar warning';
        statusText.textContent = '⚠ No cameras loaded';
    }
}

// Groups Management
async function loadGroups() {
    try {
        const data = await apiCall('/groups');
        currentGroups = data.groups;
        renderGroups();
    } catch (error) {
        console.error('Error loading groups:', error);
    }
}

function renderGroups() {
    const container = document.getElementById('groupsContainer');
    
    if (currentGroups.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 40px; color: var(--text-secondary);">
                <p style="font-size: 18px; margin-bottom: 10px;">No groups created yet</p>
                <p>Click "Create Group" to get started</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = currentGroups.map(group => {
        // Determine status badge
        let statusBadge = '';
        if (group.status === 'armed') {
            statusBadge = '<span class="badge badge-success">🛡️ Armed</span>';
        } else if (group.status === 'disarmed') {
            statusBadge = '<span class="badge" style="background: var(--bg-tertiary); color: var(--text-secondary);">🔓 Disarmed</span>';
        } else {
            statusBadge = '<span class="badge" style="background: var(--bg-tertiary); color: var(--text-muted);">❓ Unknown</span>';
        }
        
        return `
        <div class="group-card">
            <div class="group-header">
                <div class="group-info">
                    <h3>${escapeHtml(group.name)}</h3>
                    <p>${escapeHtml(group.description)}</p>
                </div>
                ${currentUser && currentUser.role === 'admin' ? `
                    <div class="group-actions">
                        <button class="icon-btn" onclick="editGroup('${group.id}')" title="Edit">✏️</button>
                        <button class="icon-btn" onclick="deleteGroup('${group.id}')" title="Delete">🗑️</button>
                    </div>
                ` : ''}
            </div>
            <div class="group-stats">
                <div class="stat">
                    <span>📹</span>
                    <span>${group.camera_macs.length} cameras</span>
                </div>
                <div class="stat">
                    ${statusBadge}
                </div>
            </div>
            <div class="group-controls">
                <button class="btn btn-success" onclick="armGroup('${group.id}')">
                    🛡️ Arm
                </button>
                <button class="btn btn-warning" onclick="disarmGroup('${group.id}')">
                    🔓 Disarm
                </button>
            </div>
        </div>
    `}).join('');
}

async function armGroup(groupId) {
    const group = currentGroups.find(g => g.id === groupId);
    if (!confirm(`Arm AI-VMD for all cameras in "${group.name}"?`)) {
        return;
    }
    
    showLoading(`Arming ${group.name}...`);
    
    try {
        const data = await apiCall(`/groups/${groupId}/arm`, {
            method: 'POST',
            body: JSON.stringify({
                start_hour: 0,
                start_min: 0,
                end_hour: 0,
                end_min: 0
            })
        });
        
        hideLoading();
        showResultsModal('Arm Operation Results', data);
        
        if (data.summary.successful > 0) {
            showNotification(`Armed ${data.summary.successful} cameras successfully`, 'success');
            // Reload groups to update status
            loadGroups();
        }
    } catch (error) {
        hideLoading();
    }
}

async function disarmGroup(groupId) {
    const group = currentGroups.find(g => g.id === groupId);
    if (!confirm(`Disarm AI-VMD for all cameras in "${group.name}"?`)) {
        return;
    }
    
    showLoading(`Disarming ${group.name}...`);
    
    try {
        const data = await apiCall(`/groups/${groupId}/disarm`, {
            method: 'POST'
        });
        
        hideLoading();
        showResultsModal('Disarm Operation Results', data);
        
        if (data.summary.successful > 0) {
            showNotification(`Disarmed ${data.summary.successful} cameras successfully`, 'success');
            // Reload groups to update status
            loadGroups();
        }
    } catch (error) {
        hideLoading();
    }
}

// Group CRUD Operations
function showCreateGroupModal() {
    // Load cameras list with checkboxes
    const camerasList = document.getElementById('createGroupCamerasList');
    if (currentCameras && currentCameras.length > 0) {
        camerasList.innerHTML = currentCameras.map(camera => `
            <div class="camera-checkbox">
                <input type="checkbox" 
                       id="create_cam_${camera.mac_address}" 
                       value="${camera.mac_address}">
                <label for="create_cam_${camera.mac_address}">
                    <span class="camera-label-name">${escapeHtml(camera.camera_name)}</span>
                    <span class="camera-label-model">${camera.model_name}</span>
                    <span class="camera-label-ip">${camera.ip_address}</span>
                </label>
            </div>
        `).join('');
    } else {
        camerasList.innerHTML = '<p style="color: var(--text-secondary);">No cameras available</p>';
    }
    
    document.getElementById('createGroupModal').classList.add('active');
}

function closeCreateGroupModal() {
    document.getElementById('createGroupModal').classList.remove('active');
    document.getElementById('createGroupForm').reset();
}

async function editGroup(groupId) {
    const group = currentGroups.find(g => g.id === groupId);
    if (!group) return;
    
    // Populate form
    document.getElementById('editGroupId').value = group.id;
    document.getElementById('editGroupName').value = group.name;
    document.getElementById('editGroupDescription').value = group.description;
    
    // Load cameras list with checkboxes
    const camerasList = document.getElementById('groupCamerasList');
    camerasList.innerHTML = currentCameras.map(camera => `
        <div class="camera-checkbox">
            <input type="checkbox" 
                   id="cam_${camera.mac_address}" 
                   value="${camera.mac_address}"
                   ${group.camera_macs.includes(camera.mac_address) ? 'checked' : ''}>
            <label for="cam_${camera.mac_address}">
                <span class="camera-label-name">${escapeHtml(camera.camera_name)}</span>
                <span class="camera-label-model">${camera.model_name}</span>
                <span class="camera-label-ip">${camera.ip_address}</span>
            </label>
        </div>
    `).join('');
    
    document.getElementById('editGroupModal').classList.add('active');
}

function closeEditGroupModal() {
    document.getElementById('editGroupModal').classList.remove('active');
}

async function deleteGroup(groupId) {
    const group = currentGroups.find(g => g.id === groupId);
    if (!confirm(`Delete group "${group.name}"? This cannot be undone.`)) {
        return;
    }
    
    try {
        await apiCall(`/groups/${groupId}`, { method: 'DELETE' });
        showNotification('Group deleted successfully', 'success');
        loadGroups();
        loadSystemStatus();
    } catch (error) {
        // Error already shown by apiCall
    }
}

// Cameras Management
async function loadCameras() {
    try {
        const data = await apiCall('/cameras');
        currentCameras = data.cameras;
        renderCameras();
    } catch (error) {
        console.error('Error loading cameras:', error);
    }
}

async function loadAIApps() {
    try {
        const data = await apiCall('/ai-apps');
        availableAIApps = data.ai_apps;
    } catch (error) {
        console.error('Error loading AI apps:', error);
    }
}

function renderCameras() {
    const container = document.getElementById('camerasContainer');
    
    if (currentCameras.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 40px; color: var(--text-secondary);">
                <p>No cameras loaded</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = `
        <table class="camera-table">
            <thead>
                <tr>
                    <th>Camera</th>
                    <th>IP Address</th>
                    <th>Model</th>
                    <th>Port</th>
                    <th>AI Apps</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${currentCameras.map(camera => {
                    // Use saved actual_app_count if available, otherwise use configured count
                    const aiAppCount = camera.actual_app_count !== undefined && camera.actual_app_count !== null ? 
                                      camera.actual_app_count : 
                                      (camera.installids ? camera.installids.length : 0);
                    const appCountDisplay = aiAppCount > 0 ? 
                        `<span class="badge badge-success">${aiAppCount} AI app${aiAppCount !== 1 ? 's' : ''}</span>` :
                        `<span class="badge" style="background: var(--bg-tertiary); color: var(--text-muted);">Not configured</span>`;
                    
                    return `
                    <tr>
                        <td>
                            <div class="camera-name">${escapeHtml(camera.camera_name)}</div>
                            <div class="camera-ip">${camera.mac_address}</div>
                        </td>
                        <td>${camera.ip_address}</td>
                        <td><span class="badge badge-info">${camera.model_name}</span></td>
                        <td>${camera.http_port}</td>
                        <td>
                            ${appCountDisplay}
                        </td>
                        <td>
                            <div class="camera-actions">
                                ${currentUser && currentUser.role === 'admin' ? `
                                    <button class="btn btn-primary" onclick="editCameraAIApps('${camera.mac_address}')" title="Configure AI Apps">
                                        ⚙️
                                    </button>
                                ` : ''}
                                <button class="btn btn-success" onclick="showCameraControl('${camera.mac_address}')" title="Arm/Disarm">
                                    🎮
                                </button>
                                ${currentUser && currentUser.role === 'admin' ? `
                                    <button class="btn btn-primary" onclick="showInstalledApps('${camera.mac_address}')" title="View Installed Apps">
                                        📱
                                    </button>
                                    <button class="btn btn-danger" onclick="deleteCamera('${camera.mac_address}')" title="Delete Camera">
                                        🗑️
                                    </button>
                                ` : ''}
                            </div>
                        </td>
                    </tr>
                `}).join('')}
            </tbody>
        </table>
    `;
}

async function reloadCameras() {
    showLoading('Reloading cameras...');
    
    try {
        await apiCall('/cameras/reload', { method: 'POST' });
        await loadCameras();
        await loadSystemStatus();
        hideLoading();
        showNotification('Cameras reloaded successfully', 'success');
    } catch (error) {
        hideLoading();
    }
}

// Camera Discovery
let discoveredCamerasData = [];

async function discoverCameras() {
    showLoading('Discovering cameras on the network...');
    
    try {
        const data = await apiCall('/cameras/discover', {
            method: 'POST',
            body: JSON.stringify({
                timeout: 3.0,
                save: false
            })
        });
        
        hideLoading();
        
        if (data.cameras && data.cameras.length > 0) {
            discoveredCamerasData = data.cameras;
            showDiscoveryResults(data.cameras);
        } else {
            showNotification('No cameras discovered on the network', 'info');
            alert('No cameras discovered.\n\nMake sure:\n1. Cameras are powered on\n2. Cameras are on the same network\n3. Firewall allows UDP ports 10669-10670');
        }
    } catch (error) {
        hideLoading();
    }
}

function showDiscoveryResults(cameras) {
    const resultsDiv = document.getElementById('discoveryResults');
    const saveBtn = document.getElementById('saveDiscoveredBtn');
    
    resultsDiv.innerHTML = `
        <div style="background: var(--bg-color); padding: 16px; border-radius: 8px; margin-bottom: 16px;">
            <strong>✓ Discovered ${cameras.length} camera(s)</strong>
        </div>
        
        <table class="camera-table">
            <thead>
                <tr>
                    <th>Camera Name</th>
                    <th>Model</th>
                    <th>IP Address</th>
                    <th>MAC Address</th>
                    <th>Port</th>
                    <th>Firmware</th>
                </tr>
            </thead>
            <tbody>
                ${cameras.map(camera => `
                    <tr>
                        <td>${escapeHtml(camera.camera_name)}</td>
                        <td>${escapeHtml(camera.model_name)}</td>
                        <td>${camera.ip_address}</td>
                        <td style="font-family: monospace; font-size: 12px;">${camera.mac_address}</td>
                        <td>${camera.http_port}</td>
                        <td>${camera.firmware_version}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
        
        <div class="info-box" style="margin-top: 16px;">
            <strong>⚠️ Important:</strong>
            <p style="margin-top: 8px;">
                The discovered cameras will be saved to <code>cameras.json</code>, but you must manually add 
                the <code>installid</code> field for each camera. This value is camera-specific and cannot 
                be auto-detected. Check your camera's CGI documentation for the correct installid values.
            </p>
        </div>
    `;
    
    // Show save button
    saveBtn.style.display = 'inline-flex';
    
    // Show modal
    document.getElementById('discoveryModal').classList.add('active');
}

async function saveDiscoveredCameras() {
    if (!discoveredCamerasData || discoveredCamerasData.length === 0) {
        alert('No cameras to save');
        return;
    }
    
    if (!confirm(`Save ${discoveredCamerasData.length} discovered cameras to cameras.json?\n\nWARNING: This will overwrite your existing cameras.json file!`)) {
        return;
    }
    
    showLoading('Saving cameras...');
    
    try {
        const data = await apiCall('/cameras/discover', {
            method: 'POST',
            body: JSON.stringify({
                timeout: 0.1,  // Quick timeout since we're just saving
                save: true
            })
        });
        
        hideLoading();
        closeDiscoveryModal();
        
        showNotification('Cameras saved successfully', 'success');
        
        // Show important message
        setTimeout(() => {
            alert('✓ Cameras saved to cameras.json\n\n⚠️ IMPORTANT:\nYou must edit cameras.json and add the "installid" field for each camera.\n\nWithout installid, cameras cannot be controlled.\n\nReload the page to see the new cameras.');
        }, 500);
        
    } catch (error) {
        hideLoading();
    }
}

function closeDiscoveryModal() {
    document.getElementById('discoveryModal').classList.remove('active');
    discoveredCamerasData = [];
}

// Manual Camera Addition
function showAddManualCameraModal() {
    // Reset form
    document.getElementById('addManualCameraForm').reset();
    document.getElementById('manualHttpPort').value = '80';
    document.getElementById('manualCameraNamePrefix').value = 'Manual Camera';
    document.getElementById('manualEnhancedSecurity').checked = true;
    document.getElementById('addManualResults').style.display = 'none';

    // Show the form (may have been hidden after previous submission)
    document.getElementById('addManualCameraForm').style.display = 'block';

    // Show modal
    document.getElementById('addManualCameraModal').classList.add('active');
}

function closeAddManualCameraModal() {
    document.getElementById('addManualCameraModal').classList.remove('active');
}

async function addManualCameras(event) {
    event.preventDefault();

    const ipAddresses = document.getElementById('manualIpAddresses').value.trim();
    const httpPort = parseInt(document.getElementById('manualHttpPort').value) || 80;
    const cameraNamePrefix = document.getElementById('manualCameraNamePrefix').value.trim();
    const enhancedSecurity = document.getElementById('manualEnhancedSecurity').checked;

    if (!ipAddresses) {
        alert('Please enter at least one IP address');
        return;
    }

    showLoading('Adding cameras...');

    try {
        const data = await apiCall('/cameras/add-manual', {
            method: 'POST',
            body: JSON.stringify({
                ip_addresses: ipAddresses,
                http_port: httpPort,
                camera_name_prefix: cameraNamePrefix,
                enhanced_security: enhancedSecurity
            })
        });

        hideLoading();

        if (data.success) {
            // Show results
            const resultsDiv = document.getElementById('addManualResults');
            let html = `
                <div class="info-box" style="background: var(--success-color); color: white; padding: 12px; border-radius: 8px;">
                    <strong>${data.message}</strong>
                </div>
            `;

            if (data.added && data.added.length > 0) {
                html += `
                    <div style="margin-top: 16px;">
                        <strong>Added Cameras:</strong>
                        <table class="camera-table" style="margin-top: 8px;">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>IP Address</th>
                                    <th>Port</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${data.added.map(cam => `
                                    <tr>
                                        <td>${escapeHtml(cam.camera_name)}</td>
                                        <td>${cam.ip_address}</td>
                                        <td>${cam.http_port}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                `;
            }

            if (data.skipped && data.skipped.length > 0) {
                html += `
                    <div style="margin-top: 16px;">
                        <strong style="color: var(--warning-color);">Skipped (already exist):</strong>
                        <ul style="margin-top: 8px; padding-left: 20px;">
                            ${data.skipped.map(item => `<li>${item.ip} - ${item.reason}</li>`).join('')}
                        </ul>
                    </div>
                `;
            }

            html += `
                <div style="margin-top: 16px;">
                    <button class="btn btn-primary" onclick="closeAddManualCameraModal(); loadCameras();">Done</button>
                </div>
            `;

            resultsDiv.innerHTML = html;
            resultsDiv.style.display = 'block';

            // Hide the form
            document.getElementById('addManualCameraForm').style.display = 'none';

            // Refresh cameras list
            await loadCameras();
            await loadSystemStatus();

            showNotification(`Added ${data.added.length} camera(s) successfully`, 'success');
        }
    } catch (error) {
        hideLoading();
    }
}

async function deleteCamera(macAddress) {
    const camera = currentCameras.find(c => c.mac_address === macAddress);
    if (!camera) {
        alert('Camera not found');
        return;
    }

    if (!confirm(`Delete camera "${camera.camera_name}" (${camera.ip_address})?\n\nThis will remove it from cameras.json.`)) {
        return;
    }

    showLoading('Deleting camera...');

    try {
        const data = await apiCall(`/cameras/${macAddress}`, {
            method: 'DELETE'
        });

        hideLoading();

        if (data.success) {
            showNotification(data.message, 'success');
            await loadCameras();
            await loadSystemStatus();
        }
    } catch (error) {
        hideLoading();
    }
}

// Credentials Management
async function loadCredentialsStatus() {
    try {
        const data = await apiCall('/credentials');
        renderCredentialsStatus(data);
    } catch (error) {
        console.error('Error loading credentials:', error);
    }
}

function renderCredentialsStatus(data) {
    const container = document.getElementById('credentialsStatus');
    
    if (data.configured) {
        container.className = 'credentials-status configured';
        container.innerHTML = `
            ✓ Credentials configured for user: <strong>${escapeHtml(data.username)}</strong>
        `;
    } else {
        container.className = 'credentials-status not-configured';
        container.innerHTML = '⚠ No credentials configured. Please enter credentials below.';
    }
}

async function deleteCredentials() {
    if (!confirm('Delete stored credentials? You will need to re-enter them.')) {
        return;
    }
    
    try {
        await apiCall('/credentials', { method: 'DELETE' });
        showNotification('Credentials deleted successfully', 'success');
        loadCredentialsStatus();
        loadSystemStatus();
        document.getElementById('credentialsForm').reset();
    } catch (error) {
        // Error already shown by apiCall
    }
}

// System Info
async function loadSystemInfo() {
    const container = document.getElementById('systemInfo');
    
    container.innerHTML = `
        <div class="info-box">
            <div class="info-row">
                <span class="info-label">Cameras Loaded:</span>
                <span>${systemStatus.camera_count}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Groups Configured:</span>
                <span>${systemStatus.group_count}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Credentials:</span>
                <span>${systemStatus.credentials_configured ? '✓ Configured' : '✗ Not Configured'}</span>
            </div>
        </div>
    `;
}

// Results Modal
function showResultsModal(title, data) {
    document.getElementById('resultsTitle').textContent = title;
    
    // Render summary
    const summary = document.getElementById('resultsSummary');
    summary.innerHTML = `
        <div class="result-stat">
            <div class="number">${data.summary.total}</div>
            <div class="label">Total</div>
        </div>
        <div class="result-stat">
            <div class="number" style="color: var(--success-color)">${data.summary.successful}</div>
            <div class="label">Successful</div>
        </div>
        <div class="result-stat">
            <div class="number" style="color: var(--danger-color)">${data.summary.failed}</div>
            <div class="label">Failed</div>
        </div>
    `;
    
    // Render details
    const details = document.getElementById('resultsDetails');
    details.innerHTML = data.results.map(result => `
        <div class="result-item ${result.success ? 'success' : 'error'}">
            <div class="result-info">
                <div class="camera-name">${escapeHtml(result.camera_name)}</div>
                <div class="message">${result.ip_address} - ${escapeHtml(result.message)}</div>
            </div>
            <div class="result-status">${result.success ? '✓' : '✗'}</div>
        </div>
    `).join('');
    
    document.getElementById('resultsModal').classList.add('active');
}

function closeResultsModal() {
    document.getElementById('resultsModal').classList.remove('active');
}

// Loading Overlay
function showLoading(text = 'Processing...') {
    document.getElementById('loadingText').textContent = text;
    document.getElementById('loadingOverlay').classList.add('active');
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.remove('active');
}

// Notifications
function showNotification(message, type = 'info') {
    // Simple console notification for now
    // You can replace this with a toast notification library
    console.log(`[${type.toUpperCase()}] ${message}`);
    
    // Also show as alert for important messages
    if (type === 'error') {
        alert(message);
    }
}

// Utility Functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Close modals on outside click
window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.classList.remove('active');
    }
}

// AI Apps Configuration
async function editCameraAIApps(macAddress) {
    const camera = currentCameras.find(c => c.mac_address === macAddress);
    if (!camera) {
        alert('Camera not found');
        return;
    }
    
    // Check if AI apps are loaded
    if (!availableAIApps || Object.keys(availableAIApps).length === 0) {
        alert('AI applications not loaded. Please refresh the page.');
        console.error('availableAIApps is empty:', availableAIApps);
        return;
    }
    
    // Show modal with loading state
    document.getElementById('aiAppsCameraName').textContent = camera.camera_name;
    document.getElementById('aiAppsCameraMac').value = macAddress;
    document.getElementById('aiAppsContainer').innerHTML = '<div style="text-align: center; padding: 20px;">Loading installed apps...</div>';
    document.getElementById('editAIAppsModal').classList.add('active');
    
    // Get camera details and installed apps
    try {
        const [cameraData, installedApps] = await Promise.all([
            apiCall(`/cameras/${macAddress}`),
            apiCall(`/cameras/${macAddress}/installed-apps`)
        ]);
        
        const camera = cameraData.camera;
        console.log('Camera data:', camera);
        console.log('Installed apps:', installedApps);
        
        // Build map of installed func IDs for quick lookup
        const installedFuncIds = new Set();
        const installedAppsMap = {};
        
        if (installedApps.success && installedApps.apps) {
            installedApps.apps.forEach(app => {
                installedFuncIds.add(parseInt(app.func_id));
                installedAppsMap[app.func_id] = app;
            });
        }
        
        // Filter installids to only include installed apps
        // This prevents showing checked boxes for non-installed apps
        const validInstallids = camera.installids ? 
            camera.installids.filter(id => installedFuncIds.has(id)) : [];
        
        // Render AI apps by category with installation status
        const container = document.getElementById('aiAppsContainer');
        let html = '';
        
        // Add summary with refresh button
        if (installedApps.success) {
            html += `
                <div class="ai-apps-summary" style="background: var(--bg-tertiary); padding: 12px; border-radius: 8px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
                    <div style="display: flex; gap: 20px; font-size: 13px;">
                        <div><strong>Installed on camera:</strong> ${installedApps.app_count} apps</div>
                        <div><strong>Mode:</strong> ${installedApps.limitation_mode}</div>
                    </div>
                    <button class="btn btn-secondary" onclick="refreshInstalledApps('${macAddress}')" style="padding: 6px 12px; font-size: 12px;">
                        🔄 Refresh
                    </button>
                </div>
            `;
        }
        
        for (const [category, apps] of Object.entries(availableAIApps)) {
            html += `
                <div class="ai-apps-category">
                    <h4>${category}</h4>
                    ${apps.map(app => {
                        // Only check if both configured AND installed
                        const isChecked = validInstallids.includes(app.id);
                        const isInstalled = installedFuncIds.has(app.id);
                        const installedApp = installedAppsMap[app.id];
                        
                        return `
                            <div class="ai-app-item ${isInstalled ? 'app-installed' : 'app-not-installed'}">
                                <input type="checkbox" 
                                       id="ai_app_${app.id}" 
                                       value="${app.id}"
                                       ${isChecked ? 'checked' : ''}
                                       ${!isInstalled ? 'disabled' : ''}>
                                <label for="ai_app_${app.id}">
                                    <span style="flex: 1;">
                                        ${app.name}
                                        <span class="ai-app-id">${app.id}</span>
                                    </span>
                                    ${isInstalled ? 
                                        `<span class="badge badge-success" style="font-size: 11px;">✓ Installed</span>` :
                                        `<span class="badge" style="background: var(--bg-primary); color: var(--text-muted); font-size: 11px;">Not Installed</span>`
                                    }
                                </label>
                            </div>
                        `;
                    }).join('')}
                </div>
            `;
        }
        
        container.innerHTML = html;
        
    } catch (error) {
        console.error('Error loading camera details:', error);
        document.getElementById('aiAppsContainer').innerHTML = `
            <div style="text-align: center; padding: 20px; color: var(--danger-color);">
                Error loading apps. Please try again.
            </div>
        `;
    }
}

async function saveAIApps() {
    const macAddress = document.getElementById('aiAppsCameraMac').value;
    
    // Get selected AI app IDs
    const checkboxes = document.querySelectorAll('#aiAppsContainer input[type="checkbox"]:checked');
    const installids = Array.from(checkboxes).map(cb => parseInt(cb.value));
    
    if (installids.length === 0) {
        if (!confirm('No AI apps selected. This camera will have no AI detection enabled. Continue?')) {
            return;
        }
    }
    
    showLoading('Saving AI apps...');
    
    try {
        await apiCall(`/cameras/${macAddress}/installids`, {
            method: 'PUT',
            body: JSON.stringify({ installids })
        });
        
        hideLoading();
        closeEditAIAppsModal();
        
        showNotification(`AI apps updated successfully`, 'success');
        
        // Reload cameras to reflect changes
        await loadCameras();
        
    } catch (error) {
        hideLoading();
    }
}

function closeEditAIAppsModal() {
    document.getElementById('editAIAppsModal').classList.remove('active');
}

// Single Camera Control
async function showCameraControl(macAddress) {
    const camera = currentCameras.find(c => c.mac_address === macAddress);
    if (!camera) {
        alert('Camera not found');
        return;
    }
    
    // Set camera info and show modal with loading state
    document.getElementById('controlCameraName').textContent = camera.camera_name;
    document.getElementById('controlCameraMac').value = macAddress;
    document.getElementById('controlCameraApps').innerHTML = '<em style="color: var(--text-secondary);">Loading...</em>';
    document.getElementById('cameraControlModal').classList.add('active');
    
    // Fetch actually installed apps from camera
    try {
        const installedApps = await apiCall(`/cameras/${macAddress}/installed-apps`);
        
        // Get configured installids from camera config
        const configuredIds = new Set(camera.installids || []);
        
        // Filter to only show apps that are BOTH configured AND installed
        const appsToControl = installedApps.success && installedApps.apps ? 
            installedApps.apps.filter(app => configuredIds.has(parseInt(app.func_id))) : [];
        
        // Render apps that will actually be controlled
        const appsContainer = document.getElementById('controlCameraApps');
        
        if (appsToControl.length > 0) {
            appsContainer.innerHTML = appsToControl.map(app => `
                <div style="padding: 4px 0;">
                    <span class="badge badge-success">${escapeHtml(app.name)}</span>
                    <span class="ai-app-id">${app.func_id}</span>
                </div>
            `).join('');
        } else if (configuredIds.size === 0) {
            appsContainer.innerHTML = '<em style="color: var(--text-secondary);">No AI apps configured for control</em>';
        } else {
            appsContainer.innerHTML = '<em style="color: var(--warning-color);">Configured apps not found on camera</em>';
        }
        
    } catch (error) {
        console.error('Error loading camera apps:', error);
        document.getElementById('controlCameraApps').innerHTML = 
            '<em style="color: var(--danger-color);">Error loading apps</em>';
    }
}

async function armSingleCamera() {
    const macAddress = document.getElementById('controlCameraMac').value;
    const camera = currentCameras.find(c => c.mac_address === macAddress);
    
    if (!confirm(`Arm all AI apps on "${camera.camera_name}"?`)) {
        return;
    }
    
    showLoading(`Arming ${camera.camera_name}...`);
    
    try {
        const data = await apiCall(`/cameras/${macAddress}/arm`, {
            method: 'POST',
            body: JSON.stringify({})
        });
        
        hideLoading();
        closeCameraControlModal();
        showResultsModal('Single Camera Arm Results', data);
        
        if (data.summary.successful > 0) {
            showNotification(`Armed ${data.summary.successful} AI apps on ${camera.camera_name}`, 'success');
        }
    } catch (error) {
        hideLoading();
    }
}

async function disarmSingleCamera() {
    const macAddress = document.getElementById('controlCameraMac').value;
    const camera = currentCameras.find(c => c.mac_address === macAddress);
    
    if (!confirm(`Disarm all AI apps on "${camera.camera_name}"?`)) {
        return;
    }
    
    showLoading(`Disarming ${camera.camera_name}...`);
    
    try {
        const data = await apiCall(`/cameras/${macAddress}/disarm`, {
            method: 'POST'
        });
        
        hideLoading();
        closeCameraControlModal();
        showResultsModal('Single Camera Disarm Results', data);
        
        if (data.summary.successful > 0) {
            showNotification(`Disarmed ${data.summary.successful} AI apps on ${camera.camera_name}`, 'success');
        }
    } catch (error) {
        hideLoading();
    }
}

function closeCameraControlModal() {
    document.getElementById('cameraControlModal').classList.remove('active');
}

// Dashboard
async function loadDashboard() {
    try {
        const status = await apiCall('/status');
        
        document.getElementById('statCameras').textContent = status.status.camera_count;
        document.getElementById('statGroups').textContent = status.status.group_count;
        document.getElementById('statCredentials').textContent = status.status.credentials_configured ? 'Configured' : 'Not Set';
        
        if (currentUser && currentUser.role === 'admin') {
            const users = await apiCall('/users');
            document.getElementById('statUsers').textContent = users.count;
        }
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

// User Management (Admin Only)
async function loadUsers() {
    if (!currentUser || currentUser.role !== 'admin') {
        return;
    }
    
    try {
        const data = await apiCall('/users');
        currentUsers = data.users;
        renderUsers();
    } catch (error) {
        console.error('Error loading users:', error);
    }
}

function renderUsers() {
    const tbody = document.getElementById('usersTableBody');
    
    if (currentUsers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 40px; color: var(--text-secondary);">No users found</td></tr>';
        return;
    }
    
    tbody.innerHTML = currentUsers.map(user => `
        <tr>
            <td>
                <strong>${escapeHtml(user.username)}</strong>
            </td>
            <td>
                <span class="badge ${user.role === 'admin' ? 'badge-info' : 'badge-success'}">${user.role}</span>
            </td>
            <td>${user.created_at ? new Date(user.created_at).toLocaleString() : 'N/A'}</td>
            <td>${user.last_login ? new Date(user.last_login).toLocaleString() : 'Never'}</td>
            <td>
                <div style="display: flex; gap: 8px;">
                    <button class="btn btn-primary" onclick="showResetPasswordModal('${user.username}')" style="padding: 6px 12px; font-size: 12px;">
                        🔑 Reset Password
                    </button>
                    ${user.username !== currentUser.username ? `
                        <button class="btn btn-danger" onclick="deleteUser('${user.username}')" style="padding: 6px 12px; font-size: 12px;">
                            🗑️ Delete
                        </button>
                    ` : ''}
                </div>
            </td>
        </tr>
    `).join('');
}

function showCreateUserModal() {
    document.getElementById('createUserModal').classList.add('active');
    document.getElementById('createUserForm').reset();
}

function closeCreateUserModal() {
    document.getElementById('createUserModal').classList.remove('active');
}

async function createUser(event) {
    event.preventDefault();
    
    const username = document.getElementById('newUsername').value;
    const password = document.getElementById('newPassword').value;
    const role = document.getElementById('newUserRole').value;
    
    showLoading('Creating user...');
    
    try {
        await apiCall('/users', {
            method: 'POST',
            body: JSON.stringify({ username, password, role })
        });
        
        hideLoading();
        closeCreateUserModal();
        showNotification(`User ${username} created successfully`, 'success');
        loadUsers();
        loadDashboard();  // Update user count
    } catch (error) {
        hideLoading();
    }
}

function showResetPasswordModal(username) {
    document.getElementById('resetPasswordUsername').textContent = username;
    document.getElementById('resetPasswordModal').classList.add('active');
    document.getElementById('resetPasswordForm').reset();
    
    // Store username in form
    document.getElementById('resetPasswordForm').dataset.username = username;
}

function closeResetPasswordModal() {
    document.getElementById('resetPasswordModal').classList.remove('active');
}

async function resetUserPassword(event) {
    event.preventDefault();
    
    const username = event.target.dataset.username;
    const newPassword = document.getElementById('resetNewPassword').value;
    
    if (!confirm(`Reset password for user "${username}"?`)) {
        return;
    }
    
    showLoading('Resetting password...');
    
    try {
        await apiCall(`/users/${username}/reset-password`, {
            method: 'POST',
            body: JSON.stringify({ new_password: newPassword })
        });
        
        hideLoading();
        closeResetPasswordModal();
        showNotification(`Password reset for user ${username}`, 'success');
        loadUsers();
    } catch (error) {
        hideLoading();
    }
}

async function deleteUser(username) {
    if (!confirm(`Delete user "${username}"? This cannot be undone.`)) {
        return;
    }
    
    showLoading('Deleting user...');
    
    try {
        await apiCall(`/users/${username}`, {
            method: 'DELETE'
        });
        
        hideLoading();
        showNotification(`User ${username} deleted successfully`, 'success');
        loadUsers();
        loadDashboard();  // Update user count
    } catch (error) {
        hideLoading();
    }
}

// Setup form handlers
function setupForms() {
    // Credentials form
    document.getElementById('credentialsForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const username = document.getElementById('credUsername').value;
        const password = document.getElementById('credPassword').value;
        
        showLoading('Saving credentials...');
        
        try {
            await apiCall('/credentials', {
                method: 'POST',
                body: JSON.stringify({ username, password })
            });
            
            hideLoading();
            showNotification('Credentials saved successfully', 'success');
            loadCredentialsStatus();
            loadSystemStatus();
        } catch (error) {
            hideLoading();
        }
    });
    
    // Create group form
    document.getElementById('createGroupForm').addEventListener('submit', createGroup);

    // Edit group form
    document.getElementById('editGroupForm').addEventListener('submit', saveGroup);

    // Add manual camera form
    if (document.getElementById('addManualCameraForm')) {
        document.getElementById('addManualCameraForm').addEventListener('submit', addManualCameras);
    }
    
    // Create user form (if admin)
    if (document.getElementById('createUserForm')) {
        document.getElementById('createUserForm').addEventListener('submit', createUser);
    }
    
    // Reset password form (if admin)
    if (document.getElementById('resetPasswordForm')) {
        document.getElementById('resetPasswordForm').addEventListener('submit', resetUserPassword);
    }
}

// Create Group
async function createGroup(event) {
    event.preventDefault();
    
    const name = document.getElementById('groupName').value;
    const description = document.getElementById('groupDescription').value;
    
    // Get selected cameras (optional - can be empty)
    const checkboxes = document.querySelectorAll('#createGroupCamerasList input[type="checkbox"]:checked');
    const camera_macs = Array.from(checkboxes).map(cb => cb.value);
    
    showLoading('Creating group...');
    
    try {
        const groupData = {
            name: name,
            description: description,
            camera_macs: camera_macs
        };
        
        await apiCall('/groups', {
            method: 'POST',
            body: JSON.stringify(groupData)
        });
        
        hideLoading();
        closeCreateGroupModal();
        showNotification('Group created successfully', 'success');
        loadGroups();
        loadSystemStatus();
    } catch (error) {
        hideLoading();
    }
}

// Save Group (Edit)
async function saveGroup(event) {
    event.preventDefault();
    
    const groupId = document.getElementById('editGroupId').value;
    const name = document.getElementById('editGroupName').value;
    const description = document.getElementById('editGroupDescription').value;
    
    // Get selected cameras
    const checkboxes = document.querySelectorAll('#groupCamerasList input[type="checkbox"]:checked');
    const camera_macs = Array.from(checkboxes).map(cb => cb.value);
    
    showLoading('Saving group...');
    
    try {
        const groupData = {
            name: name,
            description: description,
            camera_macs: camera_macs
        };
        
        await apiCall(`/groups/${groupId}`, {
            method: 'PUT',
            body: JSON.stringify(groupData)
        });
        
        hideLoading();
        closeEditGroupModal();
        showNotification('Group updated successfully', 'success');
        loadGroups();
        loadSystemStatus();
    } catch (error) {
        hideLoading();
    }
}

// Installed Apps
async function showInstalledApps(macAddress) {
    const camera = currentCameras.find(c => c.mac_address === macAddress);
    if (!camera) {
        alert('Camera not found');
        return;
    }
    
    // Set camera name
    document.getElementById('installedAppsCameraName').textContent = camera.camera_name;
    
    // Show modal with loading
    const modal = document.getElementById('installedAppsModal');
    const content = document.getElementById('installedAppsContent');
    
    content.innerHTML = `
        <div class="loading-apps">
            <div class="loading-spinner"></div>
            <div>Loading installed applications...</div>
        </div>
    `;
    
    modal.classList.add('active');
    
    // Fetch installed apps
    try {
        const data = await apiCall(`/cameras/${macAddress}/installed-apps`);
        
        if (data.success) {
            renderInstalledApps(data);
        } else {
            content.innerHTML = `
                <div class="error-message">
                    <strong>Error:</strong> ${escapeHtml(data.message || 'Failed to load applications')}
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading installed apps:', error);
        content.innerHTML = `
            <div class="error-message">
                <strong>Error:</strong> Failed to communicate with camera. Please check credentials and network connection.
            </div>
        `;
    }
}

function renderInstalledApps(data) {
    const content = document.getElementById('installedAppsContent');
    
    // Summary
    let html = `
        <div class="app-summary">
            <div class="app-summary-card">
                <div class="app-summary-label">Total Apps</div>
                <div class="app-summary-value">${data.app_count}</div>
            </div>
            <div class="app-summary-card">
                <div class="app-summary-label">Max Apps</div>
                <div class="app-summary-value">${data.max_app_count}</div>
            </div>
            <div class="app-summary-card">
                <div class="app-summary-label">Mode</div>
                <div class="app-summary-value" style="font-size: 18px;">${data.limitation_mode}</div>
            </div>
        </div>
    `;
    
    // Apps list
    if (data.apps && data.apps.length > 0) {
        html += '<div class="apps-grid">';
        
        data.apps.forEach(app => {
            
            html += `
                <div class="app-card">
                    <div class="app-card-header">
                        <div>
                            <div class="app-name">${escapeHtml(app.name)}</div>
                            <div class="app-version">v${escapeHtml(app.version)}</div>
                        </div>
                        <div class="app-badges">
                            ${app.use_ai ? '<span class="badge badge-info">AI</span>' : ''}
                            <span class="badge badge-success">Ch ${app.channel}</span>
                        </div>
                    </div>
                    
                    <div class="app-details">
                        <div class="app-detail">
                            <div class="app-detail-label">Install ID</div>
                            <div class="app-detail-value">
                                <span class="install-id">${app.install_id}</span>
                            </div>
                        </div>
                        <div class="app-detail">
                            <div class="app-detail-label">Func ID</div>
                            <div class="app-detail-value">${app.func_id}</div>
                        </div>
                        <div class="app-detail">
                            <div class="app-detail-label">CPU Usage</div>
                            <div class="app-detail-value">${app.cpu_rate}%</div>
                        </div>
                        <div class="app-detail">
                            <div class="app-detail-label">RAM</div>
                            <div class="app-detail-value">${formatBytes(app.ram_size)}</div>
                        </div>
                        <div class="app-detail">
                            <div class="app-detail-label">ROM</div>
                            <div class="app-detail-value">${formatBytes(app.rom_size)}</div>
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
    } else {
        html += '<p style="text-align: center; padding: 40px; color: var(--text-secondary);">No applications found</p>';
    }
    
    content.innerHTML = html;
}

function formatBytes(bytes) {
    const kb = parseInt(bytes);
    if (kb < 1024) return kb + ' KB';
    return (kb / 1024).toFixed(1) + ' MB';
}

function formatTrialTime(seconds) {
    if (seconds < 0) return 'Unlimited';
    
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    
    if (days > 0) {
        return `${days} day${days !== 1 ? 's' : ''} ${hours}h`;
    } else if (hours > 0) {
        return `${hours} hour${hours !== 1 ? 's' : ''}`;
    } else {
        return 'Less than 1 hour';
    }
}

function closeInstalledAppsModal() {
    document.getElementById('installedAppsModal').classList.remove('active');
}

// Refresh installed apps for a camera
async function refreshInstalledApps(macAddress) {
    showLoading('Refreshing installed apps...');
    
    try {
        // Re-query the camera
        const installedApps = await apiCall(`/cameras/${macAddress}/installed-apps`);
        
        if (installedApps.success) {
            // Update the camera's app count in memory
            const camera = currentCameras.find(c => c.mac_address === macAddress);
            if (camera) {
                camera.actualAppCount = installedApps.app_count;
            }
            
            hideLoading();
            showNotification(`Found ${installedApps.app_count} installed apps`, 'success');
            
            // Reload the configuration modal to show updated info
            closeEditAIAppsModal();
            editCameraAIApps(macAddress);
        } else {
            hideLoading();
            showNotification('Failed to refresh installed apps', 'error');
        }
    } catch (error) {
        hideLoading();
        console.error('Error refreshing apps:', error);
    }
}

// Activity Log Functions
let currentActivityLog = [];

async function loadActivityLog() {
    try {
        const data = await apiCall('/activity-log?limit=100');
        currentActivityLog = data.entries;
        renderActivityLog();
    } catch (error) {
        console.error('Error loading activity log:', error);
    }
}

function renderActivityLog() {
    const tbody = document.getElementById('activityLogTableBody');
    
    if (currentActivityLog.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 40px; color: var(--text-secondary);">No activity logged yet</td></tr>';
        return;
    }
    
    tbody.innerHTML = currentActivityLog.map(entry => {
        const timestamp = new Date(entry.timestamp);
        const timeStr = timestamp.toLocaleString();
        
        const actionBadge = entry.action === 'arm' ? 
            '<span class="badge badge-success">🛡️ Armed</span>' :
            '<span class="badge" style="background: var(--warning-color); color: white;">🔓 Disarmed</span>';
        
        const resultBadge = entry.success ?
            '<span class="badge badge-success">✓ Success</span>' :
            '<span class="badge badge-danger">✗ Failed</span>';
        
        const targetIcon = entry.target_type === 'group' ? '📁' : '📹';
        
        return `
            <tr>
                <td style="white-space: nowrap;">${timeStr}</td>
                <td><strong>${escapeHtml(entry.user)}</strong></td>
                <td>${actionBadge}</td>
                <td>
                    <span>${targetIcon}</span>
                    <strong>${escapeHtml(entry.target_name)}</strong>
                    <br>
                    <small style="color: var(--text-secondary);">${entry.target_type}</small>
                </td>
                <td style="text-align: center;">${entry.cameras_affected}</td>
                <td>${resultBadge}</td>
            </tr>
        `;
    }).join('');
}
