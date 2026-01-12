/**
 * WebSocket Manager for Coven Rich UI
 */

class WebSocketManager {
    constructor() {
        this.ws = null;
        this.sessionId = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.handlers = {
            state_update: [],
            error: [],
            connected: [],
            disconnected: []
        };
    }

    /**
     * Connect to WebSocket server
     * @param {string} sessionId - Game session ID
     */
    connect(sessionId) {
        this.sessionId = sessionId;
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
     * Setup WebSocket event handlers
     */
    setupEventHandlers() {
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
            this.emit('connected', { sessionId: this.sessionId });
        };

        this.ws.onclose = (event) => {
            console.log('WebSocket disconnected:', event.code, event.reason);
            this.emit('disconnected', { code: event.code, reason: event.reason });

            // Attempt reconnection
            if (this.sessionId && this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                console.log(`Reconnecting... attempt ${this.reconnectAttempts}`);
                setTimeout(() => this.connect(this.sessionId), this.reconnectDelay * this.reconnectAttempts);
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
        if (this.handlers[event]) {
            this.handlers[event].push(handler);
        }
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
            this.sessionId = null; // Prevent reconnection
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
