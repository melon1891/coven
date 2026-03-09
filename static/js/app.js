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

    // Setup lobby event handlers
    setupLobbyHandlers();

    // Show start screen
    uiManager.showScreen('start');
}

/**
 * Setup WebSocket event handlers
 */
function setupWebSocketHandlers() {
    wsManager.on('connected', (data) => {
        console.log('Connected:', data);
    });

    wsManager.on('disconnected', (data) => {
        console.log('Disconnected:', data.reason);
    });

    wsManager.on('state_update', (state) => {
        gameManager.handleStateUpdate(state);
    });

    wsManager.on('trick_animation', (state) => {
        if (state && state.current_trick_plays) {
            uiManager.updateTrickPlays(state.current_trick_plays);
        }
    });

    wsManager.on('error', (data) => {
        console.error('WebSocket error:', data.message);
    });

    // Multiplayer lobby events
    wsManager.on('lobby_state', (data) => {
        // Update host status from server
        if (data.is_host !== undefined) {
            gameManager.isHost = data.is_host;
        }
        uiManager.updateLobby(data);
        // Show/hide start button for host
        const startBtn = document.getElementById('start-game-btn');
        if (gameManager.isHost) {
            startBtn.classList.remove('hidden');
        } else {
            startBtn.classList.add('hidden');
        }
    });

    wsManager.on('player_joined', (data) => {
        console.log('Player joined:', data);
        if (data.players) {
            uiManager.updateLobby({ players: data.players });
        }
        showToast(`${data.player ? data.player.name : 'Player'} が参加しました`, 'success');
    });

    wsManager.on('player_disconnected', (data) => {
        console.log('Player disconnected:', data);
        if (data.player) {
            showToast(`${data.player.name} が切断しました`, 'warning');
        }
    });

    wsManager.on('player_reconnected', (data) => {
        console.log('Player reconnected:', data);
        if (data.player) {
            showToast(`${data.player.name} が再接続しました`, 'success');
        }
    });

    wsManager.on('game_starting', () => {
        uiManager.showScreen('game');
    });
}

/**
 * Setup UI event handlers
 */
function setupUIHandlers() {
    // Solo play button
    const startBtn = document.getElementById('start-btn');
    startBtn.addEventListener('click', async () => {
        const seedInput = document.getElementById('seed-input');
        const seed = seedInput.value ? parseInt(seedInput.value) : null;
        const aiBot = document.getElementById('ai-bot-toggle')?.checked || false;

        startBtn.disabled = true;
        startBtn.textContent = 'Starting...';

        const success = await gameManager.startGame(seed, aiBot);

        if (success) {
            uiManager.showScreen('game');
            gameManager.updateUI();
        } else {
            startBtn.disabled = false;
            startBtn.textContent = 'ソロプレイ (CPU対戦)';
            alert('ゲームの開始に失敗しました。もう一度お試しください。');
        }
    });

    // New game button (on result screen)
    const newGameBtn = document.getElementById('new-game-btn');
    newGameBtn.addEventListener('click', () => {
        wsManager.disconnect();
        gameManager.isMultiplayer = false;
        gameManager.roomCode = null;
        gameManager.playerToken = null;
        gameManager.playerSlot = null;
        gameManager.isHost = false;
        uiManager.showScreen('start');
        document.getElementById('start-btn').disabled = false;
        document.getElementById('start-btn').textContent = 'ソロプレイ (CPU対戦)';
    });

    // Settings button
    const settingsBtn = document.getElementById('settings-btn');
    settingsBtn.addEventListener('click', () => {
        console.log('Settings clicked');
    });
}

/**
 * Setup lobby event handlers
 */
function setupLobbyHandlers() {
    // Create room button
    document.getElementById('create-room-btn').addEventListener('click', async () => {
        const nameInput = document.getElementById('player-name-input');
        const playerName = nameInput.value.trim() || 'Player';

        const btn = document.getElementById('create-room-btn');
        btn.disabled = true;
        btn.textContent = '作成中...';

        const result = await gameManager.createRoom(playerName);

        if (result) {
            document.getElementById('lobby-room-code').textContent = result.room_code;
            uiManager.showScreen('lobby');
        } else {
            alert('ルームの作成に失敗しました。');
        }

        btn.disabled = false;
        btn.textContent = 'ルーム作成';
    });

    // Join room button
    document.getElementById('join-room-btn').addEventListener('click', async () => {
        const nameInput = document.getElementById('player-name-input');
        const codeInput = document.getElementById('room-code-input');
        const playerName = nameInput.value.trim() || 'Player';
        const roomCode = codeInput.value.trim().toUpperCase();

        if (!roomCode) {
            alert('ルームコードを入力してください。');
            return;
        }

        const btn = document.getElementById('join-room-btn');
        btn.disabled = true;
        btn.textContent = '参加中...';

        const result = await gameManager.joinRoom(roomCode, playerName);

        if (result) {
            document.getElementById('lobby-room-code').textContent = roomCode;
            uiManager.showScreen('lobby');
        } else {
            alert('ルームへの参加に失敗しました。コードを確認してください。');
        }

        btn.disabled = false;
        btn.textContent = '参加';
    });

    // Copy room code button
    document.getElementById('copy-code-btn').addEventListener('click', () => {
        const code = document.getElementById('lobby-room-code').textContent;
        if (code && code !== '------') {
            navigator.clipboard.writeText(code).then(() => {
                const btn = document.getElementById('copy-code-btn');
                btn.textContent = 'OK!';
                setTimeout(() => { btn.textContent = 'コピー'; }, 1500);
            }).catch(() => {
                // Fallback: select text
                const el = document.getElementById('lobby-room-code');
                const range = document.createRange();
                range.selectNodeContents(el);
                const sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
            });
        }
    });

    // Start game button (host only)
    document.getElementById('start-game-btn').addEventListener('click', async () => {
        const btn = document.getElementById('start-game-btn');
        btn.disabled = true;
        btn.textContent = '開始中...';

        const success = await gameManager.startMultiplayerGame();

        if (!success) {
            alert('ゲームの開始に失敗しました。');
            btn.disabled = false;
            btn.textContent = 'ゲーム開始';
        }
        // On success, game_starting WS event will switch to game screen
    });

    // Leave room button
    document.getElementById('leave-room-btn').addEventListener('click', () => {
        gameManager.leaveRoom();
        uiManager.showScreen('start');
    });
}

/**
 * Utility: Format number with animation
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
 */
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    document.body.appendChild(toast);

    requestAnimationFrame(() => {
        toast.classList.add('show');
    });

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
