/**
 * Game Manager for Coven Rich UI
 */

class GameManager {
    constructor() {
        this.sessionId = null;
        this.state = null;
        this.pendingInput = null;
        this.isProcessing = false;
        this.lastInputType = null;

        // Round summary tracking
        this.prevRoundNo = null;
        this.roundStartPlayers = null;
        this.roundStartLogLength = 0;
        this._roundSummaryPending = false;

        // Multiplayer properties
        this.roomCode = null;
        this.playerToken = null;
        this.playerSlot = null;  // 0-3
        this.playerName = null;
        this.isHost = false;
        this.isMultiplayer = false;
    }

    /**
     * Start a new solo game
     * @param {number|null} seed - Optional seed for reproducibility
     */
    async startGame(seed = null, aiBot = false) {
        try {
            let url = seed !== null ? `/api/game/new?seed=${seed}` : '/api/game/new';
            if (aiBot) url += (url.includes('?') ? '&' : '?') + 'ai_bot=true';
            const response = await fetch(url, { method: 'POST' });
            const data = await response.json();

            if (data.error) {
                console.error('Failed to start game:', data.error);
                return false;
            }

            this.sessionId = data.session_id;
            this.state = data.state;
            this.pendingInput = data.state.pending_input;
            this.isMultiplayer = false;
            this.playerSlot = 0;

            // Connect WebSocket
            wsManager.connect(this.sessionId);

            return true;
        } catch (error) {
            console.error('Failed to start game:', error);
            return false;
        }
    }

    /**
     * Create a multiplayer room
     * @param {string} playerName - Player name
     * @returns {Object|null} Room data or null on failure
     */
    async createRoom(playerName) {
        try {
            const response = await fetch('/api/room/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: playerName })
            });
            const data = await response.json();

            if (data.error) {
                console.error('Failed to create room:', data.error);
                return null;
            }

            this.roomCode = data.room_code;
            this.playerToken = data.token;
            this.playerSlot = data.slot;
            this.playerName = playerName;
            this.isHost = true;
            this.isMultiplayer = true;

            this.saveToken(data.room_code, data.token);

            // Connect room WebSocket
            wsManager.connectRoom(data.room_code, data.token);

            return data;
        } catch (error) {
            console.error('Failed to create room:', error);
            return null;
        }
    }

    /**
     * Join a multiplayer room
     * @param {string} roomCode - Room code
     * @param {string} playerName - Player name
     * @returns {Object|null} Room data or null on failure
     */
    async joinRoom(roomCode, playerName) {
        try {
            const code = roomCode.toUpperCase();
            const response = await fetch(`/api/room/${code}/join`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: playerName })
            });
            const data = await response.json();

            if (data.error) {
                console.error('Failed to join room:', data.error);
                return null;
            }

            this.roomCode = code;
            this.playerToken = data.token;
            this.playerSlot = data.slot;
            this.playerName = playerName;
            this.isHost = false;
            this.isMultiplayer = true;

            this.saveToken(code, data.token);

            // Connect room WebSocket
            wsManager.connectRoom(code, data.token);

            return data;
        } catch (error) {
            console.error('Failed to join room:', error);
            return null;
        }
    }

    /**
     * Start the multiplayer game (host only)
     * @returns {boolean} Success
     */
    async startMultiplayerGame() {
        if (!this.roomCode || !this.isHost) return false;

        try {
            const response = await fetch(`/api/room/${this.roomCode}/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: this.playerToken })
            });
            const data = await response.json();

            if (data.error) {
                console.error('Failed to start game:', data.error);
                return false;
            }

            return true;
        } catch (error) {
            console.error('Failed to start multiplayer game:', error);
            return false;
        }
    }

    /**
     * Leave the current room
     */
    leaveRoom() {
        wsManager.disconnect();
        this.roomCode = null;
        this.playerToken = null;
        this.playerSlot = null;
        this.isHost = false;
        this.isMultiplayer = false;
    }

    /**
     * Save token to localStorage for reconnection
     */
    saveToken(roomCode, token) {
        localStorage.setItem(`coven_token_${roomCode}`, token);
    }

    /**
     * Load token from localStorage
     */
    loadToken(roomCode) {
        return localStorage.getItem(`coven_token_${roomCode}`);
    }

    /**
     * Send player input via REST API (solo) or WebSocket (multiplayer)
     * @param {*} value - Input value
     */
    async sendInput(value) {
        if (this.isProcessing) return;
        this.isProcessing = true;

        // In multiplayer mode, send via WebSocket
        if (this.isMultiplayer) {
            wsManager.sendInput(value);
            this.isProcessing = false;
            return;
        }

        // Solo mode: send via REST API
        const inputType = this.pendingInput ? this.pendingInput.type : null;
        const prevTrickCount = (this.state && this.state.trick_history) ? this.state.trick_history.length : 0;

        try {
            const response = await fetch(`/api/game/${this.sessionId}/input`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ value })
            });
            const data = await response.json();

            if (data.error) {
                console.error('Input error:', data.error);
                return;
            }

            this.lastInputType = inputType;

            // Play animation steps sequentially, inserting trick result popups at trick boundaries
            let shownTrickCount = prevTrickCount;
            if (data.animation_steps && data.animation_steps.length > 0) {
                for (const step of data.animation_steps) {
                    const stepTrickCount = (step.trick_history || []).length;

                    if (stepTrickCount > shownTrickCount) {
                        for (let i = shownTrickCount; i < stepTrickCount; i++) {
                            await uiManager.showTrickResult(step.trick_history[i]);
                        }
                        uiManager.updateTrickPlays([]);
                        shownTrickCount = stepTrickCount;
                    }

                    uiManager.updateTrickPlays(step.current_trick_plays || []);
                    await new Promise(r => setTimeout(r, 800));
                }
            }

            const newTrickCount = (data.state.trick_history || []).length;
            if (inputType === 'choose_card' && newTrickCount > shownTrickCount) {
                for (let i = shownTrickCount; i < newTrickCount; i++) {
                    await uiManager.showTrickResult(data.state.trick_history[i]);
                }
            }

            // Check for round change and show summary
            await this._checkRoundSummary(data.state);

            this.state = data.state;
            this.pendingInput = data.state.pending_input;

            this.updateUI(false);

        } catch (error) {
            console.error('Failed to send input:', error);
        } finally {
            this.isProcessing = false;
        }
    }

    /**
     * Send input via WebSocket (legacy)
     * @param {*} value - Input value
     */
    sendInputWS(value) {
        if (this.isProcessing) return;
        this.isProcessing = true;
        wsManager.sendInput(value);
    }

    /**
     * Handle state update from WebSocket
     * @param {Object} state - Updated game state
     */
    async handleStateUpdate(state) {
        this.isProcessing = false;

        // In multiplayer, update playerSlot from viewer_slot if provided
        if (state.viewer_slot !== undefined) {
            this.playerSlot = state.viewer_slot;
        }

        // Detect round change and show summary
        await this._checkRoundSummary(state);

        this.state = state;
        this.pendingInput = state.pending_input;

        this.updateUI();
    }

    /**
     * Check if round changed and show summary popup
     * @param {Object} newState - The new game state
     */
    async _checkRoundSummary(newState) {
        const newRoundNo = newState.round_no;

        // Initialize snapshot on first state
        if (this.prevRoundNo === null) {
            this.prevRoundNo = newRoundNo;
            this.roundStartPlayers = JSON.parse(JSON.stringify(newState.players || []));
            return;
        }

        // Round changed - show summary of completed round
        if (newRoundNo > this.prevRoundNo && !newState.game_over) {
            const completedRound = this.prevRoundNo + 1; // 1-based display

            // this.state has the last state from the previous round (end-of-round data)
            // this.roundStartPlayers has the start-of-round player snapshot
            const endPlayers = this.state ? this.state.players : newState.players;
            const startPlayers = this.roundStartPlayers || [];

            if (startPlayers.length > 0 && endPlayers && endPlayers.length > 0) {
                // Use log entries from the previous state (end of round)
                const log = (this.state && this.state.log) ? this.state.log : (newState.log || []);
                const roundLog = log.filter(entry =>
                    !entry.startsWith('===') &&
                    !entry.startsWith('アップグレード:')
                );

                await uiManager.showRoundSummary(completedRound, startPlayers, endPlayers, roundLog);
            }

            // Save new snapshot for the next round
            this.prevRoundNo = newRoundNo;
            this.roundStartPlayers = JSON.parse(JSON.stringify(newState.players || []));
        }
    }

    /**
     * Update UI based on current state
     * @param {boolean} animateTrickPlays - Whether to animate trick plays
     */
    updateUI(animateTrickPlays = false) {
        if (!this.state) return;

        // Update game state display
        uiManager.updateGameState(this.state, animateTrickPlays);

        // Check for game over
        if (this.state.game_over) {
            uiManager.showResult(this.state.players);
            return;
        }

        // Handle pending input
        if (this.pendingInput) {
            this.handlePendingInput();
        }
    }

    /**
     * Handle pending input request
     */
    handlePendingInput() {
        const input = this.pendingInput;
        if (!input) return;

        // "waiting" type means it's another player's turn - just show indicator
        if (input.type === 'waiting') {
            uiManager.showInput(input, null);
            return;
        }

        // Update hand if available
        if (input.context && input.context.hand) {
            const legal = input.context.legal || null;
            uiManager.updatePlayerHand(input.context.hand, legal);
        }

        // Show input UI
        uiManager.showInput(input, (value) => {
            this.sendInput(value);
        });
    }

    /**
     * Get current game state
     * @returns {Object|null} Current state
     */
    getState() {
        return this.state;
    }

    /**
     * Check if game is over
     * @returns {boolean}
     */
    isGameOver() {
        return this.state && this.state.game_over;
    }
}

// Global instance
const gameManager = new GameManager();
