/**
 * WebSocket Manager for Coven Rich UI
 */

class WebSocketManager {
    constructor() {
        this.ws = null;
        this.sessionId = null;
        this.roomCode = null;
        this.token = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.handlers = {
            state_update: [],
            trick_animation: [],
            error: [],
            connected: [],
            disconnected: [],
            lobby_state: [],
            player_joined: [],
            player_disconnected: [],
            player_reconnected: [],
            game_starting: []
        };
    }

    /**
     * Connect to WebSocket server (solo mode)
     * @param {string} sessionId - Game session ID
     */
    connect(sessionId) {
        this.sessionId = sessionId;
        this.roomCode = null;
        this.token = null;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${sessionId}`;

        try {
            this.ws = new WebSocket(wsUrl);
            this.setupEventHandlers();
        } catch (error) {
            console.error('WebSocket connection error:', error);
            this.emit('error', { message: 'Failed to connect to server' });
        }
    }

    /**
     * Connect to a room WebSocket (multiplayer mode)
     * @param {string} roomCode - Room code
     * @param {string} token - Player token
     */
    connectRoom(roomCode, token) {
        this.roomCode = roomCode;
        this.token = token;
        this.sessionId = null;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/room/${roomCode}?token=${token}`;

        try {
            this.ws = new WebSocket(wsUrl);
            this.setupEventHandlers();
        } catch (error) {
            console.error('WebSocket room connection error:', error);
            this.emit('error', { message: 'Failed to connect to room' });
        }
    }

    /**
     * Setup WebSocket event handlers
     */
    setupEventHandlers() {
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
            this.emit('connected', { sessionId: this.sessionId, roomCode: this.roomCode });
        };

        this.ws.onclose = (event) => {
            console.log('WebSocket disconnected:', event.code, event.reason);
            this.emit('disconnected', { code: event.code, reason: event.reason });

            // Attempt reconnection
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                if (this.roomCode && this.token) {
                    this.reconnectAttempts++;
                    console.log(`Reconnecting to room... attempt ${this.reconnectAttempts}`);
                    setTimeout(() => this.connectRoom(this.roomCode, this.token), this.reconnectDelay * this.reconnectAttempts);
                } else if (this.sessionId) {
                    this.reconnectAttempts++;
                    console.log(`Reconnecting... attempt ${this.reconnectAttempts}`);
                    setTimeout(() => this.connect(this.sessionId), this.reconnectDelay * this.reconnectAttempts);
                }
            }
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.emit('error', { message: 'Connection error' });
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (error) {
                console.error('Failed to parse message:', error);
            }
        };
    }

    /**
     * Handle incoming messages
     * @param {Object} data - Parsed message data
     */
    handleMessage(data) {
        const { type, ...rest } = data;

        switch (type) {
            case 'state_update':
                this.emit('state_update', rest.data || rest);
                break;
            case 'trick_animation':
                this.emit('trick_animation', rest.data || rest);
                break;
            case 'lobby_state':
                this.emit('lobby_state', rest.data || rest);
                break;
            case 'player_joined':
                this.emit('player_joined', rest.data || rest);
                break;
            case 'player_disconnected':
                this.emit('player_disconnected', rest.data || rest);
                break;
            case 'player_reconnected':
                this.emit('player_reconnected', rest.data || rest);
                break;
            case 'game_starting':
                this.emit('game_starting', rest.data || rest);
                break;
            case 'error':
                this.emit('error', rest);
                break;
            default:
                console.log('Unknown message type:', type, rest);
        }
    }

    /**
     * Send input to server
     * @param {*} inputData - Input data to send
     */
    sendInput(inputData) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'input',
                data: inputData
            }));
        } else {
            console.error('WebSocket not connected');
            this.emit('error', { message: 'Not connected to server' });
        }
    }

    /**
     * Request current state
     */
    requestState() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'get_state'
            }));
        }
    }

    /**
     * Register event handler
     * @param {string} event - Event name
     * @param {Function} handler - Handler function
     */
    on(event, handler) {
        if (!this.handlers[event]) {
            this.handlers[event] = [];
        }
        this.handlers[event].push(handler);
    }

    /**
     * Emit event to handlers
     * @param {string} event - Event name
     * @param {*} data - Event data
     */
    emit(event, data) {
        if (this.handlers[event]) {
            this.handlers[event].forEach(handler => handler(data));
        }
    }

    /**
     * Disconnect WebSocket
     */
    disconnect() {
        if (this.ws) {
            this.sessionId = null;
            this.roomCode = null;
            this.token = null;
            this.ws.close();
            this.ws = null;
        }
    }

    /**
     * Check if connected
     * @returns {boolean}
     */
    isConnected() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }
}

// Global instance
const wsManager = new WebSocketManager();
