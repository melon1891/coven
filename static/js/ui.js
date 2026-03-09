/**
 * UI Manager for Coven Rich UI
 */

class UIManager {
    constructor() {
        this.screens = {
            start: document.getElementById('start-screen'),
            lobby: document.getElementById('lobby-screen'),
            game: document.getElementById('game-screen'),
            result: document.getElementById('result-screen')
        };

        // Cache DOM elements
        this.elements = {
            // Header
            roundNo: document.getElementById('round-no'),
            phaseDisplay: document.getElementById('phase-display'),

            // Play area
            trickDisplay: document.getElementById('trick-display'),
            trickInfo: document.getElementById('trick-info'),
            inputArea: document.getElementById('input-area'),
            inputPrompt: document.getElementById('input-prompt'),
            inputContent: document.getElementById('input-content'),
            playerHand: document.getElementById('player-hand'),

            // Player info
            p1Gold: document.getElementById('p1-gold'),
            p1Vp: document.getElementById('p1-vp'),
            p1Grace: document.getElementById('p1-grace'),
            p1Debt: document.getElementById('p1-debt'),
            p1Workers: document.getElementById('p1-workers'),
            p1Declared: document.getElementById('p1-declared'),
            p1Won: document.getElementById('p1-won'),
            p1Witches: document.getElementById('p1-witches'),

            // Opponents
            opponents: {
                p2: document.getElementById('opponent-p2'),
                p3: document.getElementById('opponent-p3'),
                p4: document.getElementById('opponent-p4')
            },

            // Other
            upgradesList: document.getElementById('upgrades-list'),
            gameLog: document.getElementById('game-log'),
            trickHistory: document.getElementById('trick-history'),
            resultRankings: document.getElementById('result-rankings')
        };
    }

    /**
     * Switch to a specific screen
     * @param {string} screenName - Screen name (start, game, result)
     */
    showScreen(screenName) {
        Object.values(this.screens).forEach(screen => {
            screen.classList.remove('active');
        });
        if (this.screens[screenName]) {
            this.screens[screenName].classList.add('active');
        }
    }

    /**
     * Update lobby display
     * @param {Object} data - Lobby state data with players array
     */
    updateLobby(data) {
        if (!data) return;

        const slots = document.querySelectorAll('.player-slot');
        const players = data.players || [];

        // Build a map from slot index to player
        const slotMap = {};
        players.forEach(p => { slotMap[p.slot] = p; });

        slots.forEach((slotEl, i) => {
            const nameEl = slotEl.querySelector('.slot-name');
            const statusEl = slotEl.querySelector('.slot-status');
            const p = slotMap[i];

            if (p) {
                slotEl.classList.remove('empty');
                slotEl.classList.add('occupied');
                nameEl.textContent = p.name || `Player ${i + 1}`;
                if (p.slot === 0) {
                    statusEl.textContent = 'HOST';
                    statusEl.className = 'slot-status host';
                } else if (p.is_connected === false) {
                    statusEl.textContent = '切断';
                    statusEl.className = 'slot-status';
                } else {
                    statusEl.textContent = '接続中';
                    statusEl.className = 'slot-status connected';
                }
            } else {
                slotEl.classList.remove('occupied');
                slotEl.classList.add('empty');
                nameEl.textContent = '(空席 - Botが入ります)';
                statusEl.textContent = '';
                statusEl.className = 'slot-status';
            }
        });
    }

    /**
     * Show waiting indicator (when it's another player's turn)
     * @param {string} waitingFor - Name of the player being waited on
     */
    showWaitingIndicator(waitingFor) {
        this.elements.inputPrompt.textContent = '';
        this.elements.inputContent.innerHTML = `
            <div class="waiting-indicator">
                <span class="spinner"></span>
                ${waitingFor ? `${this.escapeHtml(waitingFor)} の入力を待っています...` : '他のプレイヤーを待っています...'}
            </div>
        `;
    }

    /**
     * Get rotated position for a player based on local player's slot
     * In solo mode: P1=bottom, P2=left, P3=top, P4=right
     * In multiplayer: rotate so local player is always at bottom
     * @param {string} playerName - Player name like "P1", "P2", etc.
     * @returns {string} Position: 'bottom', 'left', 'top', 'right'
     */
    getRotatedPosition(playerName) {
        const positions = ['bottom', 'left', 'top', 'right'];

        if (!gameManager.isMultiplayer) {
            const defaultMap = { 'P1': 'bottom', 'P2': 'left', 'P3': 'top', 'P4': 'right' };
            return defaultMap[playerName] || 'bottom';
        }

        const mySlot = gameManager.playerSlot || 0;
        const playerSlot = parseInt(playerName.slice(1)) - 1;  // P1->0, P2->1, etc.
        const relativeSlot = (playerSlot - mySlot + 4) % 4;
        return positions[relativeSlot];
    }

    /**
     * Update game state display
     * @param {Object} state - Game state from server
     * @param {boolean} animateTrickPlays - Whether to animate trick plays
     */
    updateGameState(state, animateTrickPlays = false) {
        if (!state) return;

        // Update header
        this.elements.roundNo.textContent = (state.round_no || 0) + 1;
        const totalRoundsEl = document.getElementById('total-rounds');
        if (totalRoundsEl && state.rounds) {
            totalRoundsEl.textContent = state.rounds;
        }
        this.elements.phaseDisplay.textContent = this.formatPhase(state.phase);

        // Update players with view rotation
        if (state.players && state.players.length > 0) {
            const mySlot = gameManager.isMultiplayer ? (gameManager.playerSlot || 0) : 0;
            const myPlayer = state.players[mySlot];
            // Build opponents in rotated order (left, top, right)
            const opponentSlots = [(mySlot + 1) % 4, (mySlot + 2) % 4, (mySlot + 3) % 4];
            const opponents = opponentSlots.map(s => state.players[s]).filter(Boolean);
            this.updatePlayerInfo(myPlayer);
            this.updateOpponents(opponents, state.sealed_by_player || {});
        }

        // Update upgrades
        this.updateUpgrades(state.revealed_upgrades || []);

        // Update log
        this.updateLog(state.log || []);

        // Update trick history
        this.updateTrickHistory(state.trick_history || []);

        // Update current trick plays (animate when all 4 cards are shown at once)
        const plays = state.current_trick_plays || [];
        const shouldAnimate = animateTrickPlays && plays.length === 4;
        console.log('updateGameState: plays.length =', plays.length, 'animateTrickPlays =', animateTrickPlays, 'shouldAnimate =', shouldAnimate);
        this.updateTrickPlays(plays, shouldAnimate);
    }

    /**
     * Format phase name for display
     * @param {string} phase - Phase identifier
     * @returns {string} Formatted phase name
     */
    formatPhase(phase) {
        const phaseNames = {
            'round_start': 'ラウンド開始',
            'declaration': '宣言',
            'grace_hand_swap': '手札交換',
            'seal': '封印',
            'trick': 'トリック',
            'upgrade_pick': 'アップグレード',
            'fourth_place_bonus': '4位ボーナス',
            'grace_priority': '先行権',
            'worker_placement': 'ワーカー配置',
            'wage_payment': '給料支払い',
            'game_end': 'ゲーム終了'
        };
        return phaseNames[phase] || phase || '不明';
    }

    /**
     * Update P1 player info
     * @param {Object} player - Player data
     */
    updatePlayerInfo(player) {
        if (!player) return;

        // Update the player info header with correct name
        const infoHeader = document.querySelector('#player-info h3');
        if (infoHeader) {
            if (gameManager.isMultiplayer) {
                infoHeader.textContent = `${player.name || 'You'} (あなた)`;
            } else {
                infoHeader.textContent = 'P1 (あなた)';
            }
        }

        this.elements.p1Gold.textContent = player.gold || 0;
        this.elements.p1Vp.textContent = player.vp || 0;
        this.elements.p1Grace.textContent = player.grace_points || 0;
        if (this.elements.p1Debt) {
            this.elements.p1Debt.textContent = player.accumulated_debt || 0;
        }

        const workers = player.workers || (player.basic_workers_total || 0);
        this.elements.p1Workers.textContent = workers;

        this.elements.p1Declared.textContent = (player.declared_tricks !== null && player.declared_tricks !== undefined) ? player.declared_tricks : '-';
        this.elements.p1Won.textContent = player.tricks_won || 0;

        // Update witches
        if (player.witches && player.witches.length > 0) {
            this.elements.p1Witches.innerHTML = player.witches.map(w =>
                `<span class="upgrade-tag" data-upgrade="${w}">${this.formatUpgradeName(w)}<span class="tooltip">${this.getUpgradeEffect(w)}</span></span>`
            ).join(' ');
            this.setupTooltipTouchHandlers(this.elements.p1Witches);
        } else {
            this.elements.p1Witches.innerHTML = '';
        }
    }

    /**
     * Update opponent displays
     * @param {Array} opponents - Array of opponent data
     * @param {Object} sealedByPlayer - Sealed cards per player name
     */
    updateOpponents(opponents, sealedByPlayer = {}) {
        const opponentIds = ['p2', 'p3', 'p4'];

        opponents.forEach((opp, index) => {
            const el = this.elements.opponents[opponentIds[index]];
            if (!el || !opp) return;

            el.querySelector('.player-name').textContent = opp.name || `P${index + 2}`;
            el.querySelector('.player-strategy').textContent = '';  // Hide CPU strategy
            el.querySelector('.stat.gold').textContent = opp.gold || 0;
            el.querySelector('.stat.vp').textContent = `${opp.vp || 0} VP`;
            el.querySelector('.stat.grace').textContent = opp.grace_points || 0;

            // Show sealed cards
            const cardsEl = el.querySelector('.opponent-cards');
            if (cardsEl) {
                const playerName = opp.name || `P${index + 2}`;
                const sealed = sealedByPlayer[playerName] || [];
                if (sealed.length > 0) {
                    cardsEl.innerHTML = '<span class="sealed-label">封印:</span> ' +
                        sealed.map(c => {
                            if (typeof c === 'string') {
                                // String format like "S01", "H03", "T"
                                return `<span class="sealed-card">${this.formatCardString(c)}</span>`;
                            }
                            const suitSymbol = this.getSuitSymbol(c.suit);
                            const suitClass = (c.suit === 'Heart' || c.suit === 'Diamond') ? 'suit-red' : 'suit-black';
                            return `<span class="sealed-card ${suitClass}">${suitSymbol}${c.rank}</span>`;
                        }).join(' ');
                } else {
                    cardsEl.innerHTML = '';
                }
            }
        });
    }

    /**
     * Get suit symbol
     */
    getSuitSymbol(suit) {
        const symbols = { 'Spade': '♠', 'Heart': '♥', 'Diamond': '♦', 'Club': '♣', 'Trump': '★' };
        return symbols[suit] || suit;
    }

    /**
     * Format card string like "S01" -> "♠1", "H03" -> "♥3", "T" -> "★"
     */
    formatCardString(str) {
        if (!str) return '';
        if (str === 'T') return '<span class="suit-red">★</span>';
        const suitChar = str[0];
        const rank = parseInt(str.slice(1), 10);
        const suitMap = { 'S': ['♠', false], 'H': ['♥', true], 'D': ['♦', true], 'C': ['♣', false], 'T': ['★', true] };
        const [symbol, isRed] = suitMap[suitChar] || [suitChar, false];
        const cls = isRed ? 'suit-red' : 'suit-black';
        return `<span class="${cls}">${symbol}${rank}</span>`;
    }

    /**
     * Update upgrades display
     * @param {Array} upgrades - Available upgrades
     */
    updateUpgrades(upgrades) {
        if (!upgrades || upgrades.length === 0) {
            this.elements.upgradesList.innerHTML = '<span class="text-secondary">なし</span>';
            return;
        }

        this.elements.upgradesList.innerHTML = upgrades.map(u =>
            `<span class="upgrade-tag" data-upgrade="${u}">${this.formatUpgradeName(u)}<span class="tooltip">${this.getUpgradeEffect(u)}</span></span>`
        ).join('');

        // Add mobile touch support
        this.setupTooltipTouchHandlers(this.elements.upgradesList);
    }

    /**
     * Format upgrade name for display
     * @param {string} name - Upgrade identifier
     * @returns {string} Formatted name
     */
    formatUpgradeName(name) {
        const names = {
            'UP_TRADE': '交易拠点',
            'UP_HUNT': '魔物討伐',
            'UP_PRAY': '祈りの祭壇',
            'UP_RITUAL': '儀式の祭壇',
            'WITCH_BLACKROAD': '黒路の魔女',
            'WITCH_BLOODHUNT': '血誓の討伐官',
            'WITCH_HERD': '群導の魔女',
            'WITCH_NEGOTIATE': '交渉の魔女',
            'WITCH_BLESSING': '祈祷の魔女',
            'WITCH_MIRROR': '鏡の魔女',
            'WITCH_ZERO_MASTER': '慎重な予言者',
            'TAKE_GOLD': '金貨を取る'
        };
        return names[name] || name;
    }

    /**
     * Update game log
     * @param {Array} log - Log entries
     */
    updateLog(log) {
        const recentLogs = log.slice(-20);
        this.elements.gameLog.innerHTML = recentLogs.map(entry => {
            const isHighlight = entry.includes('===') || entry.includes('wins') || entry.includes('VP');
            return `<div class="log-entry ${isHighlight ? 'highlight' : ''}">${this.escapeHtml(entry)}</div>`;
        }).join('');

        // Auto-scroll to bottom
        this.elements.gameLog.scrollTop = this.elements.gameLog.scrollHeight;
    }

    /**
     * Update trick history
     * @param {Array} history - Trick history
     */
    updateTrickHistory(history) {
        if (!history || history.length === 0) {
            this.elements.trickHistory.innerHTML = '<span class="text-secondary">まだトリックなし</span>';
            return;
        }

        this.elements.trickHistory.innerHTML = history.map(trick => {
            const playsStr = trick.plays.map(p => {
                const cardDisplay = typeof p.card === 'object' ? p.card.display : p.card;
                return `${p.player}: ${cardDisplay}`;
            }).join(', ');
            return `<div class="trick-entry">T${trick.trick_no}: ${playsStr} - <span class="trick-winner">${trick.winner}</span></div>`;
        }).join('');
    }

    /**
     * Update current trick plays display
     * @param {Array} plays - Current trick plays
     * @param {boolean} animate - Whether to animate cards appearing sequentially
     */
    updateTrickPlays(plays, animate = false) {
        console.log('updateTrickPlays called: animate =', animate, 'plays =', plays);

        // Clear all slots
        document.querySelectorAll('.trick-card-slot').forEach(slot => {
            slot.innerHTML = '';
        });

        if (!plays || plays.length === 0) return;

        plays.forEach((play, index) => {
            const position = this.getRotatedPosition(play.player);
            const slot = document.querySelector(`.trick-card-slot[data-position="${position}"]`);
            if (slot && play.card) {
                const cardEl = this.createCardElement(play.card);

                if (animate) {
                    // Set initial state (hidden)
                    cardEl.style.opacity = '0';
                    cardEl.style.transform = 'scale(0.7)';
                    slot.appendChild(cardEl);

                    // Animate with sequential delay
                    const delay = index * 300; // 300ms between each card
                    setTimeout(() => {
                        cardEl.style.transition = 'opacity 0.25s ease-out, transform 0.25s ease-out';
                        cardEl.style.opacity = '1';
                        cardEl.style.transform = 'scale(1)';
                    }, delay + 50); // +50ms to ensure initial state is rendered
                } else {
                    slot.appendChild(cardEl);
                }
            }
        });
    }

    /**
     * Update player hand display
     * @param {Array} hand - Cards in hand
     * @param {Array} legalCards - Legal cards (optional)
     * @param {Function} onCardClick - Click handler (optional)
     */
    updatePlayerHand(hand, legalCards = null, onCardClick = null) {
        this.elements.playerHand.innerHTML = '';

        if (!hand || hand.length === 0) {
            this.elements.playerHand.innerHTML = '<span class="text-secondary">カードなし</span>';
            return;
        }

        hand.forEach((card, index) => {
            const cardEl = this.createCardElement(card);
            cardEl.classList.add('animate-deal');
            cardEl.style.animationDelay = `${index * 0.1}s`;

            // Check if legal
            if (legalCards) {
                const isLegal = legalCards.some(lc =>
                    lc.suit === card.suit && lc.rank === card.rank
                );
                if (isLegal) {
                    cardEl.classList.add('legal', 'selectable');
                } else {
                    cardEl.classList.add('illegal');
                }
            } else if (onCardClick) {
                cardEl.classList.add('selectable');
            }

            if (onCardClick && !cardEl.classList.contains('illegal')) {
                cardEl.addEventListener('click', () => onCardClick(card));
            }

            this.elements.playerHand.appendChild(cardEl);
        });
    }

    /**
     * Create a card DOM element
     * @param {Object|string} card - Card data (object or string like "S06")
     * @returns {HTMLElement} Card element
     */
    createCardElement(card) {
        const cardEl = document.createElement('div');
        cardEl.className = 'card';

        // Parse card if it's a string (e.g., "S06", "H12", "T")
        let suit, rank, isTrump;
        if (typeof card === 'string') {
            const parsed = this.parseCardString(card);
            suit = parsed.suit;
            rank = parsed.rank;
            isTrump = parsed.isTrump;
        } else {
            suit = card.suit ? card.suit.toLowerCase() : 'unknown';
            rank = card.rank;
            isTrump = card.is_trump;
        }

        cardEl.dataset.suit = suit;
        cardEl.dataset.rank = rank || 0;

        const suitSymbols = {
            'spade': '\u2660',
            'heart': '\u2665',
            'diamond': '\u2666',
            'club': '\u2663',
            'trump': '\u2605'
        };

        const rankDisplay = isTrump ? 'T' : rank;
        const suitSymbol = suitSymbols[suit] || '?';

        cardEl.innerHTML = `
            <div class="card-corner top-left">
                <span class="card-rank">${rankDisplay}</span>
            </div>
            <div class="card-center"></div>
            <div class="card-corner bottom-right">
                <span class="card-rank">${rankDisplay}</span>
            </div>
        `;

        return cardEl;
    }

    /**
     * Parse card string to object
     * @param {string} cardStr - Card string like "S06", "H12", "T"
     * @returns {Object} Parsed card object
     */
    parseCardString(cardStr) {
        if (!cardStr || cardStr === 'T') {
            return { suit: 'trump', rank: null, isTrump: true };
        }

        const suitMap = {
            'S': 'spade',
            'H': 'heart',
            'D': 'diamond',
            'C': 'club',
            'T': 'trump'
        };

        const suitChar = cardStr.charAt(0).toUpperCase();
        const rankStr = cardStr.slice(1);
        const rank = rankStr ? parseInt(rankStr, 10) : null;

        return {
            suit: suitMap[suitChar] || 'unknown',
            rank: rank,
            isTrump: suitChar === 'T'
        };
    }

    /**
     * Create mini card display (for logs, etc.)
     * @param {Object} card - Card data
     * @returns {string} HTML string
     */
    createMiniCard(card) {
        const suit = card.suit ? card.suit.toLowerCase() : 'unknown';
        const display = card.display || `${card.suit?.[0] || '?'}${card.rank || ''}`;
        return `<span class="card-mini" data-suit="${suit}">${display}</span>`;
    }

    /**
     * Show input prompt
     * @param {Object} inputRequest - Input request data
     * @param {Function} onSubmit - Submit handler
     */
    showInput(inputRequest, onSubmit) {
        if (!inputRequest) {
            this.elements.inputPrompt.textContent = '待機中...';
            this.elements.inputContent.innerHTML = '';
            return;
        }

        const { type, context } = inputRequest;

        switch (type) {
            case 'waiting':
                this.showWaitingIndicator(inputRequest.waiting_for);
                break;
            case 'declaration':
                this.showDeclarationInput(context, onSubmit);
                break;
            case 'seal':
                this.showSealInput(context, onSubmit);
                break;
            case 'choose_card':
                this.showChooseCardInput(context, onSubmit);
                break;
            case 'grace_hand_swap':
                this.showGraceHandSwapInput(context, onSubmit);
                break;
            case 'upgrade':
                this.showUpgradeInput(context, onSubmit);
                break;
            case 'upgrade_level_choice':
                this.showUpgradeLevelChoiceInput(context, onSubmit);
                break;
            case 'fourth_place_bonus':
                this.showFourthPlaceBonusInput(context, onSubmit);
                break;
            case 'ritual_choice':
                this.showRitualChoiceInput(context, onSubmit);
                break;
            case 'grace_priority':
                this.showGracePriorityInput(context, onSubmit);
                break;
            case 'worker_actions':
                this.showWorkerActionsInput(context, onSubmit);
                break;
            default:
                this.elements.inputPrompt.textContent = `Unknown input: ${type}`;
                this.elements.inputContent.innerHTML = '';
        }
    }

    /**
     * Declaration input UI
     */
    showDeclarationInput(context, onSubmit) {
        this.elements.inputPrompt.textContent = '何トリック勝ちますか？';

        let value = 2;
        this.elements.inputContent.innerHTML = `
            <div class="declaration-slider">
                <input type="range" id="declaration-range" min="0" max="4" value="${value}">
                <span class="declaration-value" id="declaration-value">${value}</span>
            </div>
            <button class="btn btn-primary" id="declaration-submit">宣言</button>
        `;

        const range = document.getElementById('declaration-range');
        const valueDisplay = document.getElementById('declaration-value');
        const submitBtn = document.getElementById('declaration-submit');

        range.addEventListener('input', (e) => {
            value = parseInt(e.target.value);
            valueDisplay.textContent = value;
        });

        submitBtn.addEventListener('click', () => onSubmit(value));

        // Update hand display
        this.updatePlayerHand(context.hand || []);
    }

    /**
     * Seal card input UI
     */
    showSealInput(context, onSubmit) {
        this.elements.inputPrompt.textContent = '封印するカードを選んでください（プレイしません）';
        this.elements.inputContent.innerHTML = '';

        this.updatePlayerHand(context.hand || [], context.hand, (card) => {
            // Immediately remove the sealed card from the hand display
            const remainingHand = [...(context.hand || [])];
            const idx = remainingHand.findIndex(c => c.suit === card.suit && c.rank === card.rank);
            if (idx !== -1) remainingHand.splice(idx, 1);
            this.updatePlayerHand(remainingHand);
            onSubmit(card);
        });
    }

    /**
     * Choose card input UI
     */
    showChooseCardInput(context, onSubmit) {
        const leadCard = context.lead_card;
        let prompt = 'カードを出してください';
        if (leadCard) {
            const suitName = this.getSuitName(leadCard.suit);
            prompt = `${suitName}をフォローするか、好きなカードを出してください`;
        } else {
            prompt = '好きなカードでリードしてください';
        }
        this.elements.inputPrompt.textContent = prompt;
        this.elements.inputContent.innerHTML = '';

        // Show plays so far
        if (context.plays_so_far && context.plays_so_far.length > 0) {
            this.updateTrickPlays(context.plays_so_far);
        }

        this.updatePlayerHand(context.hand || [], context.legal || [], (card) => {
            // Immediately remove the played card from the hand display
            const remainingHand = [...(context.hand || [])];
            const idx = remainingHand.findIndex(c => c.suit === card.suit && c.rank === card.rank);
            if (idx !== -1) remainingHand.splice(idx, 1);
            this.updatePlayerHand(remainingHand);
            onSubmit(card);
        });
    }

    /**
     * Get Japanese suit name
     */
    getSuitName(suit) {
        const suitNames = {
            'Spade': 'スペード',
            'spade': 'スペード',
            'Heart': 'ハート',
            'heart': 'ハート',
            'Diamond': 'ダイヤ',
            'diamond': 'ダイヤ',
            'Club': 'クラブ',
            'club': 'クラブ',
            'Trump': '切り札',
            'trump': '切り札'
        };
        return suitNames[suit] || suit;
    }

    /**
     * Grace hand swap input UI
     */
    showGraceHandSwapInput(context, onSubmit) {
        this.elements.inputPrompt.textContent = `手札を交換しますか？（コスト: ${context.cost}恩寵、所持: ${context.grace_points}）`;

        const hand = context.hand || [];
        let selectedCards = [];

        this.elements.inputContent.innerHTML = `
            <div class="hand-swap-grid" id="swap-grid"></div>
            <div class="swap-actions">
                <button class="btn btn-secondary" id="swap-skip">スキップ</button>
                <button class="btn btn-primary" id="swap-confirm" disabled>交換確定</button>
            </div>
        `;

        const grid = document.getElementById('swap-grid');
        const skipBtn = document.getElementById('swap-skip');
        const confirmBtn = document.getElementById('swap-confirm');

        hand.forEach(card => {
            const cardEl = this.createCardElement(card);
            cardEl.classList.add('selectable');

            const checkbox = document.createElement('div');
            checkbox.className = 'card-checkbox';
            cardEl.appendChild(checkbox);

            cardEl.addEventListener('click', () => {
                const index = selectedCards.findIndex(c => c.suit === card.suit && c.rank === card.rank);
                if (index >= 0) {
                    selectedCards.splice(index, 1);
                    cardEl.classList.remove('selected');
                } else {
                    selectedCards.push(card);
                    cardEl.classList.add('selected');
                }
                confirmBtn.disabled = selectedCards.length === 0;
            });

            grid.appendChild(cardEl);
        });

        skipBtn.addEventListener('click', () => onSubmit([]));
        confirmBtn.addEventListener('click', () => onSubmit(selectedCards));

        this.elements.playerHand.innerHTML = '';
    }

    /**
     * Upgrade selection input UI
     */
    showUpgradeInput(context, onSubmit) {
        this.elements.inputPrompt.textContent = 'アップグレードを選んでください';

        const revealed = context.revealed || [];
        const taken = context.already_taken || [];

        this.elements.inputContent.innerHTML = '';

        revealed.forEach(upgrade => {
            const isTaken = taken.includes(upgrade);
            const option = document.createElement('div');
            option.className = `upgrade-option ${isTaken ? 'taken' : ''}`;

            option.innerHTML = `
                <div class="upgrade-name">${this.formatUpgradeName(upgrade)}</div>
                <div class="upgrade-effect">${this.getUpgradeEffect(upgrade)}</div>
            `;

            if (!isTaken) {
                option.addEventListener('click', () => onSubmit(upgrade));
            }

            this.elements.inputContent.appendChild(option);
        });

        // Add take gold option
        if (context.can_take_gold) {
            const goldOption = document.createElement('div');
            goldOption.className = 'upgrade-option';
            goldOption.innerHTML = `
                <div class="upgrade-name">金貨を取る</div>
                <div class="upgrade-effect">+${context.gold_amount}金貨</div>
            `;
            goldOption.addEventListener('click', () => onSubmit('TAKE_GOLD'));
            this.elements.inputContent.appendChild(goldOption);
        }
    }

    /**
     * Upgrade level choice input UI (Lv2 or separate)
     */
    showUpgradeLevelChoiceInput(context, onSubmit) {
        const upgrade = context.upgrade || '';
        this.elements.inputPrompt.textContent = `${this.formatUpgradeName(upgrade)} の強化方法を選択`;

        this.elements.inputContent.innerHTML = '';

        const lv2Option = document.createElement('div');
        lv2Option.className = 'upgrade-option';
        lv2Option.innerHTML = `
            <div class="upgrade-name">Lv2に強化</div>
            <div class="upgrade-effect">1スポット、効果+1</div>
        `;
        lv2Option.addEventListener('click', () => onSubmit('true'));
        this.elements.inputContent.appendChild(lv2Option);

        const separateOption = document.createElement('div');
        separateOption.className = 'upgrade-option';
        separateOption.innerHTML = `
            <div class="upgrade-name">別枠配置</div>
            <div class="upgrade-effect">2つの独立したLv1スポット</div>
        `;
        separateOption.addEventListener('click', () => onSubmit('false'));
        this.elements.inputContent.appendChild(separateOption);
    }

    /**
     * Get upgrade effect description
     */
    getUpgradeEffect(upgrade) {
        const effects = {
            'UP_TRADE': '共有スポット: 2金（Lv2: 3金）',
            'UP_HUNT': '共有スポット: 1VP（Lv2: 2VP）',
            'UP_PRAY': '共有スポット: 1恩寵（Lv2: 2恩寵）',
            'UP_RITUAL': '共有スポット: 2恩寵or2金（Lv2: 3恩寵or3金）※ワーカー永久消費',
            'WITCH_BLACKROAD': 'パッシブ: 交易+1金',
            'WITCH_BLOODHUNT': 'パッシブ: 討伐+1VP',
            'WITCH_HERD': 'パッシブ: 毎R給料-1',
            'WITCH_NEGOTIATE': '共有スポット: 1恩寵→2金',
            'WITCH_BLESSING': 'パッシブ: 毎R+1恩寵',
            'WITCH_MIRROR': 'パッシブ: 他者宣言成功時+1金',
            'WITCH_ZERO_MASTER': 'パッシブ: 0宣言成功で3恩寵/3金/2VP選択'
        };
        return effects[upgrade] || '';
    }

    /**
     * Fourth place bonus input UI
     */
    showFourthPlaceBonusInput(context, onSubmit) {
        this.elements.inputPrompt.textContent = '4位でした！ボーナスを選んでください：';

        this.elements.inputContent.innerHTML = `
            <button class="btn btn-primary" id="bonus-gold">+${context.gold_option}金貨</button>
            <button class="btn btn-secondary" id="bonus-grace">+${context.grace_option}恩寵</button>
        `;

        document.getElementById('bonus-gold').addEventListener('click', () => onSubmit('gold'));
        document.getElementById('bonus-grace').addEventListener('click', () => onSubmit('grace'));
    }

    /**
     * Ritual choice input UI
     */
    showRitualChoiceInput(context, onSubmit) {
        const graceAmount = context.grace_amount || 2;
        const goldAmount = context.gold_amount || 2;
        this.elements.inputPrompt.textContent = '儀式の祭壇: 報酬を選んでください（ワーカー1人を永久消費）';

        this.elements.inputContent.innerHTML = `
            <button class="btn btn-secondary" id="ritual-grace">+${graceAmount}恩寵</button>
            <button class="btn btn-primary" id="ritual-gold">+${goldAmount}金</button>
        `;

        document.getElementById('ritual-grace').addEventListener('click', () => onSubmit('grace'));
        document.getElementById('ritual-gold').addEventListener('click', () => onSubmit('gold'));
    }

    /**
     * Grace priority input UI
     */
    showGracePriorityInput(context, onSubmit) {
        const cost = context.cost || 2;
        const grace = context.grace || 0;
        this.elements.inputPrompt.textContent =
            `同トリック数のプレイヤーがいます。恩寵 ${cost} を消費して先行権を得ますか？（恩寵: ${grace}）`;

        this.elements.inputContent.innerHTML = `
            <button class="btn btn-primary" id="grace-yes">先行権を使う</button>
            <button class="btn btn-secondary" id="grace-no">使わない</button>
        `;

        document.getElementById('grace-yes').addEventListener('click', () => onSubmit(true));
        document.getElementById('grace-no').addEventListener('click', () => onSubmit(false));
    }

    /**
     * Worker actions input UI
     */
    showWorkerActionsInput(context, onSubmit) {
        const workers = context.available_workers || 0;
        const actions = context.available_actions || [];
        const recruitCost = context.recruit_cost || 2;

        this.elements.inputPrompt.textContent = `ワーカーを配置（残り${workers}人）`;

        this.elements.inputContent.innerHTML = `
            <div class="worker-actions-grid" id="actions-grid"></div>
        `;

        const grid = document.getElementById('actions-grid');

        // Format action display name from action string
        const formatAction = (action) => {
            if (action === 'TRADE') return { name: '共通交易', effect: '+2金' };
            if (action === 'HUNT') return { name: '共通討伐', effect: '+1VP' };
            if (action === 'PRAY') return { name: '共通祈り', effect: '+1恩寵' };
            if (action === 'RECRUIT') return { name: '雇用', effect: `-${recruitCost}金→+1人` };
            if (action.startsWith('SPOT:')) {
                // Format: SPOT:{owner}:{idx}:{type}
                const parts = action.split(':');
                const ownerName = parts[1];
                const spotName = parts[3];
                const playerName = context.player_name || '';
                const isOwn = (ownerName === playerName);
                const ownerTag = isOwn ? '' : ` [${ownerName}]`;
                const spotInfo = {
                    'UP_TRADE': { name: '交易', effect: '+金' },
                    'UP_HUNT': { name: '討伐', effect: '+VP' },
                    'UP_PRAY': { name: '祈り', effect: '+恩寵' },
                    'UP_RITUAL': { name: '儀式', effect: '恩寵or金(ワーカー消費)' },
                    'WITCH_NEGOTIATE': { name: '交渉の魔女', effect: '1恩寵→2金' },
                };
                const info = spotInfo[spotName] || { name: spotName, effect: '' };
                return { name: `${info.name}${ownerTag}`, effect: isOwn ? info.effect : `${info.effect} (${ownerName}+1金)` };
            }
            return { name: action, effect: '' };
        };

        actions.forEach(action => {
            const info = formatAction(action);

            const btn = document.createElement('button');
            btn.className = 'worker-action-btn';
            btn.dataset.action = action;
            btn.innerHTML = `
                <div class="action-name">${info.name}</div>
                <div class="action-effect">${info.effect}</div>
            `;

            btn.addEventListener('click', () => {
                // Single action selection — submit immediately
                onSubmit(action);
            });

            grid.appendChild(btn);
        });
    }

    /**
     * Show game result
     * @param {Array} players - Sorted players by VP
     */
    showResult(players) {
        this.showScreen('result');

        const rankings = players
            .map((p, i) => ({ ...p, rank: i + 1 }))
            .sort((a, b) => b.vp - a.vp);

        this.elements.resultRankings.innerHTML = rankings.map((p, i) => {
            let label;
            if (gameManager.isMultiplayer) {
                label = p.is_bot ? ' (CPU)' : '';
            } else {
                label = p.is_bot ? ' (CPU)' : ' (You)';
            }
            const debtInfo = p.accumulated_debt > 0 ? ` <span class="ranking-debt">負債:${p.accumulated_debt}</span>` : '';
            return `
                <div class="ranking-entry rank-${i + 1}">
                    <span class="ranking-position">${i === 0 ? '1st' : i === 1 ? '2nd' : i === 2 ? '3rd' : '4th'}</span>
                    <span class="ranking-name">${this.escapeHtml(p.name)}${label}</span>
                    <span class="ranking-vp">${p.vp} VP</span>
                    <span class="ranking-detail">${p.gold || 0}G / ${p.grace_points || 0}恩寵${debtInfo}</span>
                </div>
            `;
        }).join('');
    }

    /**
     * Setup touch handlers for tooltips (mobile support)
     * @param {HTMLElement} container - Container with tooltip elements
     */
    setupTooltipTouchHandlers(container) {
        const tags = container.querySelectorAll('.upgrade-tag');

        tags.forEach(tag => {
            // Touch start - show tooltip
            tag.addEventListener('touchstart', (e) => {
                // Hide all other tooltips first
                document.querySelectorAll('.upgrade-tag.tooltip-active').forEach(el => {
                    if (el !== tag) el.classList.remove('tooltip-active');
                });
                tag.classList.toggle('tooltip-active');
                e.preventDefault();
            }, { passive: false });
        });

        // Hide tooltip when tapping elsewhere (only add once)
        if (!this._tooltipDocListenerAdded) {
            document.addEventListener('touchstart', (e) => {
                if (!e.target.closest('.upgrade-tag')) {
                    document.querySelectorAll('.upgrade-tag.tooltip-active').forEach(el => {
                        el.classList.remove('tooltip-active');
                    });
                }
            }, { passive: true });
            this._tooltipDocListenerAdded = true;
        }
    }

    /**
     * Show trick result popup
     * @param {Object} trick - Trick data {trick_no, winner, plays: [{player, card}]}
     * @returns {Promise} Resolves when user clicks OK
     */
    showTrickResult(trick) {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'trick-result-overlay';

            const popup = document.createElement('div');
            popup.className = 'trick-result-popup';

            const title = document.createElement('div');
            title.className = 'trick-result-title';
            title.textContent = `トリック ${trick.trick_no} 結果`;
            popup.appendChild(title);

            const cardsArea = document.createElement('div');
            cardsArea.className = 'trick-result-cards';

            trick.plays.forEach((play) => {
                const playEl = document.createElement('div');
                playEl.className = 'trick-result-play';
                if (play.player === trick.winner) {
                    playEl.classList.add('winner');
                }

                const nameEl = document.createElement('div');
                nameEl.className = 'trick-result-player-name';
                nameEl.textContent = play.player;

                const cardEl = this.createCardElement(play.card);

                playEl.appendChild(nameEl);
                playEl.appendChild(cardEl);
                cardsArea.appendChild(playEl);
            });

            popup.appendChild(cardsArea);

            const winnerInfo = document.createElement('div');
            winnerInfo.className = 'trick-result-winner';
            winnerInfo.textContent = `${trick.winner} がトリックを取りました！`;
            popup.appendChild(winnerInfo);

            const okBtn = document.createElement('button');
            okBtn.className = 'btn btn-primary trick-result-ok';
            okBtn.textContent = 'OK';
            okBtn.addEventListener('click', () => {
                overlay.classList.add('fade-out');
                setTimeout(() => {
                    overlay.remove();
                    resolve();
                }, 200);
            });
            popup.appendChild(okBtn);

            overlay.appendChild(popup);
            document.body.appendChild(overlay);
            okBtn.focus();
        });
    }

    /**
     * Show round-end summary popup
     * @param {number} roundNo - Completed round number (1-based display)
     * @param {Array} prevPlayers - Player snapshots from start of round
     * @param {Array} currPlayers - Player snapshots at end of round
     * @param {Array} logEntries - Log entries for this round
     * @returns {Promise} Resolves when user clicks OK
     */
    showRoundSummary(roundNo, prevPlayers, currPlayers, logEntries) {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'round-summary-overlay';

            const popup = document.createElement('div');
            popup.className = 'round-summary-popup';

            const title = document.createElement('div');
            title.className = 'round-summary-title';
            title.textContent = `Round ${roundNo} 結果`;
            popup.appendChild(title);

            const content = document.createElement('div');
            content.className = 'round-summary-content';

            // Show each player's changes
            currPlayers.forEach((curr, i) => {
                const prev = prevPlayers[i] || {};
                const playerEl = document.createElement('div');
                playerEl.className = 'round-summary-player';

                const nameEl = document.createElement('div');
                nameEl.className = 'round-summary-player-name';
                nameEl.textContent = curr.name || `P${i + 1}`;
                playerEl.appendChild(nameEl);

                const changes = [];
                const goldDiff = (curr.gold || 0) - (prev.gold || 0);
                const vpDiff = (curr.vp || 0) - (prev.vp || 0);
                const graceDiff = (curr.grace_points || 0) - (prev.grace_points || 0);
                const workersDiff = (curr.workers || curr.basic_workers_total || 0) - (prev.workers || prev.basic_workers_total || 0);
                const debtDiff = (curr.accumulated_debt || 0) - (prev.accumulated_debt || 0);

                if (goldDiff !== 0) changes.push({ label: '金貨', value: goldDiff, cls: goldDiff > 0 ? 'positive' : 'negative' });
                if (vpDiff !== 0) changes.push({ label: 'VP', value: vpDiff, cls: vpDiff > 0 ? 'positive' : 'negative' });
                if (graceDiff !== 0) changes.push({ label: '恩寵', value: graceDiff, cls: graceDiff > 0 ? 'positive' : 'negative' });
                if (workersDiff !== 0) changes.push({ label: 'ワーカー', value: workersDiff, cls: workersDiff > 0 ? 'positive' : 'negative' });
                if (debtDiff > 0) changes.push({ label: '負債', value: debtDiff, cls: 'negative' });

                const statsEl = document.createElement('div');
                statsEl.className = 'round-summary-stats';

                if (changes.length > 0) {
                    statsEl.innerHTML = changes.map(c =>
                        `<span class="round-summary-change ${c.cls}">${c.label}: ${c.value > 0 ? '+' : ''}${c.value}</span>`
                    ).join('');
                } else {
                    statsEl.innerHTML = '<span class="round-summary-change">変化なし</span>';
                }

                playerEl.appendChild(statsEl);

                // Show declaration result
                const declared = curr.declared_tricks;
                const won = curr.tricks_won_this_round !== undefined ? curr.tricks_won_this_round : curr.tricks_won;
                if (declared !== null && declared !== undefined) {
                    const declEl = document.createElement('div');
                    declEl.className = 'round-summary-declaration';
                    const success = declared === won;
                    declEl.innerHTML = `宣言: ${declared} / 獲得: ${won || 0} <span class="${success ? 'decl-success' : 'decl-fail'}">${success ? '成功' : '失敗'}</span>`;
                    playerEl.appendChild(declEl);
                }

                content.appendChild(playerEl);
            });

            popup.appendChild(content);

            // Show relevant log entries
            if (logEntries && logEntries.length > 0) {
                const logSection = document.createElement('div');
                logSection.className = 'round-summary-log';
                const logTitle = document.createElement('div');
                logTitle.className = 'round-summary-log-title';
                logTitle.textContent = 'ログ';
                logSection.appendChild(logTitle);
                const logList = document.createElement('div');
                logList.className = 'round-summary-log-entries';
                logEntries.forEach(entry => {
                    const entryEl = document.createElement('div');
                    entryEl.className = 'round-summary-log-entry';
                    entryEl.textContent = entry;
                    logList.appendChild(entryEl);
                });
                logSection.appendChild(logList);
                popup.appendChild(logSection);
            }

            const okBtn = document.createElement('button');
            okBtn.className = 'btn btn-primary round-summary-ok';
            okBtn.textContent = 'OK';
            okBtn.addEventListener('click', () => {
                overlay.classList.add('fade-out');
                setTimeout(() => {
                    overlay.remove();
                    resolve();
                }, 200);
            });
            popup.appendChild(okBtn);

            overlay.appendChild(popup);
            document.body.appendChild(overlay);
            okBtn.focus();
        });
    }

    /**
     * Escape HTML characters
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Global instance
const uiManager = new UIManager();
