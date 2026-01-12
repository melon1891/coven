/**
 * Game Manager for Coven Rich UI
 */

class GameManager {
    constructor() {
        this.sessionId = null;
        this.state = null;
        this.pendingInput = null;
        this.isProcessing = false;
        this.lastInputType = null;  // Track last input type for animation
    }

    /**
     * Start a new game
     * @param {number|null} seed - Optional seed for reproducibility
     */
    async startGame(seed = null) {
        try {
            const url = seed !== null ? `/api/game/new?seed=${seed}` : '/api/game/new';
            const response = await fetch(url, { method: 'POST' });
            const data = await response.json();

            if (data.error) {
                console.error('Failed to start game:', data.error);
                return false;
            }

            this.sessionId = data.session_id;
            this.state = data.state;
            this.pendingInput = data.state.pending_input;

            // Connect WebSocket
            wsManager.connect(this.sessionId);

            return true;
        } catch (error) {
            console.error('Failed to start game:', error);
            return false;
        }
    }

    /**
     * Send player input via REST API
     * @param {*} value - Input value
     */
    async sendInput(value) {
        if (this.isProcessing) return;
        this.isProcessing = true;

        // Remember the input type before sending
        const inputType = this.pendingInput ? this.pendingInput.type : null;

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
            this.state = data.state;
            this.pendingInput = data.state.pending_input;

            // Debug: log trick plays
            console.log('Input type:', inputType, 'Trick plays:', data.state.current_trick_plays);

            // Update UI with animation flag
            this.updateUI(inputType === 'choose_card');

        } catch (error) {
            console.error('Failed to send input:', error);
        } finally {
            this.isProcessing = false;
        }
    }

    /**
     * Send input via WebSocket
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
    handleStateUpdate(state) {
        this.isProcessing = false;
        this.state = state;
        this.pendingInput = state.pending_input;
        this.updateUI();
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
