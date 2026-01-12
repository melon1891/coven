/**
 * UI Manager for Coven Rich UI
 */

class UIManager {
    constructor() {
        this.screens = {
            start: document.getElementById('start-screen'),
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
            p1Workers: document.getElementById('p1-workers'),
            p1TradeLevel: document.getElementById('p1-trade-level'),
            p1HuntLevel: document.getElementById('p1-hunt-level'),
            p1PrayLevel: document.getElementById('p1-pray-level'),
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
     * Update game state display
     * @param {Object} state - Game state from server
     * @param {boolean} animateTrickPlays - Whether to animate trick plays
     */
    updateGameState(state, animateTrickPlays = false) {
        if (!state) return;

        // Update header
        this.elements.roundNo.textContent = (state.round_no || 0) + 1;
        this.elements.phaseDisplay.textContent = this.formatPhase(state.phase);

        // Update players
        if (state.players && state.players.length > 0) {
            this.updatePlayerInfo(state.players[0]); // P1
            this.updateOpponents(state.players.slice(1)); // P2-P4
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

        this.elements.p1Gold.textContent = player.gold || 0;
        this.elements.p1Vp.textContent = player.vp || 0;
        this.elements.p1Grace.textContent = player.grace_points || 0;

        const workers = player.workers || ((player.basic_workers_total || 0) + (player.upgraded_workers || 0));
        this.elements.p1Workers.textContent = workers;

        this.elements.p1TradeLevel.textContent = `Lv${player.trade_level || 0}`;
        this.elements.p1HuntLevel.textContent = `Lv${player.hunt_level || 0}`;
        this.elements.p1PrayLevel.textContent = `Lv${player.pray_level || 0}`;

        this.elements.p1Declared.textContent = player.declared_tricks !== undefined ? player.declared_tricks : '-';
        this.elements.p1Won.textContent = player.tricks_won_this_round || 0;

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
     */
    updateOpponents(opponents) {
        const opponentIds = ['p2', 'p3', 'p4'];

        opponents.forEach((opp, index) => {
            const el = this.elements.opponents[opponentIds[index]];
            if (!el || !opp) return;

            el.querySelector('.player-name').textContent = opp.name || `P${index + 2}`;
            el.querySelector('.player-strategy').textContent = '';  // Hide CPU strategy
            el.querySelector('.stat.gold').textContent = opp.gold || 0;
            el.querySelector('.stat.vp').textContent = `${opp.vp || 0} VP`;
            el.querySelector('.stat.grace').textContent = opp.grace_points || 0;
        });
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
            'UP_TRADE': '交易強化',
            'UP_HUNT': '討伐強化',
            'UP_PRAY': '祈り強化',
            'RECRUIT_INSTANT': '即時雇用',
            'RECRUIT_WAGE_DISCOUNT': '給料軽減',
            'UP_DONATE': '寄付解放',
            'UP_RITUAL': '儀式解放',
            'WITCH_BLACKROAD': '闇商人',
            'WITCH_BLOODHUNT': '血の狩人',
            'WITCH_HERD': '群れの守護',
            'WITCH_TREASURE': '財宝変換',
            'WITCH_BLESSING': '祝福の魔女',
            'WITCH_PROPHET': '予言の魔女',
            'WITCH_ZERO_MASTER': '零の達人',
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

        // Position mapping: P1=bottom, P2=left, P3=top, P4=right
        const positionMap = {
            'P1': 'bottom',
            'P2': 'left',
            'P3': 'top',
            'P4': 'right'
        };

        plays.forEach((play, index) => {
            const position = positionMap[play.player];
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
            case 'fourth_place_bonus':
                this.showFourthPlaceBonusInput(context, onSubmit);
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
     * Get upgrade effect description
     */
    getUpgradeEffect(upgrade) {
        const effects = {
            'UP_TRADE': '交易で+2金貨',
            'UP_HUNT': '討伐で+1VP',
            'UP_PRAY': '祈りで+1恩寵',
            'RECRUIT_INSTANT': '即座に+1ワーカー',
            'RECRUIT_WAGE_DISCOUNT': '毎ラウンド給料-1',
            'UP_DONATE': '寄付アクション解放',
            'UP_RITUAL': '儀式アクション解放',
            'WITCH_BLACKROAD': '交易+2金貨',
            'WITCH_BLOODHUNT': '討伐+1VP',
            'WITCH_HERD': '給料-1',
            'WITCH_TREASURE': '1金貨→1恩寵',
            'WITCH_BLESSING': '毎ラウンド+1恩寵',
            'WITCH_PROPHET': '宣言成功時+1金貨',
            'WITCH_ZERO_MASTER': '0宣言成功で+2恩寵'
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
     * Worker actions input UI
     */
    showWorkerActionsInput(context, onSubmit) {
        const workers = context.available_workers || 0;
        const actions = context.available_actions || ['TRADE', 'HUNT', 'RECRUIT', 'PRAY'];
        const gold = context.gold || 0;
        const recruitCost = context.recruit_cost || 2;
        const canRecruit = context.can_recruit && gold >= recruitCost;

        this.elements.inputPrompt.textContent = `${workers}人のワーカーを配置`;

        let selectedActions = [];
        let recruitUsed = false;

        const updateUI = () => {
            countDisplay.textContent = selectedActions.length;
            submitBtn.disabled = selectedActions.length === 0;
            // Update button states
            document.querySelectorAll('.worker-action-btn').forEach(btn => {
                const action = btn.dataset.action;
                const count = selectedActions.filter(a => a === action).length;
                btn.querySelector('.action-count').textContent = count > 0 ? `x${count}` : '';
                btn.classList.toggle('selected', count > 0);
            });
        };

        this.elements.inputContent.innerHTML = `
            <div class="worker-actions-grid" id="actions-grid"></div>
            <div class="worker-count">選択: <span id="selected-count">0</span> / ${workers}</div>
            <div class="action-buttons">
                <button class="btn btn-secondary" id="actions-clear">クリア</button>
                <button class="btn btn-primary" id="actions-submit" disabled>確定</button>
            </div>
        `;

        const grid = document.getElementById('actions-grid');
        const countDisplay = document.getElementById('selected-count');
        const submitBtn = document.getElementById('actions-submit');
        const clearBtn = document.getElementById('actions-clear');

        const actionInfo = {
            'TRADE': { name: '交易', effect: '+金貨' },
            'HUNT': { name: '討伐', effect: '+VP' },
            'RECRUIT': { name: '雇用', effect: `-${recruitCost}金, +1人` },
            'PRAY': { name: '祈り', effect: '+恩寵' },
            'DONATE': { name: '寄付', effect: '-2金, +1恩寵' },
            'RITUAL': { name: '儀式', effect: '+1恩寵' }
        };

        actions.forEach(action => {
            const info = actionInfo[action] || { name: action, effect: '' };
            const isRecruitDisabled = action === 'RECRUIT' && !canRecruit;

            const btn = document.createElement('button');
            btn.className = 'worker-action-btn';
            btn.dataset.action = action;
            btn.disabled = isRecruitDisabled;
            btn.innerHTML = `
                <div class="action-name">${info.name}</div>
                <div class="action-effect">${info.effect}</div>
                <div class="action-count"></div>
            `;

            btn.addEventListener('click', () => {
                if (btn.disabled) return;

                if (selectedActions.length < workers) {
                    selectedActions.push(action);

                    // RECRUIT can only be used once
                    if (action === 'RECRUIT') {
                        recruitUsed = true;
                        btn.disabled = true;
                    }
                    updateUI();
                }
            });

            // Right-click to remove
            btn.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                const idx = selectedActions.lastIndexOf(action);
                if (idx >= 0) {
                    selectedActions.splice(idx, 1);
                    if (action === 'RECRUIT') {
                        recruitUsed = false;
                        btn.disabled = !canRecruit;
                    }
                    updateUI();
                }
            });

            grid.appendChild(btn);
        });

        clearBtn.addEventListener('click', () => {
            selectedActions = [];
            recruitUsed = false;
            document.querySelectorAll('.worker-action-btn').forEach(btn => {
                const action = btn.dataset.action;
                if (action === 'RECRUIT') {
                    btn.disabled = !canRecruit;
                } else {
                    btn.disabled = false;
                }
            });
            updateUI();
        });

        submitBtn.addEventListener('click', () => onSubmit(selectedActions));
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

        this.elements.resultRankings.innerHTML = rankings.map((p, i) => `
            <div class="ranking-entry rank-${i + 1}">
                <span class="ranking-position">${i === 0 ? '1st' : i === 1 ? '2nd' : i === 2 ? '3rd' : '4th'}</span>
                <span class="ranking-name">${p.name}${p.is_bot ? ' (CPU)' : ' (You)'}</span>
                <span class="ranking-vp">${p.vp} VP</span>
            </div>
        `).join('');
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
