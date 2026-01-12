/**
 * Main Application for Coven Rich UI
 */

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

/**
 * Initialize the application
 */
function initializeApp() {
    // Setup WebSocket handlers
    setupWebSocketHandlers();

    // Setup UI event handlers
    setupUIHandlers();

    // Show start screen
    uiManager.showScreen('start');
}

/**
 * Setup WebSocket event handlers
 */
function setupWebSocketHandlers() {
    wsManager.on('connected', (data) => {
        console.log('Connected to game:', data.sessionId);
    });

    wsManager.on('disconnected', (data) => {
        console.log('Disconnected:', data.reason);
        // Could show reconnection message
    });

    wsManager.on('state_update', (state) => {
        gameManager.handleStateUpdate(state);
    });

    wsManager.on('error', (data) => {
        console.error('WebSocket error:', data.message);
        // Could show error message to user
    });
}

/**
 * Setup UI event handlers
 */
function setupUIHandlers() {
    // Start button
    const startBtn = document.getElementById('start-btn');
    startBtn.addEventListener('click', async () => {
        const seedInput = document.getElementById('seed-input');
        const seed = seedInput.value ? parseInt(seedInput.value) : null;

        startBtn.disabled = true;
        startBtn.textContent = 'Starting...';

        const success = await gameManager.startGame(seed);

        if (success) {
            uiManager.showScreen('game');
            gameManager.updateUI();
        } else {
            startBtn.disabled = false;
            startBtn.textContent = 'Start Game';
            alert('Failed to start game. Please try again.');
        }
    });

    // New game button (on result screen)
    const newGameBtn = document.getElementById('new-game-btn');
    newGameBtn.addEventListener('click', () => {
        wsManager.disconnect();
        uiManager.showScreen('start');
        document.getElementById('start-btn').disabled = false;
        document.getElementById('start-btn').textContent = 'Start Game';
    });

    // Settings button (placeholder)
    const settingsBtn = document.getElementById('settings-btn');
    settingsBtn.addEventListener('click', () => {
        console.log('Settings clicked');
        // TODO: Implement settings panel
    });
}

/**
 * Utility: Format number with animation
 * @param {HTMLElement} element - Element to update
 * @param {number} newValue - New value
 */
function animateNumber(element, newValue) {
    const currentValue = parseInt(element.textContent) || 0;
    if (currentValue === newValue) return;

    const diff = newValue - currentValue;
    const steps = 10;
    const stepValue = diff / steps;
    let step = 0;

    const interval = setInterval(() => {
        step++;
        const value = Math.round(currentValue + stepValue * step);
        element.textContent = value;

        if (step >= steps) {
            element.textContent = newValue;
            clearInterval(interval);
        }
    }, 30);
}

/**
 * Utility: Show toast notification
 * @param {string} message - Message to show
 * @param {string} type - Type (info, success, warning, error)
 */
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    document.body.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => {
        toast.classList.add('show');
    });

    // Remove after delay
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Add toast styles dynamically
const toastStyles = document.createElement('style');
toastStyles.textContent = `
    .toast {
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%) translateY(100px);
        padding: 12px 24px;
        border-radius: 8px;
        background: var(--bg-card);
        color: var(--text-primary);
        box-shadow: var(--shadow-lg);
        z-index: 1000;
        opacity: 0;
        transition: all 0.3s ease;
    }
    .toast.show {
        transform: translateX(-50%) translateY(0);
        opacity: 1;
    }
    .toast-success { border-left: 4px solid var(--success-color); }
    .toast-warning { border-left: 4px solid var(--warning-color); }
    .toast-error { border-left: 4px solid var(--danger-color); }
    .toast-info { border-left: 4px solid var(--grace-color); }
`;
document.head.appendChild(toastStyles);
