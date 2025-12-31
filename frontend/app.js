/**
 * OryggiAI Database Assistant - Frontend Application
 * Modern chat interface with session management and backend integration
 */

// ==================== Configuration ====================
const CONFIG = {
    API_BASE_URL: '/api/chat',
    ACTIONS_API_URL: '/api/actions',
    REPORTS_DOWNLOAD_URL: '/api/reports/download',
    TENANT_ID: 'default',
    USER_ID: 'admin',
    USER_ROLE: 'ADMIN',
    STATUS_CHECK_INTERVAL: 30000, // 30 seconds
    AUTO_RESIZE_TEXTAREA: true
};

// ==================== State Management ====================
const state = {
    isLoading: false,
    sessionId: null,
    isConnected: false,
    // Action confirmation state
    pendingAction: null,  // { threadId, actionType, message }
    awaitingConfirmation: false,
    // Clarification state
    pendingClarification: null,  // { originalQuestion, attempt, maxAttempts }
    awaitingClarification: false,
    // Biometric enrollment state
    enrollmentInProgress: false,
    enrollmentData: null,  // { biometricType, terminal, timeout, employee }
    countdownInterval: null
};

// ==================== DOM Elements ====================
const elements = {
    // Messages
    chatMessages: null,
    // Input
    chatForm: null,
    questionInput: null,
    sendBtn: null,
    // Loading
    loadingIndicator: null,
    // Status
    statusDot: null,
    statusText: null,
    // Session Info
    sessionIdDisplay: null,
    userIdDisplay: null,
    userRoleDisplay: null,
    // Buttons
    newSessionBtn: null,
    clearChatBtn: null,
    darkModeToggle: null,
    // Examples
    exampleList: null,
    // Confirmation Modal
    confirmationModal: null,
    confirmationMessage: null,
    actionDetails: null,
    confirmActionBtn: null,
    cancelActionBtn: null,
    // Enrollment Overlay
    enrollmentOverlay: null,
    enrollmentTitle: null,
    enrollmentBadge: null,
    enrollmentStatusMsg: null,
    enrollmentDeviceName: null,
    countdownProgress: null,
    countdownText: null,
    palmIcon: null,
    faceIcon: null,
    fingerIcon: null,
    step1: null,
    step2: null,
    step2Text: null,
    step3: null,
    enrollmentCancelBtn: null
};

// ==================== Initialization ====================
document.addEventListener('DOMContentLoaded', () => {
    initializeElements();
    initializeSession();
    setupEventListeners();
    initializeDarkMode();
    checkServerStatus();

    // Periodic status check
    setInterval(checkServerStatus, CONFIG.STATUS_CHECK_INTERVAL);
});

function initializeElements() {
    // Messages
    elements.chatMessages = document.getElementById('chatMessages');

    // Input
    elements.chatForm = document.getElementById('chatForm');
    elements.questionInput = document.getElementById('questionInput');
    elements.sendBtn = document.getElementById('sendBtn');

    // Loading
    elements.loadingIndicator = document.getElementById('loadingIndicator');

    // Status
    elements.statusDot = document.getElementById('statusDot');
    elements.statusText = document.getElementById('statusText');

    // Session Info
    elements.sessionIdDisplay = document.getElementById('sessionIdDisplay');
    elements.userIdDisplay = document.getElementById('userIdDisplay');
    elements.userRoleDisplay = document.getElementById('userRoleDisplay');

    // Buttons
    elements.newSessionBtn = document.getElementById('newSessionBtn');
    elements.clearChatBtn = document.getElementById('clearChatBtn');
    elements.darkModeToggle = document.getElementById('darkModeToggle');

    // Examples
    elements.exampleList = document.getElementById('exampleList');

    // Update session info display
    elements.userIdDisplay.textContent = CONFIG.USER_ID;
    elements.userRoleDisplay.textContent = CONFIG.USER_ROLE;

    // Confirmation Modal
    elements.confirmationModal = document.getElementById('confirmationModal');
    elements.confirmationMessage = document.getElementById('confirmationMessage');
    elements.actionDetails = document.getElementById('actionDetails');
    elements.confirmActionBtn = document.getElementById('confirmActionBtn');
    elements.cancelActionBtn = document.getElementById('cancelActionBtn');

    // Enrollment Overlay
    elements.enrollmentOverlay = document.getElementById('enrollmentOverlay');
    elements.enrollmentTitle = document.getElementById('enrollmentTitle');
    elements.enrollmentBadge = document.getElementById('enrollmentBadge');
    elements.enrollmentStatusMsg = document.getElementById('enrollmentStatusMsg');
    elements.enrollmentDeviceName = document.getElementById('enrollmentDeviceName');
    elements.countdownProgress = document.getElementById('countdownProgress');
    elements.countdownText = document.getElementById('countdownText');
    elements.palmIcon = document.getElementById('palmIcon');
    elements.faceIcon = document.getElementById('faceIcon');
    elements.fingerIcon = document.getElementById('fingerIcon');
    elements.step1 = document.getElementById('step1');
    elements.step2 = document.getElementById('step2');
    elements.step2Text = document.getElementById('step2Text');
    elements.step3 = document.getElementById('step3');
    elements.enrollmentCancelBtn = document.getElementById('enrollmentCancelBtn');

    // Setup enrollment cancel button
    if (elements.enrollmentCancelBtn) {
        elements.enrollmentCancelBtn.addEventListener('click', cancelEnrollment);
    }
}

function initializeSession() {
    // Generate session ID based on timestamp
    state.sessionId = generateSessionId();
    updateSessionDisplay();
}

function generateSessionId() {
    const timestamp = new Date().toISOString().slice(0, 10).replace(/-/g, '');
    const random = Math.random().toString(36).substring(2, 8);
    return `session_${CONFIG.USER_ID}_${timestamp}_${random}`;
}

function updateSessionDisplay() {
    if (elements.sessionIdDisplay) {
        elements.sessionIdDisplay.textContent = state.sessionId;
        elements.sessionIdDisplay.title = state.sessionId; // Full text on hover
    }
}

// ==================== Event Listeners ====================
function setupEventListeners() {
    // Form submission
    elements.chatForm.addEventListener('submit', handleSubmit);

    // Auto-resize textarea
    if (CONFIG.AUTO_RESIZE_TEXTAREA) {
        elements.questionInput.addEventListener('input', autoResizeTextarea);
    }

    // New session button
    elements.newSessionBtn.addEventListener('click', startNewSession);

    // Clear chat button
    elements.clearChatBtn.addEventListener('click', clearChat);

    // Dark mode toggle
    if (elements.darkModeToggle) {
        elements.darkModeToggle.addEventListener('click', toggleDarkMode);
    }

    // Example queries
    const exampleItems = elements.exampleList.querySelectorAll('li');
    exampleItems.forEach(item => {
        item.addEventListener('click', () => {
            const query = item.getAttribute('data-query');
            if (query) {
                elements.questionInput.value = query;
                elements.questionInput.focus();
                autoResizeTextarea();
            }
        });
    });

    // Enter to submit (Shift+Enter for new line)
    elements.questionInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            elements.chatForm.dispatchEvent(new Event('submit'));
        }
    });

    // Global keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // Press '/' to focus input
        if (e.key === '/' && document.activeElement !== elements.questionInput) {
            e.preventDefault();
            elements.questionInput.focus();
        }
    });
}

function autoResizeTextarea() {
    const textarea = elements.questionInput;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
}

function startNewSession() {
    if (confirm('Start a new session? Current chat will be cleared.')) {
        state.sessionId = generateSessionId();
        updateSessionDisplay();
        clearChat();
        showNotification('New session started', 'success');
    }
}

function clearChat() {
    elements.chatMessages.innerHTML = '';
    // Add welcome card back
    addWelcomeCard();
}

function addWelcomeCard() {
    elements.chatMessages.innerHTML = `
        <div class="welcome-card">
            <div class="welcome-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
            </div>
            <h2>Welcome to OryggiAI Database Assistant</h2>
            <p>Ask me anything about your employee database in natural language. I can help you query data, generate reports, and provide insights.</p>
            <div class="welcome-features">
                <div class="feature-badge">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                    </svg>
                    Natural Language Queries
                </div>
                <div class="feature-badge">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                    </svg>
                    PDF & Excel Reports
                </div>
                <div class="feature-badge">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                    </svg>
                    Role-Based Access
                </div>
            </div>
        </div>
    `;
}

// ==================== Server Status ====================
async function checkServerStatus() {
    try {
        // Use the /health endpoint which actually exists on the backend
        const response = await fetch('/health', {
            method: 'GET',
            signal: AbortSignal.timeout(5000) // 5 second timeout
        });

        updateConnectionStatus(response.ok);
    } catch (error) {
        updateConnectionStatus(false);
    }
}

function updateConnectionStatus(isConnected) {
    state.isConnected = isConnected;

    if (isConnected) {
        elements.statusDot.classList.add('connected');
        elements.statusText.textContent = 'Connected';
    } else {
        elements.statusDot.classList.remove('connected');
        elements.statusText.textContent = 'Disconnected';
    }
}

// ==================== Form Submission ====================
async function handleSubmit(e) {
    e.preventDefault();

    if (state.isLoading) return;

    const question = elements.questionInput.value.trim();
    if (!question) return;

    // Check server connection
    if (!state.isConnected) {
        showNotification('Server is not connected. Please check if the backend is running.', 'error');
        return;
    }

    // Add user message to chat
    addUserMessage(question);

    // Clear input and reset height
    elements.questionInput.value = '';
    elements.questionInput.style.height = 'auto';

    // Check if user typed a confirmation ("yes") when there's a pending action
    const confirmationWords = ['yes', 'confirm', 'approve', 'ok', 'proceed', 'y', 'sure', 'go ahead'];
    const isConfirmation = confirmationWords.some(word => question.toLowerCase().trim() === word);

    if (isConfirmation && state.pendingAction && state.pendingAction.threadId) {
        console.log('[CHAT] Detected text confirmation for pending action:', state.pendingAction);
        // Route through the proper approval flow with enrollment overlay
        await handleTextConfirmation();
        return;
    }

    // Show loading
    setLoading(true);

    try {
        // Check if this is an action request (access control)
        if (isActionRequest(question)) {
            const actionResult = await executeAction(question);

            // Check if action requires confirmation
            if (actionResult.awaiting_confirmation) {
                // Show confirmation card in chat
                addConfirmationMessage(actionResult);
                setLoading(false);
                return;
            }

            // Action completed without confirmation (e.g., list_access)
            addBotMessage({
                answer: actionResult.answer,
                success: actionResult.success,
                error: actionResult.error
            });
            setLoading(false);
            return;
        }

        // Send regular query request to backend
        const response = await fetch(`${CONFIG.API_BASE_URL}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question: question,
                tenant_id: CONFIG.TENANT_ID,
                user_id: CONFIG.USER_ID,
                user_role: CONFIG.USER_ROLE,
                session_id: state.sessionId
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // Update session ID from response (if provided)
        if (data.session_id) {
            state.sessionId = data.session_id;
            updateSessionDisplay();
        }

        // Check if clarification is needed
        if (data.needs_clarification) {
            addClarificationMessage(data);
            return;
        }

        // Add bot response
        addBotMessage(data);

    } catch (error) {
        console.error('Error:', error);
        addErrorMessage('Failed to get response from server. Please check if the backend is running and try again.');
    } finally {
        setLoading(false);
    }
}

// ==================== Message Rendering ====================
function addUserMessage(text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message message-user';
    messageDiv.innerHTML = `
        <div class="message-bubble">${escapeHtml(text)}</div>
    `;
    elements.chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

function addBotMessage(data) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message message-bot';

    let html = '<div class="message-content">';

    // Answer
    if (data.answer) {
        html += `<div class="answer">${escapeHtml(data.answer)}</div>`;
    }

    // SQL Query - REMOVED per user request
    // if (data.sql_query) {
    //     html += `
    //         <div class="sql-query">
    //             <div class="sql-query-header">
    //                 <span class="sql-label">Generated SQL Query</span>
    //                 <button class="copy-btn" onclick="copyToClipboard(\`${escapeForTemplate(data.sql_query)}\`, event)">
    //                     Copy
    //                 </button>
    //             </div>
    //             <pre>${escapeHtml(data.sql_query)}</pre>
    //         </div>
    //     `;
    // }

    // NEW: Render results as a table if available
    if (data.results && Array.isArray(data.results) && data.results.length > 0) {
        html += renderResultsTable(data.results);
    }

    // Check for report download link
    const downloadInfo = extractReportInfo(data.answer);
    if (downloadInfo) {
        html += `
            <div class="download-section">
                <button class="download-btn" onclick="downloadReport('${escapeHtml(downloadInfo.filename)}')">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Download Report
                </button>
            </div>
        `;
    }

    // Metadata (if success)
    if (data.success) {
        html += '<div class="metadata">';

        if (data.result_count !== undefined) {
            html += `
                <div class="metadata-badge">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                    </svg>
                    ${data.result_count} result(s)
                </div>
            `;
        }

        if (data.tables_used && data.tables_used.length > 0) {
            html += `
                <div class="metadata-badge">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    Tables: ${data.tables_used.join(', ')}
                </div>
            `;
        }

        if (data.execution_time !== undefined) {
            html += `
                <div class="metadata-badge">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    ${data.execution_time.toFixed(2)}s
                </div>
            `;
        }

        html += '</div>';
    }

    // Error message
    if (!data.success && data.error) {
        html += `
            <div class="error-box">
                <p><strong>Error:</strong> ${escapeHtml(data.error)}</p>
            </div>
        `;
    }

    html += '</div>';

    messageDiv.innerHTML = html;
    elements.chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// Pagination state for tables
let tableDataStore = {};
let tableIdCounter = 0;

// NEW: Function to render query results as an HTML table with pagination
function renderResultsTable(results) {
    if (!results || results.length === 0) return '';

    // Generate unique table ID
    const tableId = `table_${tableIdCounter++}`;

    // Store data for pagination
    tableDataStore[tableId] = {
        results: results,
        currentPage: 1,
        rowsPerPage: 20
    };

    // Get column names from first result
    const columns = Object.keys(results[0]);

    // Limit to reasonable number of columns for display
    const maxColumns = 8;
    const displayColumns = columns.slice(0, maxColumns);
    const hasMoreColumns = columns.length > maxColumns;

    let tableHtml = `<div class="results-table-container" id="${tableId}_container">`;
    tableHtml += `<table class="results-table" id="${tableId}">`;

    // Table header
    tableHtml += '<thead><tr>';
    displayColumns.forEach(col => {
        tableHtml += `<th>${escapeHtml(col)}</th>`;
    });
    if (hasMoreColumns) {
        tableHtml += `<th>... +${columns.length - maxColumns} more</th>`;
    }
    tableHtml += '</tr></thead>';

    // Table body - render first page
    tableHtml += `<tbody id="${tableId}_body">`;
    tableHtml += renderTableRows(results, displayColumns, hasMoreColumns, 1, 20);
    tableHtml += '</tbody></table>';

    // Pagination controls
    const totalPages = Math.ceil(results.length / 20);
    if (results.length > 20) {
        tableHtml += `<div class="table-pagination" id="${tableId}_pagination">`;
        tableHtml += `<button class="pagination-btn" onclick="changePage('${tableId}', 1)" id="${tableId}_first" disabled>First</button>`;
        tableHtml += `<button class="pagination-btn" onclick="changePage('${tableId}', 'prev')" id="${tableId}_prev" disabled>Previous</button>`;
        tableHtml += `<span class="pagination-info" id="${tableId}_info">Page 1 of ${totalPages} (Showing 1-20 of ${results.length})</span>`;
        tableHtml += `<button class="pagination-btn" onclick="changePage('${tableId}', 'next')" id="${tableId}_next">Next</button>`;
        tableHtml += `<button class="pagination-btn" onclick="changePage('${tableId}', ${totalPages})" id="${tableId}_last">Last</button>`;
        tableHtml += '</div>';
    } else {
        tableHtml += `<div class="table-footer">Showing ${results.length} of ${results.length} rows</div>`;
    }

    tableHtml += '</div>';

    return tableHtml;
}

// Helper function to render table rows for a specific page
function renderTableRows(results, displayColumns, hasMoreColumns, page, rowsPerPage) {
    const startIdx = (page - 1) * rowsPerPage;
    const endIdx = Math.min(startIdx + rowsPerPage, results.length);

    let rowsHtml = '';
    for (let i = startIdx; i < endIdx; i++) {
        const row = results[i];
        rowsHtml += '<tr>';
        displayColumns.forEach(col => {
            const value = row[col];
            const formattedValue = formatCellValue(value);
            rowsHtml += `<td>${escapeHtml(formattedValue)}</td>`;
        });
        if (hasMoreColumns) {
            rowsHtml += '<td class="truncated-cell">...</td>';
        }
        rowsHtml += '</tr>';
    }
    return rowsHtml;
}

// Global function to change page
window.changePage = function(tableId, action) {
    const data = tableDataStore[tableId];
    if (!data) return;

    const totalPages = Math.ceil(data.results.length / data.rowsPerPage);
    let newPage = data.currentPage;

    if (action === 'prev') {
        newPage = Math.max(1, data.currentPage - 1);
    } else if (action === 'next') {
        newPage = Math.min(totalPages, data.currentPage + 1);
    } else if (typeof action === 'number') {
        newPage = Math.max(1, Math.min(totalPages, action));
    }

    if (newPage === data.currentPage) return;

    data.currentPage = newPage;

    // Get column info from first row
    const columns = Object.keys(data.results[0]);
    const maxColumns = 8;
    const displayColumns = columns.slice(0, maxColumns);
    const hasMoreColumns = columns.length > maxColumns;

    // Update table body
    const tbody = document.getElementById(`${tableId}_body`);
    if (tbody) {
        tbody.innerHTML = renderTableRows(data.results, displayColumns, hasMoreColumns, newPage, data.rowsPerPage);
    }

    // Update pagination info
    const startRow = (newPage - 1) * data.rowsPerPage + 1;
    const endRow = Math.min(newPage * data.rowsPerPage, data.results.length);
    const info = document.getElementById(`${tableId}_info`);
    if (info) {
        info.textContent = `Page ${newPage} of ${totalPages} (Showing ${startRow}-${endRow} of ${data.results.length})`;
    }

    // Update button states
    const firstBtn = document.getElementById(`${tableId}_first`);
    const prevBtn = document.getElementById(`${tableId}_prev`);
    const nextBtn = document.getElementById(`${tableId}_next`);
    const lastBtn = document.getElementById(`${tableId}_last`);

    if (firstBtn) firstBtn.disabled = newPage === 1;
    if (prevBtn) prevBtn.disabled = newPage === 1;
    if (nextBtn) nextBtn.disabled = newPage === totalPages;
    if (lastBtn) lastBtn.disabled = newPage === totalPages;
};

// NEW: Helper function to format cell values
function formatCellValue(value) {
    if (value === null || value === undefined) {
        return 'NULL';
    }
    if (typeof value === 'boolean') {
        return value ? 'Yes' : 'No';
    }
    if (typeof value === 'number') {
        return value.toString();
    }
    if (typeof value === 'string' && value.length > 100) {
        return value.substring(0, 100) + '...';
    }
    return String(value);
}

function addErrorMessage(text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message message-bot';
    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="error-box">
                <p><strong>Error:</strong> ${escapeHtml(text)}</p>
            </div>
        </div>
    `;
    elements.chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// ==================== Loading State ====================
function setLoading(loading) {
    state.isLoading = loading;
    elements.sendBtn.disabled = loading;
    elements.questionInput.disabled = loading;

    if (loading) {
        elements.loadingIndicator.classList.add('active');
    } else {
        elements.loadingIndicator.classList.remove('active');
    }
}

// ==================== Utilities ====================
function scrollToBottom() {
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeForTemplate(text) {
    return text.replace(/`/g, '\\`').replace(/\$/g, '\\$');
}

function extractReportInfo(text) {
    if (!text) return null;

    // Match pattern: "Report saved to: <path>"
    const match = text.match(/Report saved to:\s*(.+?)(?:\n|$)/i);
    if (match) {
        const path = match[1].trim();
        // Extract filename from path (handle both forward and backslashes)
        const filename = path.split(/[/\\]/).pop();
        return { filename };
    }
    return null;
}

function showNotification(message, type = 'info') {
    // Simple console notification for now
    // Can be enhanced with a toast notification system later
    console.log(`[${type.toUpperCase()}] ${message}`);

    // Optional: Show browser notification if permission granted
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('OryggiAI', { body: message });
    }
}

// ==================== Global Functions (called from inline handlers) ====================
window.copyToClipboard = function (text, event) {
    navigator.clipboard.writeText(text).then(() => {
        const button = event.target.closest('button');
        if (button) {
            const originalText = button.textContent;
            button.textContent = 'Copied!';
            button.style.background = 'rgba(16, 185, 129, 0.2)';
            button.style.borderColor = 'rgba(16, 185, 129, 0.3)';
            button.style.color = '#10b981';

            setTimeout(() => {
                button.textContent = originalText;
                button.style.background = '';
                button.style.borderColor = '';
                button.style.color = '';
            }, 2000);
        }
        showNotification('SQL query copied to clipboard', 'success');
    }).catch(err => {
        console.error('Failed to copy:', err);
        showNotification('Failed to copy to clipboard', 'error');
    });
};

window.downloadReport = function (filename) {
    const downloadUrl = `${CONFIG.REPORTS_DOWNLOAD_URL}/${encodeURIComponent(filename)}`;
    window.open(downloadUrl, '_blank');
    showNotification(`Downloading: ${filename}`, 'success');
};

// ==================== Action Confirmation System ====================

/**
 * Check if a query is an action request (access control)
 */
function isActionRequest(question) {
    const actionKeywords = [
        // Phase 5 - Original access control keywords
        'grant', 'give access', 'allow', 'provide access',
        'block', 'deny', 'stop access', 'prevent',
        'revoke', 'remove access', 'delete permission',
        'list access', 'show permissions', 'what access',
        // Phase 6 - Extended access control keywords
        'register visitor', 'register a visitor', 'add visitor', 'add a visitor',
        'new visitor', 'visitor registration', 'create visitor',
        'temporary card', 'temp card', 'assign card', 'visitor card',
        'database backup', 'backup database', 'backup oryggi', 'db backup', 'backup the database',
        'enroll card', 'card enrollment', 'assign access card', 'issue card',
        'enroll employee', 'add employee', 'new employee', 'employee enrollment',
        'create employee', 'register employee',
        'door access', 'specific door', 'grant door', 'block door', 'manage door',
        // Authentication management keywords
        'add authentication', 'remove authentication', 'manage authentication',
        'add fingerprint', 'remove fingerprint', 'enable fingerprint', 'disable fingerprint',
        'add face', 'remove face', 'enable face', 'disable face',
        'add card auth', 'remove card auth', 'authentication type', 'set authentication',
        // Biometric enrollment keywords
        'enroll palm', 'enroll face', 'enroll finger', 'enroll biometric',
        'palm enrollment', 'face enrollment', 'finger enrollment', 'fingerprint enrollment',
        'biometric enrollment', 'register palm', 'register face', 'register fingerprint'
    ];
    const questionLower = question.toLowerCase();
    return actionKeywords.some(kw => questionLower.includes(kw));
}

/**
 * Execute an action request
 */
async function executeAction(question) {
    try {
        const response = await fetch(`${CONFIG.ACTIONS_API_URL}/execute`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question: question,
                user_id: CONFIG.USER_ID,
                user_role: CONFIG.USER_ROLE,
                session_id: state.sessionId
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('Action execution error:', error);
        throw error;
    }
}

/**
 * Show confirmation modal for destructive actions
 */
function showConfirmationModal(threadId, actionType, confirmationMessage) {
    state.pendingAction = { threadId, actionType, message: confirmationMessage };
    state.awaitingConfirmation = true;

    // Update modal content
    elements.confirmationMessage.textContent = confirmationMessage;

    // Format action type for display
    const actionTypeDisplay = actionType.replace('_', ' ').toUpperCase();
    elements.actionDetails.innerHTML = `
        <div class="action-type-badge ${actionType}">
            <span class="action-type-label">Action Type:</span>
            <span class="action-type-value">${actionTypeDisplay}</span>
        </div>
    `;

    // Show modal
    elements.confirmationModal.classList.add('active');

    // Setup button handlers
    elements.confirmActionBtn.onclick = handleConfirmAction;
    elements.cancelActionBtn.onclick = handleCancelAction;
}

/**
 * Hide confirmation modal
 */
function hideConfirmationModal() {
    elements.confirmationModal.classList.remove('active');
    state.awaitingConfirmation = false;
}

/**
 * Handle action confirmation
 */
async function handleConfirmAction() {
    if (!state.pendingAction) return;

    const { threadId } = state.pendingAction;
    hideConfirmationModal();
    setLoading(true);

    try {
        const response = await fetch(`${CONFIG.ACTIONS_API_URL}/${threadId}/approve`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: CONFIG.USER_ID
            })
        });

        const result = await response.json();

        // Add result message to chat
        addBotMessage({
            answer: result.message || 'Action completed.',
            success: result.success,
            error: result.error
        });

        showNotification(result.success ? 'Action completed successfully' : 'Action failed',
                        result.success ? 'success' : 'error');

    } catch (error) {
        console.error('Confirmation error:', error);
        addErrorMessage(`Failed to confirm action: ${error.message}`);
    } finally {
        state.pendingAction = null;
        setLoading(false);
    }
}

/**
 * Handle action confirmation with enrollment overlay support
 */
async function handleConfirmActionWithEnrollment() {
    if (!state.pendingAction) return;

    const { threadId, actionType } = state.pendingAction;
    const isBiometric = isBiometricEnrollment(actionType);

    hideConfirmationModal();

    // Don't show the standard loading if enrollment overlay is active
    if (!isBiometric) {
        setLoading(true);
    }

    try {
        const response = await fetch(`${CONFIG.ACTIONS_API_URL}/${threadId}/approve`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: CONFIG.USER_ID
            })
        });

        const result = await response.json();

        // Handle biometric enrollment result
        if (isBiometric && state.enrollmentInProgress) {
            if (result.success) {
                showEnrollmentSuccess(result.message || 'Biometric enrolled successfully!');
            } else {
                showEnrollmentFailure(result.error || result.message || 'Enrollment failed');
            }

            // Wait for overlay to close before adding message to chat
            setTimeout(() => {
                addBotMessage({
                    answer: result.message || (result.success ? 'Enrollment completed.' : 'Enrollment failed.'),
                    success: result.success,
                    error: result.error
                });
            }, result.success ? 3500 : 4500);
        } else {
            // Non-biometric action - standard handling
            addBotMessage({
                answer: result.message || 'Action completed.',
                success: result.success,
                error: result.error
            });
        }

        showNotification(result.success ? 'Action completed successfully' : 'Action failed',
                        result.success ? 'success' : 'error');

    } catch (error) {
        console.error('Confirmation error:', error);

        if (isBiometric && state.enrollmentInProgress) {
            showEnrollmentFailure(`Error: ${error.message}`);
            setTimeout(() => {
                addErrorMessage(`Failed to confirm action: ${error.message}`);
            }, 4500);
        } else {
            addErrorMessage(`Failed to confirm action: ${error.message}`);
        }
    } finally {
        state.pendingAction = null;
        if (!isBiometric) {
            setLoading(false);
        }
    }
}

/**
 * Handle action cancellation
 */
async function handleCancelAction() {
    if (!state.pendingAction) return;

    const { threadId } = state.pendingAction;
    hideConfirmationModal();
    setLoading(true);

    try {
        const response = await fetch(`${CONFIG.ACTIONS_API_URL}/${threadId}/reject`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: CONFIG.USER_ID,
                reason: 'Cancelled by user'
            })
        });

        const result = await response.json();

        // Add cancellation message to chat
        addBotMessage({
            answer: 'Action cancelled.',
            success: true
        });

        showNotification('Action cancelled', 'info');

    } catch (error) {
        console.error('Cancellation error:', error);
        addErrorMessage(`Failed to cancel action: ${error.message}`);
    } finally {
        state.pendingAction = null;
        setLoading(false);
    }
}

/**
 * Add confirmation message to chat with inline buttons
 */
function addConfirmationMessage(data) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message message-bot';

    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="confirmation-card">
                <div class="confirmation-icon">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                </div>
                <h4>Action Requires Confirmation</h4>
                <p class="confirmation-text">${escapeHtml(data.confirmation_message)}</p>
                <div class="confirmation-actions">
                    <button class="confirm-btn-inline approve" onclick="handleInlineApprove('${data.thread_id}')">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                        </svg>
                        Approve
                    </button>
                    <button class="confirm-btn-inline reject" onclick="handleInlineReject('${data.thread_id}')">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                        Reject
                    </button>
                </div>
            </div>
        </div>
    `;

    elements.chatMessages.appendChild(messageDiv);
    scrollToBottom();

    // Store pending action
    state.pendingAction = {
        threadId: data.thread_id,
        actionType: data.action_type,
        message: data.confirmation_message
    };
}

/**
 * Handle inline approve button click
 */
window.handleInlineApprove = async function(threadId) {
    // Get the pending action info
    const pendingInfo = state.pendingAction;

    // Check if this is a biometric enrollment
    if (pendingInfo && isBiometricEnrollment(pendingInfo.actionType)) {
        // Extract biometric info from the confirmation message
        const biometricInfo = extractBiometricInfo(pendingInfo.message || '');

        // Show the enrollment overlay
        showEnrollmentOverlay(
            biometricInfo.biometricType,
            biometricInfo.terminal,
            biometricInfo.employee,
            60  // Default timeout
        );
    }

    state.pendingAction = { threadId, ...pendingInfo };
    await handleConfirmActionWithEnrollment();
};

/**
 * Handle inline reject button click
 */
window.handleInlineReject = async function(threadId) {
    state.pendingAction = { threadId };
    await handleCancelAction();
};

/**
 * Handle text confirmation ("yes" typed in chat)
 * This function routes text confirmations through the proper approval flow with enrollment overlay
 */
async function handleTextConfirmation() {
    if (!state.pendingAction || !state.pendingAction.threadId) {
        console.warn('[CHAT] handleTextConfirmation called but no pending action');
        return;
    }

    const { threadId, actionType, message } = state.pendingAction;
    const isBiometric = isBiometricEnrollment(actionType);

    console.log('[CHAT] Processing text confirmation, isBiometric:', isBiometric, 'actionType:', actionType);

    // If biometric enrollment, show the overlay BEFORE the API call
    if (isBiometric) {
        const biometricInfo = extractBiometricInfo(message || '');
        console.log('[CHAT] Biometric info extracted:', biometricInfo);

        showEnrollmentOverlay(
            biometricInfo.biometricType,
            biometricInfo.terminal,
            biometricInfo.employee,
            60  // Default timeout
        );
    } else {
        setLoading(true);
    }

    try {
        const response = await fetch(`${CONFIG.ACTIONS_API_URL}/${threadId}/approve`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: CONFIG.USER_ID
            })
        });

        const result = await response.json();
        console.log('[CHAT] Approval result:', result);

        // Handle biometric enrollment result
        if (isBiometric && state.enrollmentInProgress) {
            if (result.success) {
                showEnrollmentSuccess(result.message || 'Biometric enrolled successfully!');
            } else {
                showEnrollmentFailure(result.error || result.message || 'Enrollment failed');
            }

            // Wait for overlay to close before adding message to chat
            setTimeout(() => {
                addBotMessage({
                    answer: result.message || (result.success ? 'Enrollment completed.' : 'Enrollment failed.'),
                    success: result.success,
                    error: result.error
                });
            }, result.success ? 3500 : 4500);
        } else {
            // Non-biometric action - standard handling
            addBotMessage({
                answer: result.message || 'Action completed.',
                success: result.success,
                error: result.error
            });
        }

        showNotification(result.success ? 'Action completed successfully' : 'Action failed',
                        result.success ? 'success' : 'error');

    } catch (error) {
        console.error('[CHAT] Text confirmation error:', error);

        if (isBiometric && state.enrollmentInProgress) {
            showEnrollmentFailure(`Error: ${error.message}`);
            setTimeout(() => {
                addErrorMessage(`Failed to confirm action: ${error.message}`);
            }, 4500);
        } else {
            addErrorMessage(`Failed to confirm action: ${error.message}`);
        }
    } finally {
        state.pendingAction = null;
        if (!isBiometric) {
            setLoading(false);
        }
    }
}

// ==================== Clarification System ====================

/**
 * Add clarification message to chat with clickable options
 */
function addClarificationMessage(data) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message message-bot';

    // Store clarification state
    state.pendingClarification = {
        originalQuestion: data.original_unclear_question || data.question,
        attempt: data.clarification_attempt || 1,
        maxAttempts: data.max_clarification_attempts || 3
    };
    state.awaitingClarification = true;

    // Build options HTML
    let optionsHtml = '';
    if (data.clarification_options && data.clarification_options.length > 0) {
        optionsHtml = '<div class="clarification-options">';
        data.clarification_options.forEach((option, index) => {
            optionsHtml += `
                <button class="clarification-option-btn" onclick="handleClarificationOption('${escapeForAttribute(option)}')">
                    <span class="option-number">${index + 1}</span>
                    <span class="option-text">${escapeHtml(option)}</span>
                </button>
            `;
        });
        optionsHtml += '</div>';
    }

    // Build attempt indicator
    let attemptHtml = '';
    if (data.clarification_attempt > 1) {
        attemptHtml = `
            <div class="clarification-attempt-info">
                Clarification ${data.clarification_attempt} of ${data.max_clarification_attempts}
            </div>
        `;
    }

    messageDiv.innerHTML = `
        <div class="message-content">
            <div class="clarification-card">
                <div class="clarification-header">
                    <div class="clarification-icon">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                    </div>
                    <h4>I need a bit more information</h4>
                </div>
                <p class="clarification-question">${escapeHtml(data.clarification_question || data.answer)}</p>
                ${optionsHtml}
                <div class="clarification-footer">
                    <p class="clarification-hint">Click an option above or type your own response below</p>
                    ${attemptHtml}
                </div>
            </div>
        </div>
    `;

    elements.chatMessages.appendChild(messageDiv);
    scrollToBottom();

    // Focus the input for manual response
    elements.questionInput.focus();
    elements.questionInput.placeholder = "Type your clarification or click an option above...";
}

/**
 * Handle when user clicks a clarification option
 */
window.handleClarificationOption = function(optionText) {
    if (!state.awaitingClarification) return;

    // Clear clarification state
    state.awaitingClarification = false;
    state.pendingClarification = null;

    // Reset input placeholder
    elements.questionInput.placeholder = "Ask a question about your database...";

    // Disable the clicked options (visual feedback)
    const optionButtons = document.querySelectorAll('.clarification-option-btn');
    optionButtons.forEach(btn => {
        btn.disabled = true;
        btn.classList.add('option-selected');
    });

    // Find and highlight the selected option
    optionButtons.forEach(btn => {
        if (btn.querySelector('.option-text').textContent === optionText) {
            btn.classList.add('option-chosen');
        }
    });

    // Add user message showing their selection
    addUserMessage(optionText);

    // Send the selected option as a new query
    sendClarificationResponse(optionText);
};

/**
 * Send clarification response to backend
 */
async function sendClarificationResponse(response) {
    setLoading(true);

    try {
        const apiResponse = await fetch(`${CONFIG.API_BASE_URL}/query`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question: response,
                tenant_id: CONFIG.TENANT_ID,
                user_id: CONFIG.USER_ID,
                user_role: CONFIG.USER_ROLE,
                session_id: state.sessionId
            })
        });

        if (!apiResponse.ok) {
            throw new Error(`HTTP error! status: ${apiResponse.status}`);
        }

        const data = await apiResponse.json();

        // Update session ID from response
        if (data.session_id) {
            state.sessionId = data.session_id;
            updateSessionDisplay();
        }

        // Check if still needs more clarification
        if (data.needs_clarification) {
            addClarificationMessage(data);
            return;
        }

        // Add bot response
        addBotMessage(data);

    } catch (error) {
        console.error('Clarification error:', error);
        addErrorMessage('Failed to process your response. Please try again.');
    } finally {
        setLoading(false);
    }
}

/**
 * Helper function to escape text for use in HTML attributes
 */
function escapeForAttribute(text) {
    return text
        .replace(/\\/g, '\\\\')
        .replace(/'/g, "\\'")
        .replace(/"/g, '\\"')
        .replace(/\n/g, '\\n');
}

// ==================== Dark Mode ====================

/**
 * Toggle dark mode on/off
 */
function toggleDarkMode() {
    const body = document.body;
    const sunIcon = elements.darkModeToggle.querySelector('.sun-icon');
    const moonIcon = elements.darkModeToggle.querySelector('.moon-icon');

    body.classList.toggle('dark-mode');

    // Toggle icons and save preference
    if (body.classList.contains('dark-mode')) {
        sunIcon.style.display = 'none';
        moonIcon.style.display = 'block';
        localStorage.setItem('darkMode', 'enabled');
    } else {
        sunIcon.style.display = 'block';
        moonIcon.style.display = 'none';
        localStorage.setItem('darkMode', 'disabled');
    }
}

/**
 * Initialize dark mode from localStorage on page load
 */
function initializeDarkMode() {
    const darkMode = localStorage.getItem('darkMode');

    if (darkMode === 'enabled') {
        const body = document.body;
        const sunIcon = elements.darkModeToggle.querySelector('.sun-icon');
        const moonIcon = elements.darkModeToggle.querySelector('.moon-icon');

        body.classList.add('dark-mode');
        if (sunIcon) sunIcon.style.display = 'none';
        if (moonIcon) moonIcon.style.display = 'block';
    }
}

// ==================== Biometric Enrollment Overlay ====================

/**
 * Show the biometric enrollment overlay
 * @param {string} biometricType - Type of biometric (palm, face, finger)
 * @param {string} terminalName - Name of the terminal device
 * @param {string} employeeId - Employee identifier
 * @param {number} timeout - Timeout in seconds
 */
function showEnrollmentOverlay(biometricType, terminalName, employeeId, timeout = 60) {
    state.enrollmentInProgress = true;
    state.enrollmentData = { biometricType, terminalName, employeeId, timeout };

    // Set title based on biometric type
    const biometricNames = {
        'palm': 'Palm',
        'face': 'Face',
        'finger': 'Fingerprint'
    };
    const biometricName = biometricNames[biometricType.toLowerCase()] || 'Biometric';

    if (elements.enrollmentTitle) {
        elements.enrollmentTitle.textContent = `${biometricName} Enrollment`;
    }

    // Show correct biometric icon
    if (elements.palmIcon) elements.palmIcon.style.display = biometricType.toLowerCase() === 'palm' ? 'block' : 'none';
    if (elements.faceIcon) elements.faceIcon.style.display = biometricType.toLowerCase() === 'face' ? 'block' : 'none';
    if (elements.fingerIcon) elements.fingerIcon.style.display = biometricType.toLowerCase() === 'finger' ? 'block' : 'none';

    // Update step 2 text
    if (elements.step2Text) {
        elements.step2Text.textContent = `Place ${biometricName.toLowerCase()} on device`;
    }

    // Set device name
    if (elements.enrollmentDeviceName) {
        elements.enrollmentDeviceName.textContent = terminalName || 'Terminal';
    }

    // Reset badge
    if (elements.enrollmentBadge) {
        elements.enrollmentBadge.textContent = 'IN PROGRESS';
        elements.enrollmentBadge.classList.remove('success', 'failed');
    }

    // Reset overlay classes
    if (elements.enrollmentOverlay) {
        elements.enrollmentOverlay.classList.remove('success', 'failed');
        elements.enrollmentOverlay.classList.add('active');
    }

    // Reset steps
    resetEnrollmentSteps();

    // Update status message
    updateEnrollmentStatus('connecting');

    // Start countdown after a brief delay (simulating connection)
    setTimeout(() => {
        updateEnrollmentStatus('ready');
        startCountdown(timeout);
    }, 1500);
}

/**
 * Update enrollment status message and steps
 */
function updateEnrollmentStatus(status) {
    const statusMessages = {
        'connecting': 'Connecting to device...',
        'ready': 'Place your biometric on the device NOW!',
        'capturing': 'Capturing biometric...',
        'success': 'Enrollment Successful!',
        'failed': 'Enrollment Failed - Please try again',
        'timeout': 'Timeout - No biometric detected'
    };

    if (elements.enrollmentStatusMsg) {
        elements.enrollmentStatusMsg.textContent = statusMessages[status] || status;
    }

    // Update steps based on status
    if (status === 'connecting') {
        setStepActive(1);
    } else if (status === 'ready') {
        setStepCompleted(1);
        setStepActive(2);
    } else if (status === 'capturing') {
        setStepCompleted(1);
        setStepActive(2);
    } else if (status === 'success') {
        setStepCompleted(1);
        setStepCompleted(2);
        setStepCompleted(3);
    } else if (status === 'failed' || status === 'timeout') {
        setStepCompleted(1);
        setStepFailed(2);
    }
}

/**
 * Reset enrollment steps
 */
function resetEnrollmentSteps() {
    [elements.step1, elements.step2, elements.step3].forEach(step => {
        if (step) {
            step.classList.remove('active', 'completed', 'failed');
        }
    });
}

/**
 * Set a step as active
 */
function setStepActive(stepNum) {
    const stepElement = stepNum === 1 ? elements.step1 : stepNum === 2 ? elements.step2 : elements.step3;
    if (stepElement) {
        stepElement.classList.remove('completed', 'failed');
        stepElement.classList.add('active');
    }
}

/**
 * Set a step as completed
 */
function setStepCompleted(stepNum) {
    const stepElement = stepNum === 1 ? elements.step1 : stepNum === 2 ? elements.step2 : elements.step3;
    if (stepElement) {
        stepElement.classList.remove('active', 'failed');
        stepElement.classList.add('completed');
    }
}

/**
 * Set a step as failed
 */
function setStepFailed(stepNum) {
    const stepElement = stepNum === 1 ? elements.step1 : stepNum === 2 ? elements.step2 : elements.step3;
    if (stepElement) {
        stepElement.classList.remove('active', 'completed');
        stepElement.classList.add('failed');
    }
}

/**
 * Start countdown timer
 */
function startCountdown(totalSeconds) {
    let remaining = totalSeconds;

    // Initial update
    updateCountdownDisplay(remaining, totalSeconds);

    // Clear any existing interval
    if (state.countdownInterval) {
        clearInterval(state.countdownInterval);
    }

    state.countdownInterval = setInterval(() => {
        remaining--;
        updateCountdownDisplay(remaining, totalSeconds);

        if (remaining <= 0) {
            clearInterval(state.countdownInterval);
            state.countdownInterval = null;
        }
    }, 1000);
}

/**
 * Update countdown display
 */
function updateCountdownDisplay(remaining, total) {
    if (elements.countdownProgress) {
        const percentage = (remaining / total) * 100;
        elements.countdownProgress.style.width = percentage + '%';
    }

    if (elements.countdownText) {
        elements.countdownText.textContent = `${remaining} seconds remaining`;
    }
}

/**
 * Show enrollment success
 */
function showEnrollmentSuccess(message) {
    // Stop countdown
    if (state.countdownInterval) {
        clearInterval(state.countdownInterval);
        state.countdownInterval = null;
    }

    // Update overlay
    if (elements.enrollmentOverlay) {
        elements.enrollmentOverlay.classList.add('success');
    }

    if (elements.enrollmentBadge) {
        elements.enrollmentBadge.textContent = 'SUCCESS';
        elements.enrollmentBadge.classList.add('success');
    }

    updateEnrollmentStatus('success');

    if (elements.enrollmentStatusMsg && message) {
        elements.enrollmentStatusMsg.textContent = message;
    }

    // Auto-hide after 3 seconds
    setTimeout(() => {
        hideEnrollmentOverlay();
    }, 3000);
}

/**
 * Show enrollment failure
 */
function showEnrollmentFailure(message) {
    // Stop countdown
    if (state.countdownInterval) {
        clearInterval(state.countdownInterval);
        state.countdownInterval = null;
    }

    // Update overlay
    if (elements.enrollmentOverlay) {
        elements.enrollmentOverlay.classList.add('failed');
    }

    if (elements.enrollmentBadge) {
        elements.enrollmentBadge.textContent = 'FAILED';
        elements.enrollmentBadge.classList.add('failed');
    }

    updateEnrollmentStatus('failed');

    if (elements.enrollmentStatusMsg && message) {
        elements.enrollmentStatusMsg.textContent = message;
    }

    // Auto-hide after 4 seconds
    setTimeout(() => {
        hideEnrollmentOverlay();
    }, 4000);
}

/**
 * Hide enrollment overlay
 */
function hideEnrollmentOverlay() {
    // Stop countdown
    if (state.countdownInterval) {
        clearInterval(state.countdownInterval);
        state.countdownInterval = null;
    }

    if (elements.enrollmentOverlay) {
        elements.enrollmentOverlay.classList.remove('active', 'success', 'failed');
    }

    state.enrollmentInProgress = false;
    state.enrollmentData = null;
}

/**
 * Cancel enrollment (called by cancel button)
 */
function cancelEnrollment() {
    hideEnrollmentOverlay();
    showNotification('Enrollment cancelled', 'info');
}

/**
 * Check if the action is a biometric enrollment
 */
function isBiometricEnrollment(actionType) {
    return actionType === 'trigger_biometric_enrollment';
}

/**
 * Extract biometric info from confirmation message
 */
function extractBiometricInfo(message) {
    const info = {
        biometricType: 'palm',
        terminal: 'Terminal',
        employee: ''
    };

    // Extract biometric type
    const typeMatch = message.match(/Biometric Type:\s*(\w+)/i);
    if (typeMatch) {
        info.biometricType = typeMatch[1].toLowerCase();
    }

    // Extract device/terminal
    const deviceMatch = message.match(/Device:\s*([^\n]+)/i);
    if (deviceMatch) {
        info.terminal = deviceMatch[1].trim();
    }

    // Extract employee
    const employeeMatch = message.match(/Employee:\s*([^\n]+)/i);
    if (employeeMatch) {
        info.employee = employeeMatch[1].trim();
    }

    return info;
}
