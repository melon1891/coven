#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
魔女協会 - Trick-taking x Worker-placement card game

RULES (A plan, NO TRUMP) implemented:
- No trump suit.
- Normal must-follow: if you have the lead suit, you MUST follow it.
- Trick winner: highest rank in the LEAD suit wins. (Other suits cannot win.)
- Each round uses a fixed SET hand per player.
- 6-card set, but only 4 tricks are played:
  - Players see 6 cards, declare target tricks (0..4),
    then "seal" 2 cards (unplayable), then play 4 tricks with remaining 4 cards.
- Declaration match => +1 VP
- Incremental action upgrades (UP_TRADE / UP_HUNT => level +1 up to 1)
- Hiring: hires do NOT act this round, BUT wage IS paid starting this round
- JSONL logging to game_log.jsonl
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any, Set
import random
import sys
import json
from datetime import datetime

# ======= Core Config =======
SUITS = ["Spade", "Heart", "Diamond", "Club"]

ROUNDS = 6
TRICKS_PER_ROUND = 4               # play 4 tricks
CARDS_PER_SET = 5                  # see 5 cards, seal 1, play 4
SETS_PER_GAME = 6                  # match rounds
REVEAL_UPGRADES = 5                # players + 1 (for 4p => 5)
NUM_DECKS = 2                      # 2デッキ = 40カード (5ランク×4スート×2)
TRUMP_COUNT = 2                    # 切り札2枚

START_GOLD = 5
WAGE_CURVE = [1, 1, 1, 1, 2, 2, 2, 3]  # 初期ワーカーの給料（8R対応）
INITIAL_WORKERS = 2  # 初期ワーカー数
MAX_WORKERS = 5      # ワーカー雇用上限
RESCUE_GOLD_FOR_4TH = 1
TAKE_GOLD_INSTEAD = 2
DECLARATION_BONUS_VP = 1  # 宣言成功ボーナス（失敗ペナルティなし）

# === 金貨→VP変換 ===
GOLD_TO_VP_RATE = 2  # ゲーム終了時、2金貨 = 1VP に変換
GOLD_TO_GRACE_RATE = 2  # ゲーム終了時、2金貨 = 1恩寵 に変換（恩寵→VP変換の前に適用）

# === 負債ペナルティ設定 ===
# 給与未払い1金につき何VPを失うか（2 = 1金不足で-2VP）
DEBT_PENALTY_MULTIPLIER = 2
# ペナルティ上限（None = 無制限）
DEBT_PENALTY_CAP: Optional[int] = None

# === 恩寵ポイントシステム ===
# 恩寵機能のON/OFF設定（Falseにすると恩寵なしの旧バージョン動作に戻る）
GRACE_ENABLED = True
# 恩寵→VP変換（5恩寵毎に3VP）
GRACE_VP_PER_N = 5       # N恩寵毎に変換
GRACE_VP_AMOUNT = 3      # 変換で得られるVP
# 恩寵消費効果: シール前に手札全交換（3恩寵で5枚すべて引き直し）
GRACE_HAND_SWAP_COST = 3
# 恩寵獲得: 祈りアクション（ワーカー配置 → 恩寵）
GRACE_PRAY_GAIN = 1  # 基礎獲得量
# 恩寵獲得: 儀式アクション（ワーカー → 恩寵/金、アップグレードで解放）
GRACE_RITUAL_GAIN = 1  # 基礎（旧定数、参照用）
# 恩寵獲得: 宣言0成功
GRACE_DECLARATION_ZERO_BONUS = 1
# 恩寵獲得: トリテ0勝
GRACE_ZERO_TRICKS_BONUS = 1
# 金貨獲得: トリテ0勝
ZERO_TRICKS_GOLD_BONUS = 1
# 4位ボーナス: 恩寵選択時の獲得量
GRACE_4TH_PLACE_BONUS = 2
# 後出し権: トリック中に順番を最後に変更（1ラウンド1回）
GRACE_LAST_PLAY_COST = 2
# 負債軽減: 恩寵消費で負債1を消去
GRACE_DEBT_REDUCTION_COST = 2

# 基本アクション（PRAY は初期から使用可能）
ACTIONS = ["TRADE", "HUNT", "RECRUIT", "PRAY"]

# === ナショナルエコノミー式ワーカー配置 ===
# 共通スポット（ブロッキング: 全体で1ワーカーのみ）
SHARED_TRADE_GOLD = 2    # Trade: 2金
SHARED_HUNT_VP = 1       # Hunt: 1VP
SHARED_PRAY_GRACE = 1    # Pray: 1恩寵
# オープンスポット（制限なし）
RECRUIT_COST = 2          # Recruit: 2金→+1人
# 個人スポット効果（アップグレードカードから）
PERSONAL_TRADE_GOLD = 2   # UP_TRADE: 2金
PERSONAL_HUNT_VP = 1      # UP_HUNT: 1VP
PERSONAL_PRAY_GRACE = 1   # UP_PRAY: 1恩寵
PERSONAL_RITUAL_GRACE = 2  # UP_RITUAL: 2恩寵 or 2金（選択）
PERSONAL_RITUAL_GOLD = 2   # UP_RITUAL: 金選択時
# 魔女個人スポット（強化効果）
WITCH_BLACKROAD_GOLD = 2  # 黒路の魔女: 2金（Trade相当）
WITCH_BLOODHUNT_VP = 1    # 血誓の討伐官: 1VP（Hunt相当）
WITCH_NEGOTIATE_GRACE_COST = 1  # 交渉の魔女: 恩寵消費
WITCH_NEGOTIATE_GOLD = 2       # 交渉の魔女: 金獲得
WITCH_ZERO_GRACE = 3           # 予言者: 恩寵報酬
WITCH_ZERO_GOLD = 3            # 予言者: 金報酬
WITCH_ZERO_VP = 2              # 予言者: VP報酬
# 恩寵による先行権コスト
GRACE_PRIORITY_COST = 2   # 配置/選択順序の先行権

# === CPU性格定義 ===
# grace_awareness: 恩寵獲得の意識（0=無関心, 0.5=適度, 1=積極的）
# prefer_grace: 恩寵を最優先するか（恩寵特化用）
STRATEGIES = {
    'CONSERVATIVE': {
        'name': '堅実',
        'name_en': 'Kenjitsu',
        'desc': '安全プレイ、金貨優先',
        'max_workers': 2,
        'prefer_gold': True,
        'hunt_ratio': 0.2,
        'accept_debt': 0,
        'grace_awareness': 0.5,  # 閾値近ければ恩寵も考慮（強化: 0.3→0.5）
    },
    'VP_AGGRESSIVE': {
        'name': 'VPつっぱ',
        'name_en': 'VP Toppa',
        'desc': 'ワーカー最大化、VP狩り',
        'max_workers': 5,
        'prefer_gold': False,
        'hunt_ratio': 0.8,
        'accept_debt': 99,
        'grace_awareness': 0.6,  # 儀式・祝福魔女を時々取る（強化: 0.4→0.6）
    },
    'BALANCED': {
        'name': 'バランス',
        'name_en': 'Balance',
        'desc': '適度なワーカー、適度な借金',
        'max_workers': 4,
        'prefer_gold': False,
        'hunt_ratio': 0.5,
        'accept_debt': 4,
        'grace_awareness': 0.7,  # バランスよく恩寵も狙う（強化: 0.5→0.7）
    },
    'DEBT_AVOID': {
        'name': '借金回避',
        'name_en': 'DebtAvoid',
        'desc': 'ワーカー控えめ、金貨管理',
        'max_workers': 3,
        'prefer_gold': False,
        'hunt_ratio': 0.4,
        'accept_debt': 1,
        'grace_awareness': 0.6,  # 金貨不要の恩寵は取る（強化: 0.4→0.6）
    },
    'GRACE_FOCUSED': {
        'name': '恩寵特化',
        'name_en': 'Grace Focus',
        'desc': '恩寵ポイント最優先、閾値ボーナス狙い',
        'max_workers': 3,
        'prefer_gold': False,
        'hunt_ratio': 0.3,
        'accept_debt': 2,
        'grace_awareness': 1.0,  # 常に恩寵優先
        'prefer_grace': True,    # 4位ボーナスも恩寵を選択
    },
}

LOG_PATH = "game_log.jsonl"


def assign_random_strategy(rng: random.Random) -> str:
    """CPUにランダムな性格を割り当てる"""
    return rng.choice(list(STRATEGIES.keys()))


# ======= Helper Functions =======

def calculate_debt_penalty(debt: int) -> int:
    """
    負債ペナルティを計算する。
    デフォルト: 1金不足につき DEBT_PENALTY_MULTIPLIER VP のペナルティ
    DEBT_PENALTY_CAP が設定されている場合はその値が上限
    """
    if debt <= 0:
        return 0
    penalty = debt * DEBT_PENALTY_MULTIPLIER
    if DEBT_PENALTY_CAP is not None:
        penalty = min(penalty, DEBT_PENALTY_CAP)
    return penalty


def calculate_debt_penalty_configurable(
    debt: int,
    multiplier: int = 1,
    cap: Optional[int] = None,
    use_tiered: bool = False
) -> int:
    """
    設定可能な負債ペナルティを計算する。

    Args:
        debt: 不足金額
        multiplier: 1金あたりのVPペナルティ倍率
        cap: ペナルティ上限（Noneで無制限）
        use_tiered: Trueで現行の段階式を使用
    """
    if debt <= 0:
        return 0
    if use_tiered:
        return calculate_debt_penalty(debt)
    penalty = debt * multiplier
    if cap is not None:
        penalty = min(penalty, cap)
    return penalty


# ======= Logger =======

class JsonlLogger:
    def __init__(self, path: str):
        self.path = path
        self.game_id = f"game-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}-{random.randint(1000,9999)}"
        self._f = open(self.path, "w", encoding="utf-8")

    def log(self, event: str, payload: Dict[str, Any]) -> None:
        rec = {
            "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "game_id": self.game_id,
            "event": event,
            **payload,
        }
        self._f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._f.flush()

    def close(self) -> None:
        self._f.close()


# ======= Game Data =======

@dataclass(frozen=True)
class Card:
    suit: str  # "Spade", "Heart", "Diamond", "Club", "Trump"
    rank: int  # 1..13 (通常) or 0 (切り札、ランクなし)

    def __str__(self) -> str:
        if self.is_trump():
            return "T"  # 切り札はランクなし
        return f"{self.suit[0]}{self.rank:02d}"

    def is_trump(self) -> bool:
        """切り札カードかどうかを判定"""
        return self.suit == "Trump"


@dataclass
class GameConfig:
    """ゲームルールに関わる設定パラメーター"""
    rounds: int = ROUNDS  # ラウンド数 (4 or 8)
    start_gold: int = START_GOLD
    initial_workers: int = INITIAL_WORKERS
    declaration_bonus_vp: int = DECLARATION_BONUS_VP
    debt_penalty_multiplier: int = DEBT_PENALTY_MULTIPLIER
    debt_penalty_cap: Optional[int] = DEBT_PENALTY_CAP
    gold_to_vp_rate: int = GOLD_TO_VP_RATE
    take_gold_instead: int = TAKE_GOLD_INSTEAD
    rescue_gold_for_4th: int = RESCUE_GOLD_FOR_4TH
    enabled_upgrades: Optional[List[str]] = None  # None = 全アップグレード有効
    rounds: int = ROUNDS  # ゲームのラウンド数（4 or 8）

    def to_dict(self) -> Dict[str, Any]:
        """設定を辞書形式で返す"""
        return {
            "rounds": self.rounds,
            "start_gold": self.start_gold,
            "initial_workers": self.initial_workers,
            "declaration_bonus_vp": self.declaration_bonus_vp,
            "debt_penalty_multiplier": self.debt_penalty_multiplier,
            "debt_penalty_cap": self.debt_penalty_cap,
            "gold_to_vp_rate": self.gold_to_vp_rate,
            "take_gold_instead": self.take_gold_instead,
            "rescue_gold_for_4th": self.rescue_gold_for_4th,
            "enabled_upgrades": self.enabled_upgrades,
            "rounds": self.rounds,
        }


@dataclass
class PlacementState:
    """ナショナルエコノミー式ワーカー配置のラウンド内状態管理"""
    shared_trade_taken: bool = False
    shared_hunt_taken: bool = False
    shared_pray_taken: bool = False
    # プレイヤー別: 使用済み個人スポットのインデックスセット（共有ボード上のスポット）
    personal_spots_used: Dict[str, Set[int]] = field(default_factory=dict)
    # プレイヤー別: 残りワーカー数
    workers_remaining: Dict[str, int] = field(default_factory=dict)
    # 配置順序（トリック勝数順）
    placement_order: List[Any] = field(default_factory=list)  # List[Player]
    # 全プレイヤー参照（共有スポット方式で使用）
    all_players: List[Any] = field(default_factory=list)  # List[Player]


@dataclass
class Player:
    name: str
    is_bot: bool = False
    rng: random.Random = field(default_factory=random.Random)
    strategy: Optional[str] = None  # CPU性格: CONSERVATIVE, VP_AGGRESSIVE, BALANCED, DEBT_AVOID
    ai_bot: bool = False  # AI (Anthropic Haiku) for decisions

    gold: int = START_GOLD
    vp: int = 0

    # Workers
    basic_workers_total: int = INITIAL_WORKERS
    basic_workers_new_hires: int = 0  # hires that become active next round

    # 個人ワーカースポット（アップグレードカードから取得）
    personal_spots: List[str] = field(default_factory=list)

    # Lv2化したスポット名のセット（ここに含まれない2枚持ちは別枠Lv1×2）
    leveled_spots: Set[str] = field(default_factory=set)

    # Permanent witches (flavor for tie-break)
    witches: List[str] = field(default_factory=list)

    # Grace points (恩寵ポイント)
    grace_points: int = 0

    # 累積負債（ゲーム終了時にペナルティ適用）
    accumulated_debt: int = 0

    # 儀式で消費されたワーカー数（ラウンド内追跡、給料計算用）
    ritual_consumed_this_round: int = 0

    # Trick-taking round state
    tricks_won_this_round: int = 0
    declared_tricks: Optional[int] = None
    used_last_play_this_round: bool = False  # 後出し権使用済みフラグ

    # Fixed hand: SETS_PER_GAME sets x CARDS_PER_SET cards
    sets: List[List[Card]] = field(default_factory=list)

    def permanent_witch_count(self) -> int:
        return len(self.witches)


def snapshot_players(players: List[Player]) -> List[Dict[str, Any]]:
    snap: List[Dict[str, Any]] = []
    for p in players:
        snap.append({
            "name": p.name,
            "is_bot": p.is_bot,
            "strategy": p.strategy,
            "strategy_name": STRATEGIES[p.strategy]['name'] if p.strategy else None,
            "gold": p.gold,
            "vp": p.vp,
            "grace_points": p.grace_points,  # 恩寵ポイント
            "workers": p.basic_workers_total,
            "new_hires_pending": p.basic_workers_new_hires,
            "personal_spots": p.personal_spots[:],
            "leveled_spots": list(p.leveled_spots),
            "witches": p.witches[:],
            "declared_tricks": p.declared_tricks,
            "tricks_won": p.tricks_won_this_round,
            "accumulated_debt": p.accumulated_debt,
        })
    return snap


# ======= IO Helpers =======

def prompt_choice(prompt: str, choices: List[str], default: Optional[str] = None) -> str:
    choices_norm = [c.upper() for c in choices]
    while True:
        if default:
            s = input(f"{prompt} ({'/'.join(choices)}), default={default}: ").strip()
            if s == "":
                s = default
        else:
            s = input(f"{prompt} ({'/'.join(choices)}): ").strip()
        s_up = s.upper()
        if s_up in choices_norm:
            return choices[choices_norm.index(s_up)]
        print(f"無効な入力です: {s}")


def print_state(players: List[Player], round_no: int) -> None:
    print("\n" + "=" * 72)
    print(f"ROUND {round_no+1}/{ROUNDS} STATE")
    if GRACE_ENABLED:
        print("[恩寵システム ON]")
    print("-" * 72)
    for p in players:
        base_info = (
            f"{p.name:10s} | Gold={p.gold:2d} VP={p.vp:2d} "
            f"Workers={p.basic_workers_total:2d} (pending={p.basic_workers_new_hires:2d}) "
            f"Spots={len(p.personal_spots)} "
            f"Witches={p.permanent_witch_count()}"
        )
        if GRACE_ENABLED:
            base_info += f" Grace={p.grace_points}"
        if p.accumulated_debt > 0:
            base_info += f" Debt={p.accumulated_debt}"
        print(base_info)
    print("=" * 72)


# ======= Setup =======

def deal_fixed_sets(
    players: List[Player],
    seed: int,
    logger: Optional[JsonlLogger],
    max_rank: int = 5,
    num_decks: int = NUM_DECKS,
) -> None:
    """
    旧方式: ゲーム開始時に全ラウンド分のカードを配る。
    現在はdeal_round_cardsを使用してラウンドごとにリシャッフル。
    """
    rng = random.Random(seed)
    deck: List[Card] = []
    for _ in range(num_decks):
        deck.extend([Card(s, r) for s in SUITS for r in range(1, max_rank + 1)])
    # 切り札カード追加（ランクなし、2枚）
    trumps = [Card("Trump", 0) for _ in range(TRUMP_COUNT)]
    deck.extend(trumps)
    rng.shuffle(deck)

    cards_per_player = SETS_PER_GAME * CARDS_PER_SET

    for p in players:
        cards = [deck.pop() for _ in range(cards_per_player)]
        p.sets = [cards[i*CARDS_PER_SET:(i+1)*CARDS_PER_SET] for i in range(SETS_PER_GAME)]

    if logger:
        hands = {p.name: [[str(c) for c in s] for s in p.sets] for p in players}
        logger.log("deal_hands", {"seed": seed, "hands": hands, "cards_per_set": CARDS_PER_SET})


def deal_round_cards(
    players: List[Player],
    round_no: int,
    rng: random.Random,
    logger: Optional[JsonlLogger],
    max_rank: int = 5,
    num_decks: int = NUM_DECKS,
) -> Tuple[Dict[str, List[Card]], List[Card]]:
    """
    ラウンドごとにデッキをリシャッフルして配札。
    2デッキ（40カード）+ 切り札2枚 = 42枚
    4人×5枚 = 20枚必要

    Returns:
        Tuple of (round_hands, remaining_deck)
    """
    deck: List[Card] = []
    for _ in range(num_decks):
        deck.extend([Card(s, r) for s in SUITS for r in range(1, max_rank + 1)])
    # 切り札カード追加
    trumps = [Card("Trump", 0) for _ in range(TRUMP_COUNT)]
    deck.extend(trumps)
    rng.shuffle(deck)

    round_hands: Dict[str, List[Card]] = {}
    for p in players:
        hand = [deck.pop() for _ in range(CARDS_PER_SET)]
        round_hands[p.name] = hand
        # p.setsに保存（後方互換性のため）
        if len(p.sets) <= round_no:
            p.sets.extend([[] for _ in range(round_no - len(p.sets) + 1)])
        p.sets[round_no] = hand

    if logger:
        logger.log("deal_round", {
            "round": round_no + 1,
            "hands": {name: [str(c) for c in cards] for name, cards in round_hands.items()},
            "cards_per_player": CARDS_PER_SET,
            "deck_size": num_decks * 4 * max_rank + TRUMP_COUNT,
            "remaining_deck_size": len(deck),
        })

    return round_hands, deck


# ======= Upgrades =======

# 利用可能なアップグレードのリスト（設定画面で使用）
ALL_UPGRADES = [
    "UP_TRADE",
    "UP_HUNT",
    "UP_PRAY",     # 祈り強化: 恩寵獲得量+1
    "UP_RITUAL",   # 儀式アクション解放（2恩寵 or 2金 選択）
]

# 魔女カード（ラウンド3のみ登場）
ALL_WITCHES = [
    "WITCH_BLACKROAD",   # 黒路の魔女: パッシブ(個人交易+1金)
    "WITCH_BLOODHUNT",   # 血誓の討伐官: パッシブ(個人討伐+1VP)
    "WITCH_HERD",        # 群導の魔女: 毎R給料-1
    "WITCH_NEGOTIATE",   # 交渉の魔女: 個人スポット(1恩寵→3金)
    "WITCH_BLESSING",    # 祈祷の魔女: 毎R+1恩寵
    "WITCH_MIRROR",      # 鏡の魔女: 他者宣言成功時+1金
    "WITCH_ZERO_MASTER", # 慎重な予言者: 宣言0成功時3恩寵/2金/1VPから選択
]

# デフォルトで有効なアップグレード（魔女を除く）
DEFAULT_ENABLED_UPGRADES = ALL_UPGRADES[:]

# 魔女が登場するラウンド（0-indexed）
WITCH_ROUND = 2  # ラウンド3 = index 2

# 各アップグレードのプール内の枚数
UPGRADE_POOL_COUNTS = {
    "UP_TRADE": 5,
    "UP_HUNT": 5,
    "UP_PRAY": 5,    # 祈り強化
    "UP_RITUAL": 5,  # 儀式アクション解放
}

# 魔女カードのプール内の枚数
WITCH_POOL_COUNTS = {
    "WITCH_BLACKROAD": 1,
    "WITCH_BLOODHUNT": 1,
    "WITCH_HERD": 1,
    "WITCH_NEGOTIATE": 1,
    "WITCH_BLESSING": 1,
    "WITCH_MIRROR": 1,
    "WITCH_ZERO_MASTER": 1,
}


class UpgradeDeck:
    """アップグレードカードのデッキと捨て札を管理するクラス。

    各ラウンドで選ばれなかったカードは捨て札に移動し、
    デッキが足りなくなったら捨て札をリシャッフルして補充する。
    """

    def __init__(self, rng: random.Random, enabled_upgrades: Optional[List[str]] = None):
        self.rng = rng
        if enabled_upgrades is None:
            enabled_upgrades = DEFAULT_ENABLED_UPGRADES
        self.enabled_upgrades = enabled_upgrades

        # 初期デッキを構築
        self.deck: List[str] = []
        for u in enabled_upgrades:
            count = UPGRADE_POOL_COUNTS.get(u, 1)
            self.deck.extend([u] * count)

        # シャッフル
        self.rng.shuffle(self.deck)

        # 捨て札
        self.discard: List[str] = []

    def _reshuffle_if_needed(self, n: int) -> None:
        """デッキ枚数が足りなければ捨て札をリシャッフルして補充"""
        if len(self.deck) < n and len(self.discard) > 0:
            self.deck.extend(self.discard)
            self.discard = []
            self.rng.shuffle(self.deck)

    def reveal(self, n: int) -> List[str]:
        """デッキからn枚を公開（引く）"""
        self._reshuffle_if_needed(n)

        # デッキから引ける分だけ引く
        drawn = self.deck[:n]
        self.deck = self.deck[n:]
        return drawn

    def discard_remaining(self, cards: List[str]) -> None:
        """選ばれなかったカードを捨て札に移動"""
        self.discard.extend(cards)


def reveal_upgrades(rng: random.Random, n: int, enabled_upgrades: Optional[List[str]] = None) -> List[str]:
    """有効なアップグレードからランダムに選択する"""
    if enabled_upgrades is None:
        enabled_upgrades = DEFAULT_ENABLED_UPGRADES

    pool: List[str] = []
    for u in enabled_upgrades:
        count = UPGRADE_POOL_COUNTS.get(u, 1)
        pool.extend([u] * count)

    if not pool:
        return []

    return [rng.choice(pool) for _ in range(n)]


def upgrade_name(u: str) -> str:
    mapping = {
        "UP_TRADE": "交易拠点（個人交易スポット）",
        "UP_HUNT": "魔物討伐（個人討伐スポット）",
        "UP_PRAY": "祈りの祭壇（個人祈りスポット）",
        "UP_RITUAL": "儀式の祭壇（個人儀式スポット）",
        "WITCH_BLACKROAD": "《黒路の魔女》",
        "WITCH_BLOODHUNT": "《血誓の討伐官》",
        "WITCH_HERD": "《群導の魔女》",
        "WITCH_NEGOTIATE": "《交渉の魔女》",
        "WITCH_BLESSING": "《祈祷の魔女》",
        "WITCH_MIRROR": "《鏡の魔女》",
        "WITCH_ZERO_MASTER": "《慎重な予言者》",
    }
    return mapping.get(u, u)


def upgrade_description(u: str) -> str:
    """Return detailed description for an upgrade card."""
    descriptions = {
        "UP_TRADE": "個人交易スポット。毎ラウンド1ワーカーを配置して2金獲得。共通交易がブロックされても使える。",
        "UP_HUNT": "個人討伐スポット。毎ラウンド1ワーカーを配置して1VP獲得。共通討伐がブロックされても使える。",
        "UP_PRAY": "個人祈りスポット。毎ラウンド1ワーカーを配置して1恩寵獲得。",
        "UP_RITUAL": f"個人儀式スポット。{PERSONAL_RITUAL_GRACE}恩寵 or {PERSONAL_RITUAL_GOLD}金を選択。配置したワーカーは永久に失われる。",
        "WITCH_BLACKROAD": "【効果】パッシブ: 個人交易スポット使用時、獲得金+1",
        "WITCH_BLOODHUNT": "【効果】パッシブ: 個人討伐スポット使用時、獲得VP+1",
        "WITCH_HERD": "【効果】毎ラウンド給料合計-1（パッシブ）",
        "WITCH_NEGOTIATE": f"【効果】個人スポット。1恩寵消費→{WITCH_NEGOTIATE_GOLD}金獲得",
        "WITCH_BLESSING": "【効果】毎ラウンド終了時、+1恩寵",
        "WITCH_MIRROR": "【効果】他プレイヤーの宣言成功時、+1金（パッシブ）",
        "WITCH_ZERO_MASTER": f"【効果】宣言0成功時、{WITCH_ZERO_GRACE}恩寵/{WITCH_ZERO_GOLD}金/{WITCH_ZERO_VP}VPから選択",
    }
    return descriptions.get(u, "説明なし")


# Witch card flavor texts
WITCH_FLAVOR = {
    "WITCH_BLACKROAD": """《黒路の魔女》
役割：交易・供給

かつて閉ざされた交易路を、魔法で「通れるもの」に変えた魔女。
その道を、誰が最初に閉ざしたのかは語られない。""",

    "WITCH_BLOODHUNT": """《血誓の討伐官》
役割：魔物討伐・VP加速

討伐の成功は、必ず誓約と引き換えに訪れる。
彼女が交わす血の誓いの内容を、村長は知らない。""",

    "WITCH_HERD": """《群導の魔女》
役割：見習い・雇用支援

見習いたちは彼女の合図ひとつで動く。
だが、誰も彼女に逆らおうとはしない。""",

    "WITCH_NEGOTIATE": """《交渉の魔女》
役割：恩寵→金貨変換

協会への恩寵を担保に、有利な取引を成立させる。
彼女の交渉術の前では、どんな商人も頷くしかない。""",

    "WITCH_BLESSING": """《祈祷の魔女》
役割：恩寵獲得

協会への忠誠を示す者に、彼女は静かに恩寵を与える。
毎ラウンド終了時、その祝福は確実に訪れる。""",

    "WITCH_MIRROR": """《鏡の魔女》
役割：他者の成功を映す

彼女の鏡は他者の成功を映し出し、その輝きを金貨に変える。
他者が栄えるほど、鏡の持ち主もまた潤う。""",

    "WITCH_ZERO_MASTER": """《慎重な予言者》
役割：慎重な戦略・多様な報酬

何も取らないと宣言し、それを守る者を彼女は讃える。
慎重な戦いには、恩寵・富・名誉の三つの道が開かれる。""",
}


def can_take_upgrade(player: Player, u: str) -> bool:
    """アップグレード取得可否（個人スポット方式: 同種2枚まで=Lv2）"""
    if u in ("UP_TRADE", "UP_HUNT", "UP_PRAY", "UP_RITUAL"):
        # 同じスポットは最大2枚（Lv1→Lv2）
        if player.personal_spots.count(u) >= 2:
            return False
        # 恩寵系はGRACE_ENABLED必要
        if u in ("UP_PRAY", "UP_RITUAL"):
            return GRACE_ENABLED
        return True
    return True


def _bot_choose_level_up(player: Player, u: str) -> bool:
    """Botが2枚目のアップグレードをLv2にするか別枠にするか判断。True=Lv2, False=別枠"""
    current_workers = player.basic_workers_total + player.basic_workers_new_hires
    # 儀式はワーカー消費するのでLv2が効率的
    if u == "UP_RITUAL":
        return True
    # ワーカーに余裕があれば別枠（2回使える）、なければLv2（1回で高効率）
    if current_workers >= 4:
        return False  # 別枠
    return True  # Lv2


def apply_upgrade(player: Player, u: str, level_up: Optional[bool] = None) -> None:
    """アップグレード適用（個人スポット方式）
    level_up: 2枚目の場合 True=Lv2化, False=別枠Lv1×2, None=1枚目（自動）
    """
    if u in ("UP_TRADE", "UP_HUNT", "UP_PRAY", "UP_RITUAL"):
        is_second = player.personal_spots.count(u) >= 1
        player.personal_spots.append(u)
        if is_second and level_up:
            player.leveled_spots.add(u)
    elif u.startswith("WITCH_"):
        player.witches.append(u)
        # 個人スポットとしても機能する魔女（BLACKROAD/BLOODHUNTはパッシブ化済み）
        if u == "WITCH_NEGOTIATE":
            player.personal_spots.append(u)


def choose_level_up_or_separate(player: Player, u: str) -> bool:
    """2枚目のアップグレード取得時にLv2化か別枠かを選択。True=Lv2, False=別枠"""
    if player.is_bot:
        return _bot_choose_level_up(player, u)

    upgrade_names = {
        "UP_TRADE": "個人交易",
        "UP_HUNT": "個人討伐",
        "UP_PRAY": "個人祈り",
        "UP_RITUAL": "個人儀式",
    }
    name = upgrade_names.get(u, u)
    print(f"\n{player.name}, {name}の2枚目を獲得します。強化方法を選んでください:")
    print(f"  1. Lv2に強化（1スポット、効果+1）")
    print(f"  2. 別枠配置（2つの独立したLv1スポット）")
    while True:
        s = input("1 or 2: ").strip()
        if s == "1":
            return True
        if s == "2":
            return False
        print("1か2を入力してください。")


def calc_expected_wage(player: Player, round_no: int) -> int:
    """次のラウンドで発生する給料を計算（初期ワーカーのみ給料発生）"""
    initial_workers = min(INITIAL_WORKERS, player.basic_workers_total + player.basic_workers_new_hires)
    return initial_workers * WAGE_CURVE[round_no]


def choose_upgrade_or_gold(player: Player, revealed: List[str], round_no: int = 0, all_players: Optional[List[Player]] = None) -> str:
    available = [u for u in revealed if can_take_upgrade(player, u)]

    if player.is_bot:
        if player.ai_bot and available:
            from ai_bot import ai_choose_upgrade
            result = ai_choose_upgrade(player, revealed, available, round_no, all_players)
            if result is not None:
                return result
        if not available:
            return "GOLD"

        # 性格に基づいた選択
        strat = STRATEGIES.get(player.strategy, STRATEGIES['BALANCED'])
        current_workers = player.basic_workers_total + player.basic_workers_new_hires
        expected_wage = calc_expected_wage(player, round_no)
        grace_awareness = strat.get('grace_awareness', 0.5)

        # 次の5恩寵境界への近さをチェック（全性格共通）
        grace_near_threshold = False
        if GRACE_ENABLED:
            next_boundary = (player.grace_points // GRACE_VP_PER_N + 1) * GRACE_VP_PER_N
            diff = next_boundary - player.grace_points
            if 0 < diff <= 3:  # 次の5恩寵境界まであと3点以内
                grace_near_threshold = True

        # 恩寵アップグレードの優先順位を判定する関数
        def pick_grace_upgrade():
            # 祈り強化 > 儀式解放 > 寄付解放 の順で優先
            if 'UP_PRAY' in available:
                return 'UP_PRAY'
            if 'UP_RITUAL' in available:
                return 'UP_RITUAL'
            if 'WITCH_BLESSING' in available:
                return 'WITCH_BLESSING'
            return None

        # 恩寵特化: 祈り強化・儀式・寄付・祝福魔女を最優先
        if strat.get('prefer_grace', False):
            grace_pick = pick_grace_upgrade()
            if grace_pick:
                return grace_pick

        # 堅実: 常に金貨優先（ただし閾値近ければ祝福魔女は検討）
        if strat['prefer_gold']:
            if grace_near_threshold and 'WITCH_BLESSING' in available:
                if player.rng.random() < grace_awareness:
                    return 'WITCH_BLESSING'
            return "GOLD"

        # VPつっぱ: 常にアップグレード優先
        if player.strategy == 'VP_AGGRESSIVE':
            # 恩寵アップグレードも考慮
            if grace_near_threshold:
                grace_pick = pick_grace_upgrade()
                if grace_pick and player.rng.random() < grace_awareness:
                    return grace_pick
            for u in available:
                if u.startswith('UP_') or u.startswith('WITCH_'):
                    return u
            return 'GOLD'

        # 借金回避: 金貨が足りなければ金貨を取る
        if player.strategy == 'DEBT_AVOID':
            if player.gold < expected_wage + 3:
                return 'GOLD'

        # 恩寵特化: ワーカー補充より恩寵優先
        if strat.get('prefer_grace', False):
            grace_pick = pick_grace_upgrade()
            if grace_pick:
                return grace_pick

        # アップグレード優先度（恩寵意識を反映）
        # 閾値に近い場合は恩寵アップグレードを優先
        if grace_near_threshold and player.rng.random() < grace_awareness:
            grace_pick = pick_grace_upgrade()
            if grace_pick:
                return grace_pick

        for u in available:
            if u.startswith('UP_HUNT'):
                return u
            if u.startswith('UP_TRADE'):
                return u

        # 恩寵アップグレードを通常優先度で検討
        if player.rng.random() < grace_awareness:
            grace_pick = pick_grace_upgrade()
            if grace_pick:
                return grace_pick

        for u in available:
            if u.startswith('WITCH_'):
                return u

        return 'GOLD'

    print(f"\n{player.name}, 報酬を選んでください:")
    if available:
        for i, u in enumerate(available, start=1):
            print(f"  {i}. {upgrade_name(u)} [{u}]")
    else:
        print("  (選択可能なアップグレードがありません)")
    print(f"  G. 代わりに{TAKE_GOLD_INSTEAD}金貨を取る")

    while True:
        s = input("番号またはGを入力: ").strip().upper()
        if s == "G":
            return "GOLD"
        try:
            idx = int(s)
            if 1 <= idx <= len(available):
                return available[idx - 1]
        except ValueError:
            pass
        print("無効な選択です。")


def choose_4th_place_bonus(player: Player, logger: Optional[JsonlLogger] = None, round_no: int = 0) -> str:
    """
    4位ボーナスとして2金か1恩寵かを選択する。
    恩寵システムが無効の場合は自動的に金貨を獲得。
    Returns: "GOLD" or "GRACE"
    """
    if not GRACE_ENABLED:
        # 恩寵システム無効時は金貨のみ
        player.gold += RESCUE_GOLD_FOR_4TH
        return "GOLD"

    if player.is_bot:
        if player.ai_bot:
            from ai_bot import ai_choose_4th_place_bonus
            result = ai_choose_4th_place_bonus(player, RESCUE_GOLD_FOR_4TH, GRACE_4TH_PLACE_BONUS)
            if result is not None:
                if result == "GRACE":
                    player.grace_points += GRACE_4TH_PLACE_BONUS
                else:
                    player.gold += RESCUE_GOLD_FOR_4TH
                return result
        # ボットの選択ロジック
        strat = STRATEGIES.get(player.strategy, STRATEGIES['BALANCED'])

        # 恩寵特化は常に恩寵を選択
        if strat.get('prefer_grace', False):
            player.grace_points += GRACE_4TH_PLACE_BONUS
            return "GRACE"

        # 次の5恩寵境界に近い場合は恩寵を選択
        next_boundary = (player.grace_points // GRACE_VP_PER_N + 1) * GRACE_VP_PER_N
        diff = next_boundary - player.grace_points
        if 0 < diff <= 2:  # 次の5恩寵境界まであと2点以内
            player.grace_points += GRACE_4TH_PLACE_BONUS
            return "GRACE"

        # それ以外は金貨を選択
        player.gold += RESCUE_GOLD_FOR_4TH
        return "GOLD"

    # 人間プレイヤー
    print(f"\n{player.name}, 4位ボーナスを選んでください:")
    print(f"  1. {RESCUE_GOLD_FOR_4TH}金貨を獲得")
    print(f"  2. {GRACE_4TH_PLACE_BONUS}恩寵を獲得")

    while True:
        s = input("番号を入力 (1 or 2): ").strip()
        if s == "1":
            player.gold += RESCUE_GOLD_FOR_4TH
            return "GOLD"
        elif s == "2":
            player.grace_points += GRACE_4TH_PLACE_BONUS
            return "GRACE"
        print("無効な選択です。")


# ======= Declaration (SEE 6 cards -> declare -> seal 2 -> play 4) =======

def declare_tricks(player: Player, round_hand: List[Card], set_index: int, all_players: Optional[List[Player]] = None) -> int:
    if player.is_bot:
        if player.ai_bot:
            from ai_bot import ai_declare_tricks
            result = ai_declare_tricks(player, round_hand, set_index, all_players)
            if result is not None:
                return result
        # 切り札の枚数をカウント
        trump_count = sum(1 for c in round_hand if c.is_trump())
        non_trump = [c for c in round_hand if not c.is_trump()]
        suits = [c.suit for c in non_trump]
        max_same = max((suits.count(s) for s in SUITS), default=0)

        # 基本値を決定
        if max_same >= 3:
            cand = [2, 2, 3, 1, 4]
        elif max_same == 2:
            cand = [1, 2, 2, 0, 3]
        else:
            cand = [0, 1, 1, 2, 2]
        v = player.rng.choice(cand)

        # 切り札があれば宣言数を増やす（切り札1枚につき+1トリック期待）
        v += trump_count
        return max(0, min(TRICKS_PER_ROUND, v))

    print(f"\n{player.name} ラウンド手札 (セット#{set_index+1}, {CARDS_PER_SET}枚): " + " ".join(str(c) for c in round_hand))
    while True:
        s = input(f"{player.name} トリック宣言 (0-{TRICKS_PER_ROUND}): ").strip()
        try:
            v = int(s)
            if 0 <= v <= TRICKS_PER_ROUND:
                return v
        except ValueError:
            pass
        print("無効な宣言です。")


def _choose_zero_master_reward(player: Player, force_bot: bool = False) -> str:
    """慎重な予言者: 宣言0成功時の報酬選択（3恩寵/2金/1VP）"""
    if player.is_bot or force_bot:
        # Bot AI: 金不足なら金、恩寵閾値近ければ恩寵、それ以外VP
        strat = STRATEGIES.get(player.strategy, STRATEGIES['BALANCED'])
        expected_wage = 0
        if strat.get('prefer_gold', False) or player.gold < 3:
            return "GOLD"
        grace_awareness = strat.get('grace_awareness', 0.5)
        if grace_awareness > 0.5:
            next_boundary = (player.grace_points // GRACE_VP_PER_N + 1) * GRACE_VP_PER_N
            diff = next_boundary - player.grace_points
            if diff <= WITCH_ZERO_GRACE:
                return "GRACE"
        return "VP"
    # 人間プレイヤー
    print(f"\n《慎重な予言者》宣言0成功！報酬を選んでください:")
    print(f"  [1] +{WITCH_ZERO_GRACE}恩寵")
    print(f"  [2] +{WITCH_ZERO_GOLD}金")
    print(f"  [3] +{WITCH_ZERO_VP}VP")
    while True:
        s = input("番号を選択: ").strip()
        if s == "1":
            return "GRACE"
        if s == "2":
            return "GOLD"
        if s == "3":
            return "VP"
        print("無効な入力です。1-3で選択してください。")


def _choose_ritual_reward(player: Player, grace_amount: int = PERSONAL_RITUAL_GRACE,
                           gold_amount: int = PERSONAL_RITUAL_GOLD,
                           force_bot: bool = False) -> str:
    """儀式の祭壇: 恩寵 or 金 を選択"""
    if player.is_bot or force_bot:
        strat = STRATEGIES.get(player.strategy, STRATEGIES['BALANCED'])
        expected_wage = calc_expected_wage(player, 0)
        if player.gold < expected_wage + 2:
            return "gold"
        grace_awareness = strat.get('grace_awareness', 0.5)
        if grace_awareness > 0.4:
            return "grace"
        return "gold"
    # 人間プレイヤー
    print(f"\n儀式の祭壇: 報酬を選んでください:")
    print(f"  [1] +{grace_amount}恩寵")
    print(f"  [2] +{gold_amount}金")
    while True:
        s = input("番号を選択: ").strip()
        if s == "1":
            return "grace"
        if s == "2":
            return "gold"
        print("無効な入力です。1-2で選択してください。")


def apply_declaration_bonus(players: List[Player], logger: Optional[JsonlLogger], round_no: int) -> None:
    for p in players:
        if p.tricks_won_this_round == p.declared_tricks:
            before = p.vp
            p.vp += DECLARATION_BONUS_VP
            print(f"宣言成功: {p.name} が {p.declared_tricks} トリックを的中 -> +{DECLARATION_BONUS_VP} VP")

            # ピタリ賞: 宣言成功で+1恩寵
            grace_bonus = 0
            if GRACE_ENABLED:
                grace_bonus = 1
                p.grace_points += 1
                print(f"  (ピタリ賞: +1恩寵)")

            gold_bonus = 0

            # 恩寵システム: 宣言0成功で追加恩寵ボーナス
            if GRACE_ENABLED and p.declared_tricks == 0:
                if "WITCH_ZERO_MASTER" in p.witches:
                    # 慎重な予言者: 3恩寵/2金/1VPから選択
                    choice = _choose_zero_master_reward(p)
                    if choice == "GRACE":
                        p.grace_points += WITCH_ZERO_GRACE
                        grace_bonus += WITCH_ZERO_GRACE
                        print(f"  (《慎重な予言者》効果: +{WITCH_ZERO_GRACE}恩寵)")
                    elif choice == "GOLD":
                        p.gold += WITCH_ZERO_GOLD
                        gold_bonus += WITCH_ZERO_GOLD
                        print(f"  (《慎重な予言者》効果: +{WITCH_ZERO_GOLD}金)")
                    elif choice == "VP":
                        p.vp += WITCH_ZERO_VP
                        print(f"  (《慎重な予言者》効果: +{WITCH_ZERO_VP}VP)")

            if logger:
                logger.log("declaration_bonus", {
                    "round": round_no + 1,
                    "player": p.name,
                    "declared": p.declared_tricks,
                    "tricks_won": p.tricks_won_this_round,
                    "vp_before": before,
                    "vp_after": p.vp,
                    "bonus_vp": DECLARATION_BONUS_VP,
                    "grace_bonus": grace_bonus,
                    "gold_bonus": gold_bonus,
                })

    # 恩寵システム: トリテ0勝で恩寵+金貨ボーナス（宣言0成功とは別）
    if GRACE_ENABLED:
        for p in players:
            if p.tricks_won_this_round == 0:
                p.grace_points += GRACE_ZERO_TRICKS_BONUS
                p.gold += ZERO_TRICKS_GOLD_BONUS
                print(f"0勝ボーナス: {p.name} がトリック0勝 -> +{GRACE_ZERO_TRICKS_BONUS} 恩寵, +{ZERO_TRICKS_GOLD_BONUS} 金")
                if logger:
                    logger.log("grace_zero_tricks_bonus", {
                        "round": round_no + 1,
                        "player": p.name,
                        "grace_gained": GRACE_ZERO_TRICKS_BONUS,
                        "gold_gained": ZERO_TRICKS_GOLD_BONUS,
                        "grace_points": p.grace_points,
                    })

    # WITCH_MIRROR: 他プレイヤーの宣言成功時+1金
    others_success_count = sum(1 for p in players if p.tricks_won_this_round == p.declared_tricks)
    for p in players:
        if "WITCH_MIRROR" in p.witches:
            # 自分の成功分を除外
            own_success = 1 if p.tricks_won_this_round == p.declared_tricks else 0
            mirror_gold = others_success_count - own_success
            if mirror_gold > 0:
                p.gold += mirror_gold
                print(f"《鏡の魔女》効果: {p.name} → 他者{mirror_gold}人成功 → +{mirror_gold}金")


def grace_hand_swap(
    player: Player,
    hand: List[Card],
    deck: List[Card],
    rng: random.Random,
    logger: Optional[JsonlLogger] = None,
    round_no: int = 0
) -> bool:
    """
    恩寵消費で手札全交換。
    シール前に使用可能。3恩寵 = 手札5枚を全て山に戻し、新しい5枚を引く。
    Returns True if swap was performed.
    """
    if not GRACE_ENABLED:
        return False
    if player.grace_points < GRACE_HAND_SWAP_COST:
        return False
    if len(deck) < len(hand):
        return False

    if player.is_bot:
        # ボット: 手札の平均ランクが低い場合に全交換を検討
        non_trump = [c for c in hand if not c.is_trump()]
        if not non_trump:
            return False
        avg_rank = sum(c.rank for c in non_trump) / len(non_trump)
        # 平均ランク2.5以下かつ恩寵に余裕がある場合のみ交換
        if avg_rank <= 2.5 and player.grace_points >= GRACE_HAND_SWAP_COST + 1:
            old_hand = hand[:]
            # 手札を全て山に戻す
            deck.extend(hand)
            hand.clear()
            rng.shuffle(deck)
            # 新しい手札を引く
            for _ in range(len(old_hand)):
                hand.append(deck.pop(0))
            player.grace_points -= GRACE_HAND_SWAP_COST
            if logger:
                logger.log("grace_hand_swap", {
                    "round": round_no + 1,
                    "player": player.name,
                    "swapped_out": [str(c) for c in old_hand],
                    "swapped_in": [str(c) for c in hand],
                    "grace_remaining": player.grace_points,
                })
            return True
        return False

    # 人間プレイヤー
    print(f"\n{player.name} 恩寵ポイント: {player.grace_points}")
    print(f"手札全交換可能 (コスト: {GRACE_HAND_SWAP_COST}恩寵、手札{len(hand)}枚を全て引き直し)")
    print("現在の手札:", " ".join(str(c) for c in hand))
    s = input("全交換しますか? (y/N): ").strip().lower()
    if s != "y":
        return False

    old_hand = hand[:]
    deck.extend(hand)
    hand.clear()
    rng.shuffle(deck)
    for _ in range(len(old_hand)):
        hand.append(deck.pop(0))
    player.grace_points -= GRACE_HAND_SWAP_COST
    print(f"全交換完了: {' '.join(str(c) for c in old_hand)} → {' '.join(str(c) for c in hand)}")
    print(f"残り恩寵: {player.grace_points}")
    if logger:
        logger.log("grace_hand_swap", {
            "round": round_no + 1,
            "player": player.name,
            "swapped_out": [str(c) for c in old_hand],
            "swapped_in": [str(c) for c in hand],
            "grace_remaining": player.grace_points,
        })
    return True


def seal_cards(player: Player, hand: List[Card], set_index: int) -> List[Card]:
    """
    Choose 2 cards to seal (unplayable). Remaining cards = TRICKS_PER_ROUND (=4).
    Sealed cards are removed from hand and returned.
    """
    assert len(hand) == CARDS_PER_SET, "seal_cards expects full set hand"
    need_seal = CARDS_PER_SET - TRICKS_PER_ROUND
    assert need_seal >= 0

    if need_seal == 0:
        return []

    if player.is_bot:
        if player.ai_bot:
            from ai_bot import ai_seal_cards
            result = ai_seal_cards(player, hand[:], player.declared_tricks)
            if result is not None:
                for c in result:
                    hand.remove(c)
                return result
        # bot heuristic: seal the two lowest ranks, but never seal trump cards
        non_trump = [c for c in hand if not c.is_trump()]
        # 切り札以外から最低ランクを選ぶ
        sealable = sorted(non_trump, key=lambda c: c.rank)
        if len(sealable) >= need_seal:
            sealed = sealable[:need_seal]
        else:
            # 切り札以外が足りない場合は切り札も含める
            sealed = sealable + sorted([c for c in hand if c.is_trump()], key=lambda c: c.rank)[:need_seal - len(sealable)]
        for c in sealed:
            hand.remove(c)
        return sealed

    print(f"\n{player.name} {need_seal}枚を公開封印してください（このラウンドは使用不可、全員に公開）")
    print("手札:", " ".join(str(c) for c in hand))
    sealed: List[Card] = []
    while len(sealed) < need_seal:
        s = input(f"公開封印するカードを選択 ({len(sealed)+1}/{need_seal}) 例: S13/H07/D01/C10/T01: ").strip().upper()
        suit_map = {"S": "Spade", "H": "Heart", "D": "Diamond", "C": "Club", "T": "Trump"}
        if len(s) < 2 or s[0] not in suit_map:
            print("無効な入力です。")
            continue
        try:
            rank = int(s[1:])
        except ValueError:
            print("無効な入力です。")
            continue
        chosen = Card(suit_map[s[0]], rank)
        if chosen not in hand:
            print("そのカードは持っていません。")
            continue
        hand.remove(chosen)
        sealed.append(chosen)
        print("残り:", " ".join(str(c) for c in hand))
    return sealed


# ======= Trick-taking (with Trump cards) =======

def trick_winner(lead_suit: str, plays: List[Tuple[Player, Card]]) -> Player:
    """
    Trump rules:
      - If any trump card is played, first trump player (closest to leader) wins.
      - Otherwise, highest card in lead suit wins.
    Tiebreaker (same rank):
      - Leader wins if tied.
      - Otherwise, player closest to leader (clockwise) wins.
    plays[0] is the leader, plays order is clockwise.
    """
    # 切り札が出ているか確認
    trumps = [(i, p, c) for i, (p, c) in enumerate(plays) if c.is_trump()]
    if trumps:
        # 切り札はランクなし、最初に出した人（親に近い人）が勝ち
        return trumps[0][1]

    # 切り札なし → リードスートの最高ランク
    leads = [(i, p, c) for i, (p, c) in enumerate(plays) if c.suit == lead_suit]
    max_rank = max(c.rank for _, _, c in leads)
    # 同ランクの場合、親に近い人（インデックスが小さい方）が勝ち
    for i, p, c in leads:
        if c.rank == max_rank:
            return p

    # Should never reach here
    return plays[0][0]


def legal_cards(hand: List[Card], lead_card: Optional[Card]) -> List[Card]:
    """
    - If leading: any card except trump (cannot lead with trump).
    - If not leading: must follow lead suit if possible.
      If cannot follow, any card including trump is legal.
    """
    if lead_card is None:
        # リード時: 切り札以外を出せる
        non_trump = [c for c in hand if not c.is_trump()]
        # 切り札しか持っていない場合は切り札を出せる
        return non_trump if non_trump else hand[:]

    lead_suit = lead_card.suit
    follow = [c for c in hand if c.suit == lead_suit]
    if follow:
        return follow  # フォロー必須
    else:
        return hand[:]  # フォローできない → 切り札含め何でもOK


def choose_card(player: Player, lead_card: Optional[Card], hand: List[Card], trick_plays: Optional[List[Tuple[Player, Card]]] = None, all_players: Optional[List[Player]] = None) -> Card:
    legal = legal_cards(hand, lead_card)

    if player.is_bot:
        if player.ai_bot:
            from ai_bot import ai_choose_card
            result = ai_choose_card(player, lead_card, hand, legal, trick_plays, all_players)
            if result is not None:
                return result
        return player.rng.choice(legal)

    while True:
        print(f"\n{player.name} 出せるカード: " + " ".join(str(c) for c in hand))
        if lead_card:
            print(f"リード: {lead_card}")
            if any(c.suit == lead_card.suit for c in hand):
                print(f"マストフォロー: {lead_card.suit}")
            else:
                trump_in_hand = [c for c in hand if c.is_trump()]
                if trump_in_hand:
                    print("フォロー不可 - 切り札使用可!")
        else:
            print("リードです（切り札でリード不可）")

        print("出せるカード:", " ".join(str(c) for c in legal))

        s = input("カードを選択 (例: S13 / H07 / D01 / C10 / T01): ").strip().upper()
        suit_map = {"S": "Spade", "H": "Heart", "D": "Diamond", "C": "Club", "T": "Trump"}
        if len(s) < 2 or s[0] not in suit_map:
            print("無効な入力です。")
            continue
        try:
            rank = int(s[1:])
        except ValueError:
            print("無効な入力です。")
            continue

        chosen = Card(suit_map[s[0]], rank)
        if chosen not in hand:
            print("そのカードは持っていません。")
            continue
        if chosen not in legal:
            print("出せないカードです（マストフォロー違反または切り札リード不可）")
            continue
        return chosen


def run_trick_taking(
    players: List[Player],
    round_no: int,
    rng: random.Random,
    logger: Optional[JsonlLogger],
    remaining_deck: Optional[List[Card]] = None
) -> int:
    """
    Flow:
      - Use round hand from player.sets[round_no]
      - Declaration after seeing round hand
      - (Grace test mode) Optional hand swap using grace points
      - Seal (CARDS_PER_SET - TRICKS_PER_ROUND) cards
      - Play TRICKS_PER_ROUND tricks with must-follow
      - Declaration bonus
    Returns leader_index used for tie-break ordering.
    """
    set_index = round_no % SETS_PER_GAME
    leader_index = round_no % len(players)

    for p in players:
        p.tricks_won_this_round = 0
        p.used_last_play_this_round = False
        p.ritual_consumed_this_round = 0

    full_hands: Dict[str, List[Card]] = {p.name: players[i].sets[set_index][:] for i, p in enumerate(players)}

    print("\n--- 宣言フェーズ (手札確認後) ---")
    for p in players:
        p.declared_tricks = declare_tricks(p, full_hands[p.name][:], set_index)

    if logger:
        logger.log("declarations", {
            "round": round_no + 1,
            "set_index": set_index + 1,
            "leader": players[leader_index].name,
            "declarations": {p.name: p.declared_tricks for p in players},
            "round_hands_full": {p.name: [str(c) for c in full_hands[p.name]] for p in players},
            "players": snapshot_players(players),
        })

    print("宣言一覧:", ", ".join(f"{p.name}:{p.declared_tricks}" for p in players))

    # 恩寵消費: シール前に手札交換
    if GRACE_ENABLED and remaining_deck:
        print("\n--- 恩寵消費フェーズ (手札交換) ---")
        for p in players:
            if p.grace_points >= GRACE_HAND_SWAP_COST:
                hand = full_hands[p.name]
                grace_hand_swap(p, hand, remaining_deck, rng, logger, round_no)

    need_seal = CARDS_PER_SET - TRICKS_PER_ROUND
    print(f"\n--- 公開封印フェーズ ({need_seal}枚を公開封印) ---")
    sealed_by_player: Dict[str, List[Card]] = {}
    playable_hands: Dict[str, List[Card]] = {}
    for p in players:
        hand = full_hands[p.name]
        sealed = seal_cards(p, hand, set_index)
        sealed_by_player[p.name] = sealed
        playable_hands[p.name] = hand[:]  # now length == TRICKS_PER_ROUND
        if logger:
            logger.log("seal_cards", {
                "round": round_no + 1,
                "player": p.name,
                "sealed": [str(c) for c in sealed],
                "playable_after_seal": [str(c) for c in playable_hands[p.name]],
            })

    if logger:
        logger.log("round_start", {
            "round": round_no + 1,
            "set_index": set_index + 1,
            "leader": players[leader_index].name,
            "no_trump": True,
            "players": snapshot_players(players),
        })

    # 他プレイヤーの公開封印カードを表示
    print("\n--- 公開封印されたカード (全プレイヤー) ---")
    for p in players:
        print(f"  {p.name}: {', '.join(str(c) for c in sealed_by_player[p.name])}")

    print(f"\n--- トリックテイキング ラウンド{round_no+1} ({CARDS_PER_SET}枚→公開封印{need_seal}枚→{TRICKS_PER_ROUND}トリック) ---")
    print(f"このラウンドのリーダー: {players[leader_index].name}")

    leader = leader_index
    for trick_idx in range(TRICKS_PER_ROUND):
        plays: List[Tuple[Player, Card]] = []
        lead_card: Optional[Card] = None

        # Build play order: leader first, then others
        # Check for 後出し権 usage after leader plays
        base_order = [(leader + offset) % len(players) for offset in range(len(players))]

        # Leader plays first
        leader_pl = players[base_order[0]]
        leader_hand = playable_hands[leader_pl.name]
        lead_card = choose_card(leader_pl, None, leader_hand)
        leader_hand.remove(lead_card)
        plays.append((leader_pl, lead_card))

        # Now check if any non-leader player wants to use 後出し権
        remaining_order = base_order[1:]  # indices of remaining players
        last_play_user_idx: Optional[int] = None  # index in remaining_order of the user

        if GRACE_ENABLED:
            for i, pidx in enumerate(remaining_order):
                p = players[pidx]
                # Check if eligible: enough grace, not used this round, not already last
                if (p.grace_points >= GRACE_LAST_PLAY_COST and
                    not p.used_last_play_this_round and
                    i < len(remaining_order) - 1):  # not already last

                    use_last_play = False
                    if p.is_bot:
                        # Bot decision: use if strategically beneficial
                        # Use if: winning declaration is at risk, or grace is abundant (>=3)
                        tricks_needed = p.declared_tricks - p.tricks_won_this_round
                        tricks_remaining = TRICKS_PER_ROUND - trick_idx
                        if p.grace_points >= 3 and tricks_needed > 0 and tricks_remaining >= tricks_needed:
                            use_last_play = p.rng.random() < 0.6  # 60% chance if conditions met（強化: 4以上30%→3以上60%）
                    else:
                        # Human player: ask
                        print(f"\n{p.name}: 後出し権を使用しますか？ (コスト: {GRACE_LAST_PLAY_COST}恩寵, 現在: {p.grace_points})")
                        print(f"  リードカード: {lead_card}")
                        choice = input("使用する？ (y/N): ").strip().lower()
                        use_last_play = choice == 'y'

                    if use_last_play:
                        p.grace_points -= GRACE_LAST_PLAY_COST
                        p.used_last_play_this_round = True
                        last_play_user_idx = i
                        print(f"  → {p.name} が後出し権を使用！ (-{GRACE_LAST_PLAY_COST}恩寵)")
                        if logger:
                            logger.log("grace_last_play", {
                                "round": round_no + 1,
                                "trick": trick_idx + 1,
                                "player": p.name,
                                "grace_remaining": p.grace_points,
                            })
                        break  # Only one player can use per trick

        # Reorder remaining players if someone used 後出し権
        if last_play_user_idx is not None:
            user_pidx = remaining_order.pop(last_play_user_idx)
            remaining_order.append(user_pidx)  # Move to end

        # Remaining players play in order
        for pidx in remaining_order:
            pl = players[pidx]
            hand = playable_hands[pl.name]
            chosen = choose_card(pl, lead_card, hand)
            hand.remove(chosen)
            plays.append((pl, chosen))

        assert lead_card is not None
        winner = trick_winner(lead_card.suit, plays)
        winner.tricks_won_this_round += 1

        print("プレイ:", " | ".join(f"{pl.name}:{c}" for pl, c in plays))
        print(f"トリック勝者: {winner.name} (リードスート {lead_card.suit})")

        if logger:
            logger.log("trick", {
                "round": round_no + 1,
                "trick": trick_idx + 1,
                "leader": players[leader].name,
                "lead_card": str(lead_card),
                "lead_suit": lead_card.suit,
                "no_trump": True,
                "plays": [{"player": pl.name, "card": str(c), "suit": c.suit, "rank": c.rank} for pl, c in plays],
                "winner": winner.name,
                "tricks_won_so_far": {pp.name: pp.tricks_won_this_round for pp in players},
            })

        leader = next(i for i, pp in enumerate(players) if pp.name == winner.name)

    if logger:
        logger.log("trick_summary", {
            "round": round_no + 1,
            "tricks_won": {p.name: p.tricks_won_this_round for p in players},
            "sealed": {name: [str(c) for c in sealed_by_player[name]] for name in sealed_by_player},
        })

    print("\n--- トリック結果 ---")
    print("-" * 40)
    for p in players:
        status = "✓" if p.tricks_won_this_round == p.declared_tricks else ""
        print(f"  {p.name}: {p.tricks_won_this_round} トリック (宣言 {p.declared_tricks}) {status}")
    print("-" * 40)

    print("\n--- 宣言ボーナス ---")
    apply_declaration_bonus(players, logger, round_no)

    return leader_index


def _offer_grace_priority(
    players: List[Player],
    leader_index: int,
    logger: Optional[JsonlLogger] = None,
    round_no: int = 0,
) -> Set[str]:
    """
    恩寵消費による先行権を提示。
    同トリック数のプレイヤーがいる場合のみ意味がある。
    Returns set of player names who used grace priority.
    """
    priority_users: Set[str] = set()

    # 同トリック数のプレイヤーがいるかチェック
    trick_counts = [p.tricks_won_this_round for p in players]
    has_ties = len(trick_counts) != len(set(trick_counts))

    if not has_ties:
        return priority_users

    for p in players:
        if p.grace_points < GRACE_PRIORITY_COST:
            continue

        # 同トリック数の相手がいるか
        tied = [q for q in players if q.name != p.name and q.tricks_won_this_round == p.tricks_won_this_round]
        if not tied:
            continue

        if p.is_bot:
            # Bot: 恩寵に余裕があれば先行権を使う
            if p.grace_points >= GRACE_PRIORITY_COST + 2:
                p.grace_points -= GRACE_PRIORITY_COST
                priority_users.add(p.name)
                if logger:
                    logger.log("grace_priority", {
                        "round": round_no + 1,
                        "player": p.name,
                        "cost": GRACE_PRIORITY_COST,
                        "grace_remaining": p.grace_points,
                    })
        else:
            print(f"\n{p.name}: 同トリック数のプレイヤーがいます。")
            print(f"  恩寵 {GRACE_PRIORITY_COST} を消費して先行権を得ますか? (恩寵: {p.grace_points})")
            s = input("  先行権を使う? (y/N): ").strip().lower()
            if s == "y":
                p.grace_points -= GRACE_PRIORITY_COST
                priority_users.add(p.name)
                print(f"  → {p.name} が先行権を獲得 (恩寵 -{GRACE_PRIORITY_COST})")
                if logger:
                    logger.log("grace_priority", {
                        "round": round_no + 1,
                        "player": p.name,
                        "cost": GRACE_PRIORITY_COST,
                        "grace_remaining": p.grace_points,
                    })

    return priority_users


def rank_players_for_upgrade(
    players: List[Player],
    leader_index: int,
    grace_priority: Optional[Set[str]] = None,
) -> List[Player]:
    """
    Rank by:
      1) tricks won (most first)
      2) grace priority used (spenders first among same trick count)
      3) grace points (higher is better)
      4) seat order from leader (fallback)
    """
    gp = grace_priority or set()
    order = {players[(leader_index + i) % 4].name: i for i in range(4)}

    def key(p: Player):
        return (p.tricks_won_this_round, 1 if p.name in gp else 0, p.grace_points, -order[p.name])

    return sorted(players, key=key, reverse=True)


# ======= Worker Placement =======

def get_available_actions(player: Player, ps: Optional[PlacementState] = None) -> List[str]:
    """プレイヤーが配置可能なアクションのリストを返す（ナショエコ式ブロッキング対応）"""
    available: List[str] = []

    if ps is None:
        # 後方互換: PlacementStateなしの場合は全アクション返す
        return ACTIONS[:]

    # 共通スポット（ブロッキング: 全体で1ワーカーのみ）
    if not ps.shared_trade_taken:
        available.append("TRADE")
    if not ps.shared_hunt_taken:
        available.append("HUNT")
    if GRACE_ENABLED and not ps.shared_pray_taken:
        available.append("PRAY")

    # Recruit（オープン: 制限なし）
    total_workers = player.basic_workers_total + player.basic_workers_new_hires
    if total_workers < MAX_WORKERS and player.gold >= RECRUIT_COST:
        available.append("RECRUIT")

    # 共有スポット（全プレイヤーのスポットが利用可能、ブロッキングあり）
    spot_owners = ps.all_players if ps.all_players else [player]
    for owner in spot_owners:
        used = ps.personal_spots_used.get(owner.name, set())
        seen_types: Set[str] = set()
        for idx, spot in enumerate(owner.personal_spots):
            if idx in used:
                continue
            # Lv2化済みの場合は同種1アクションのみ
            if spot in owner.leveled_spots:
                if spot in seen_types:
                    continue
                seen_types.add(spot)
            # コストチェック
            if spot == "WITCH_NEGOTIATE" and player.grace_points < WITCH_NEGOTIATE_GRACE_COST:
                continue
            available.append(f"SPOT:{owner.name}:{idx}:{spot}")

    return available


def _spot_display_name(action: str, player: Optional[Player] = None,
                        all_players: Optional[List['Player']] = None) -> str:
    """アクション名を表示用に変換（共有スポット対応）"""
    if action.startswith("SPOT:"):
        parts = action.split(":", 3)
        owner_name = parts[1]
        spot_name = parts[3]
        # 所有者を探してレベル判定
        owner = None
        if all_players:
            owner = next((p for p in all_players if p.name == owner_name), None)
        if owner and spot_name in owner.leveled_spots:
            level = 2
        else:
            level = 1
        lv_tag = f" Lv{level}" if level >= 2 else ""
        bonus = level - 1
        # 所有者表示（自分のスポットかどうか）
        owner_tag = ""
        if player and owner_name != player.name:
            owner_tag = f"[{owner_name}]"
        elif player and owner_name == player.name:
            owner_tag = "[自分]"
        names = {
            "UP_TRADE": f"交易{lv_tag}({PERSONAL_TRADE_GOLD + bonus}金){owner_tag}",
            "UP_HUNT": f"討伐{lv_tag}({PERSONAL_HUNT_VP + bonus}VP){owner_tag}",
            "UP_PRAY": f"祈り{lv_tag}({PERSONAL_PRAY_GRACE + bonus}恩寵){owner_tag}",
            "UP_RITUAL": f"儀式{lv_tag}({PERSONAL_RITUAL_GRACE + bonus}恩寵 or {PERSONAL_RITUAL_GOLD + bonus}金){owner_tag}",
            "WITCH_NEGOTIATE": f"交渉の魔女({WITCH_NEGOTIATE_GRACE_COST}恩寵→{WITCH_NEGOTIATE_GOLD}金){owner_tag}",
        }
        return names.get(spot_name, spot_name)
    names = {
        "TRADE": f"共通交易({SHARED_TRADE_GOLD}金)",
        "HUNT": f"共通討伐({SHARED_HUNT_VP}VP)",
        "PRAY": f"共通祈り({SHARED_PRAY_GRACE}恩寵)",
        "RECRUIT": f"雇用({RECRUIT_COST}金→+1人)",
    }
    return names.get(action, action)


def determine_placement_order(
    players: List[Player],
    leader_index: int,
    grace_priority: Optional[Set[str]] = None,
) -> List[Player]:
    """ワーカー配置の順序を決定（トリック勝数多い順→恩寵先行権→恩寵多い順→親から時計回り）"""
    gp = grace_priority or set()
    seat = {players[(leader_index + i) % len(players)].name: i for i in range(len(players))}
    return sorted(players, key=lambda p: (-p.tricks_won_this_round, -(1 if p.name in gp else 0), -p.grace_points, seat[p.name]))


def resolve_single_action(player: Player, action: str, ps: PlacementState) -> Dict[str, Any]:
    """1ワーカーのアクションを解決し、PlacementStateを更新する"""
    result: Dict[str, Any] = {"action": action, "display": _spot_display_name(action, player, ps.all_players), "effects": []}

    if action == "TRADE":
        player.gold += SHARED_TRADE_GOLD
        ps.shared_trade_taken = True
        result["effects"].append(f"+{SHARED_TRADE_GOLD}金")
    elif action == "HUNT":
        player.vp += SHARED_HUNT_VP
        ps.shared_hunt_taken = True
        result["effects"].append(f"+{SHARED_HUNT_VP}VP")
    elif action == "PRAY":
        player.grace_points += SHARED_PRAY_GRACE
        ps.shared_pray_taken = True
        result["effects"].append(f"+{SHARED_PRAY_GRACE}恩寵")
    elif action == "RECRUIT":
        player.gold -= RECRUIT_COST
        player.basic_workers_new_hires += 1
        result["effects"].append(f"-{RECRUIT_COST}金, +1人(次R)")
    elif action.startswith("SPOT:"):
        parts = action.split(":", 3)
        owner_name = parts[1]
        idx = int(parts[2])
        spot_name = parts[3]

        # スポット所有者を取得
        owner = next((p for p in ps.all_players if p.name == owner_name), player)
        is_owner = (player.name == owner_name)

        # 使用済みマーク（所有者のスポットとして記録）
        used = ps.personal_spots_used.setdefault(owner_name, set())
        used.add(idx)
        # Lv2化済みの場合は同種の全indexを使用済みにする
        if spot_name in owner.leveled_spots:
            for i2, s2 in enumerate(owner.personal_spots):
                if s2 == spot_name:
                    used.add(i2)

        # 他人のスポット使用時: 所有者に+1金（銀行から）
        if not is_owner:
            owner.gold += 1
            result["effects"].append(f"({owner_name}に+1金収入)")

        # レベル判定: 所有者のleveled_spotsで判定
        level = 2 if spot_name in owner.leveled_spots else 1
        # スポットの効果を解決（Lv2は+1ボーナス）
        if spot_name == "UP_TRADE":
            gold = PERSONAL_TRADE_GOLD + (level - 1)
            # 黒路の魔女パッシブ: 使用者本人の魔女で判定
            if "WITCH_BLACKROAD" in player.witches:
                gold += 1
            player.gold += gold
            witch_note = "(黒路+1)" if "WITCH_BLACKROAD" in player.witches else ""
            result["effects"].append(f"+{gold}金{witch_note}")
        elif spot_name == "UP_HUNT":
            vp = PERSONAL_HUNT_VP + (level - 1)
            if "WITCH_BLOODHUNT" in player.witches:
                vp += 1
            player.vp += vp
            witch_note = "(血誓+1)" if "WITCH_BLOODHUNT" in player.witches else ""
            result["effects"].append(f"+{vp}VP{witch_note}")
        elif spot_name == "UP_PRAY":
            grace = PERSONAL_PRAY_GRACE + (level - 1)
            player.grace_points += grace
            result["effects"].append(f"+{grace}恩寵")
        elif spot_name == "UP_RITUAL":
            grace_amount = PERSONAL_RITUAL_GRACE + (level - 1)
            gold_amount = PERSONAL_RITUAL_GOLD + (level - 1)
            choice = _choose_ritual_reward(player, grace_amount, gold_amount)
            if choice == "grace":
                player.grace_points += grace_amount
                result["effects"].append(f"+{grace_amount}恩寵")
            else:
                player.gold += gold_amount
                result["effects"].append(f"+{gold_amount}金")
            # 儀式の祭壇: 使用者のワーカー永久消費
            player.basic_workers_total -= 1
            player.ritual_consumed_this_round += 1
            result["effects"].append("ワーカー-1(永久消費)")
        elif spot_name == "WITCH_NEGOTIATE":
            player.grace_points -= WITCH_NEGOTIATE_GRACE_COST
            player.gold += WITCH_NEGOTIATE_GOLD
            result["effects"].append(f"-{WITCH_NEGOTIATE_GRACE_COST}恩寵, +{WITCH_NEGOTIATE_GOLD}金(交渉の魔女)")
    else:
        raise ValueError(f"Unknown action: {action}")

    return result


def bot_choose_single_action(player: Player, available: List[str],
                              ps: PlacementState, round_no: int) -> str:
    """Bot AIが1ワーカーの配置先を選択する"""
    if not available:
        return "PASS"

    if player.ai_bot:
        from ai_bot import ai_choose_worker_action
        result = ai_choose_worker_action(player, available, round_no, ps.all_players if ps.all_players else None)
        if result is not None:
            return result

    strat = STRATEGIES.get(player.strategy, STRATEGIES['BALANCED'])
    expected_wage = calc_expected_wage(player, round_no)
    gold_deficit = max(0, expected_wage - player.gold)
    grace_awareness = strat.get('grace_awareness', 0.5)

    # スコアリング: 各アクションに優先度をつける
    scores: List[Tuple[float, str]] = []
    for action in available:
        score = 50.0

        if action == "TRADE" or (action.startswith("SPOT:") and "UP_TRADE" in action):
            score += 20  # Tradeは常に有用
            if gold_deficit > 0:
                score += 35  # 給料支払いに金が必要
            if strat.get('prefer_gold', False):
                score += 15
            # 共通スポットはブロック前に確保（個人よりやや優先）
            if action == "TRADE":
                score += 5
        elif action == "HUNT" or (action.startswith("SPOT:") and "UP_HUNT" in action):
            score += 15  # Huntも常に有用
            score += strat['hunt_ratio'] * 40
            if action == "HUNT":
                score += 5
        elif action == "PRAY" or (action.startswith("SPOT:") and "UP_PRAY" in action):
            score += grace_awareness * 25
            if action == "PRAY":
                score += 5
        elif action.startswith("SPOT:") and "WITCH_NEGOTIATE" in action:
            if gold_deficit > 0:
                score += 35  # 恩寵→金変換は金不足時に有用
            else:
                score += 10
        elif action.startswith("SPOT:") and "UP_RITUAL" in action:
            # 儀式はワーカー永久消費: ワーカー2以下なら避ける
            if player.basic_workers_total <= 2:
                score -= 30
            else:
                score += 25  # 恩寵 or 金の選択は常に有用
                if gold_deficit > 0:
                    score += 15  # 金選択が可能
        elif action == "RECRUIT":
            # 金に余裕があり、共有スポットが少ない序盤のみ雇用検討
            total_shared = sum(len(p.personal_spots) for p in ps.all_players) if ps.all_players else len(player.personal_spots)
            total_spots = total_shared + 3  # 共有スポット + 共通3つ
            if (round_no < 3 and player.basic_workers_total < strat.get('max_workers', 4)
                    and player.basic_workers_total < total_spots
                    and player.gold >= RECRUIT_COST + calc_expected_wage(player, round_no)):
                score += 15
            else:
                score += 2

        # ランダム性を加える
        score += player.rng.random() * 10

        scores.append((score, action))

    scores.sort(key=lambda x: -x[0])
    return scores[0][1]


def choose_single_action(player: Player, ps: PlacementState, round_no: int) -> str:
    """1ワーカーの配置先を選択（Bot/人間共通エントリポイント）"""
    available = get_available_actions(player, ps)

    if not available:
        return "PASS"

    if player.is_bot:
        return bot_choose_single_action(player, available, ps, round_no)

    # 人間プレイヤー
    remaining = ps.workers_remaining.get(player.name, 0)
    print(f"\n{player.name} ワーカーを1人配置 (残り: {remaining})")
    print("利用可能なアクション:")
    for i, a in enumerate(available):
        print(f"  [{i}] {_spot_display_name(a, player, ps.all_players)}")
    while True:
        s = input("番号を選択: ").strip()
        try:
            idx = int(s)
            if 0 <= idx < len(available):
                return available[idx]
        except ValueError:
            # アクション名直接入力も受け付ける
            s_upper = s.upper()
            for a in available:
                if a == s_upper or a.startswith(f"SPOT:") and s_upper in a.upper():
                    return a
        print(f"無効な入力です: {s}")


def run_worker_placement_round(
    players: List[Player],
    round_no: int,
    leader_index: int,
    is_interactive: bool = False,
    logger: Optional[JsonlLogger] = None,
    grace_priority: Optional[Set[str]] = None,
) -> PlacementState:
    """ナショナルエコノミー式ワーカー配置のメインループ（CLI/Simulation共用）"""
    ps = PlacementState()
    ps.all_players = players
    order = determine_placement_order(players, leader_index, grace_priority)
    ps.placement_order = order

    for p in players:
        ps.workers_remaining[p.name] = p.basic_workers_total
        ps.personal_spots_used[p.name] = set()

    if is_interactive:
        print("\n--- ワーカー配置 (ナショナルエコノミー方式) ---")
        print(f"配置順: {' → '.join(p.name for p in order)}")

    # ラウンドロビンで1ワーカーずつ配置
    while any(ps.workers_remaining[p.name] > 0 for p in order):
        for p in order:
            if ps.workers_remaining[p.name] <= 0:
                continue
            action = choose_single_action(p, ps, round_no)
            if action == "PASS":
                ps.workers_remaining[p.name] = 0
                if is_interactive:
                    print(f"  {p.name}: PASS（配置先なし）")
                continue
            result = resolve_single_action(p, action, ps)
            ps.workers_remaining[p.name] -= 1
            if is_interactive:
                effects_str = ", ".join(result["effects"])
                print(f"  {p.name}: {result['display']} → {effects_str}")
            if logger:
                logger.log("worker_placement", {
                    "player": p.name,
                    "action": action,
                    "display": result["display"],
                    "effects": result["effects"],
                    "round": round_no + 1,
                })

    return ps


# === 後方互換ラッパー ===

def choose_actions_for_player(player: Player, round_no: int = 0) -> List[str]:
    """後方互換: 旧APIを新方式で実装（GameEngine用）"""
    ps = PlacementState()
    ps.workers_remaining[player.name] = player.basic_workers_total
    ps.personal_spots_used[player.name] = set()
    actions = []
    for _ in range(player.basic_workers_total):
        action = choose_single_action(player, ps, round_no)
        if action == "PASS":
            break
        resolve_single_action(player, action, ps)
        actions.append(action)
    return actions


def resolve_actions(player: Player, actions: List[str]) -> Dict[str, Any]:
    """後方互換: 旧resolve_actions API（結果は既にchoose_actions_for_playerで適用済み）"""
    return {"before": {}, "after": {}, "witch_bonuses": [], "grace_bonuses": []}


def pay_wages_and_debt(
    player: Player,
    round_no: int,
    debt_multiplier: Optional[int] = None,
    debt_cap: Optional[int] = None,
    initial_workers_config: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Rule:
    - 初期ワーカー（INITIAL_WORKERS）のみWAGE_CURVEに従って給料支払い
    - アップグレードワーカーは取得時2金支払い済み、以後給料なし

    Args:
        debt_multiplier: Override for debt penalty multiplier (None = use global)
        debt_cap: Override for debt penalty cap (None = use global)
        initial_workers_config: Override for initial workers count (None = use global)
    """
    before_gold, before_vp = player.gold, player.vp

    workers_active = player.basic_workers_total
    workers_hired_this_round = player.basic_workers_new_hires

    # 給料計算: 初期ワーカーのみ（儀式消費ワーカーも給料対象）
    initial_wage_rate = WAGE_CURVE[round_no]
    initial_workers_base = initial_workers_config if initial_workers_config is not None else INITIAL_WORKERS
    # 儀式で消費されたワーカーも給料計算に含める（消費前のワーカー数で計算）
    workers_for_wage = workers_active + player.ritual_consumed_this_round
    initial_workers_count = min(initial_workers_base, workers_for_wage)
    initial_workers_count = max(0, initial_workers_count)

    wage_gross = initial_workers_count * initial_wage_rate

    discount = 0
    witch_wage_bonus = ""

    # WITCH_HERD: 毎ラウンド給料-1（パッシブ効果）
    if "WITCH_HERD" in player.witches:
        discount += 1
        witch_wage_bonus = "群導の魔女: 給料-1"

    wage_net = max(0, wage_gross - discount)

    # 恩寵による負債軽減: 給料支払い前に恩寵を消費して不足分を補う
    grace_debt_reduction = 0
    if GRACE_ENABLED and player.gold < wage_net:
        potential_short = wage_net - player.gold
        while (player.grace_points >= GRACE_DEBT_REDUCTION_COST and
               potential_short > 0):
            if player.is_bot:
                # Bot: use if debt penalty would be worse (multiplier >= 2)
                actual_multiplier = debt_multiplier if debt_multiplier is not None else DEBT_PENALTY_MULTIPLIER
                if actual_multiplier >= 2:
                    player.grace_points -= GRACE_DEBT_REDUCTION_COST
                    player.gold += 1
                    potential_short -= 1
                    grace_debt_reduction += 1
                else:
                    break
            else:
                # Human player would be asked, but for simplicity in simulation, skip
                break

    paid = min(player.gold, wage_net)
    short = max(0, wage_net - player.gold)

    if player.gold >= wage_net:
        player.gold -= wage_net
    else:
        player.gold = 0
        # 負債を累積（ゲーム終了時にまとめてペナルティ適用）
        player.accumulated_debt += short

    return {
        "initial_wage_rate": initial_wage_rate,
        "initial_workers": initial_workers_count,
        "workers_active": workers_active,
        "workers_hired_this_round": workers_hired_this_round,
        "wage_gross": wage_gross,
        "wage_discount": discount,
        "wage_net": wage_net,
        "paid_gold": paid,
        "short_gold": short,
        "accumulated_debt": player.accumulated_debt,
        "grace_debt_reduction": grace_debt_reduction,  # 恩寵による負債軽減金額
        "gold_before": before_gold,
        "gold_after": player.gold,
        "vp_before": before_vp,
        "vp_after": player.vp,
        "witch_wage_bonus": witch_wage_bonus,
    }


# ======= Main =======

def main():
    logger = JsonlLogger(LOG_PATH)

    rng = random.Random(42)
    deal_seed = 42

    # CPUにランダムな性格を割り当て
    bot_rng = random.Random()  # 毎回異なるシードで性格を決定
    players = [
        Player("P1", is_bot=False, rng=random.Random(1)),
        Player("P2", is_bot=True,  rng=random.Random(2), strategy=assign_random_strategy(bot_rng)),
        Player("P3", is_bot=True,  rng=random.Random(3), strategy=assign_random_strategy(bot_rng)),
        Player("P4", is_bot=True,  rng=random.Random(4), strategy=assign_random_strategy(bot_rng)),
    ]

    # CPU性格を表示
    for p in players:
        if p.is_bot and p.strategy:
            strat = STRATEGIES[p.strategy]
            print(f"  {p.name}: {strat['name']} ({strat['name_en']})")

    logger.log("game_start", {
        "config": {
            "ROUNDS": ROUNDS,
            "TRICKS_PER_ROUND": TRICKS_PER_ROUND,
            "CARDS_PER_SET": CARDS_PER_SET,
            "SETS_PER_GAME": SETS_PER_GAME,
            "NO_TRUMP": True,
            "REVEAL_UPGRADES": REVEAL_UPGRADES,
            "START_GOLD": START_GOLD,
            "WAGE_CURVE": WAGE_CURVE,
            "DEBT_PENALTY_MULTIPLIER": DEBT_PENALTY_MULTIPLIER,
            "DEBT_PENALTY_CAP": DEBT_PENALTY_CAP,
            "RESCUE_GOLD_FOR_4TH": RESCUE_GOLD_FOR_4TH,
            "TAKE_GOLD_INSTEAD": TAKE_GOLD_INSTEAD,
            "DECLARATION_BONUS_VP": DECLARATION_BONUS_VP,
            "deal_seed": deal_seed,
            "rng_seed": 42,
        },
        "players": snapshot_players(players),
    })

    # プレイヤーのsetsを空リストで初期化
    for p in players:
        p.sets = []

    # アップグレードデッキを初期化
    upgrade_deck = UpgradeDeck(rng)

    # 魔女デッキを作成（ラウンド3用）
    witch_pool: List[str] = []
    for w in ALL_WITCHES:
        count = WITCH_POOL_COUNTS.get(w, 1)
        witch_pool.extend([w] * count)
    rng.shuffle(witch_pool)

    for round_no in range(ROUNDS):
        print_state(players, round_no)

        # ラウンド毎にデッキをリシャッフルして配札
        round_hands, remaining_deck = deal_round_cards(players, round_no, rng, logger)
        print(f"\n--- ラウンド{round_no + 1} カード配布 (リシャッフル) ---")

        # ラウンド3（WITCH_ROUND）は魔女カード、それ以外は通常アップグレード
        is_witch_round = (round_no == WITCH_ROUND)
        if is_witch_round:
            # 魔女ラウンド: 魔女カードを公開
            revealed = witch_pool[:REVEAL_UPGRADES]
            witch_pool = witch_pool[REVEAL_UPGRADES:]
            print("\n★ 魔女ラウンド！ 公開された魔女カード:")
        else:
            revealed = upgrade_deck.reveal(REVEAL_UPGRADES)
            print("\n公開されたアップグレード:")
        for u in revealed:
            print(" -", upgrade_name(u), f"[{u}]")
        logger.log("reveal_upgrades", {
            "round": round_no + 1,
            "is_witch_round": is_witch_round,
            "revealed": revealed[:],
            "deck_remaining": len(upgrade_deck.deck) if not is_witch_round else 0,
            "discard_pile": len(upgrade_deck.discard) if not is_witch_round else 0,
        })

        leader_index = run_trick_taking(players, round_no, rng, logger, remaining_deck)

        # 恩寵先行権: 同トリック数の場合に先行できる
        grace_priority: Set[str] = set()
        if GRACE_ENABLED:
            grace_priority = _offer_grace_priority(players, leader_index, logger, round_no)

        ranked = rank_players_for_upgrade(players, leader_index, grace_priority)
        logger.log("upgrade_pick_order", {
            "round": round_no + 1,
            "order": [p.name for p in ranked],
            "tricks_won": {p.name: p.tricks_won_this_round for p in players},
            "witches": {p.name: p.permanent_witch_count() for p in players},
            "declared": {p.name: p.declared_tricks for p in players},
            "grace_priority": list(grace_priority),
        })

        print("\nアップグレード選択順:")
        for i, p in enumerate(ranked, start=1):
            print(f" {i}. {p.name} トリック={p.tricks_won_this_round} 恩寵={p.grace_points} 宣言={p.declared_tricks}")

        for p in ranked:
            before = snapshot_players([p])[0]
            choice = choose_upgrade_or_gold(p, revealed, round_no)

            if choice == "GOLD":
                p.gold += TAKE_GOLD_INSTEAD
                print(f"{p.name} が {TAKE_GOLD_INSTEAD} 金貨を獲得。")
                logger.log("upgrade_pick", {
                    "round": round_no + 1,
                    "player": p.name,
                    "choice": "GOLD",
                    "gold_gain": TAKE_GOLD_INSTEAD,
                    "revealed_remaining": revealed[:],
                    "before": before,
                    "after": snapshot_players([p])[0],
                })
            else:
                revealed.remove(choice)
                # 2枚目の場合はLv2か別枠かを選択
                level_up = None
                if choice in ("UP_TRADE", "UP_HUNT", "UP_PRAY", "UP_RITUAL") and p.personal_spots.count(choice) >= 1:
                    level_up = choose_level_up_or_separate(p, choice)
                apply_upgrade(p, choice, level_up)
                lv_info = ""
                if level_up is True:
                    lv_info = " → Lv2に強化"
                elif level_up is False:
                    lv_info = " → 別枠Lv1配置"
                print(f"{p.name} がアップグレード獲得: {upgrade_name(choice)}{lv_info}")
                logger.log("upgrade_pick", {
                    "round": round_no + 1,
                    "player": p.name,
                    "choice": choice,
                    "choice_name": upgrade_name(choice),
                    "level_up": level_up,
                    "revealed_remaining": revealed[:],
                    "before": before,
                    "after": snapshot_players([p])[0],
                })

        # 選ばれなかったカードを捨て札に移動（魔女カードは捨てない）
        if revealed and not is_witch_round:
            upgrade_deck.discard_remaining(revealed)
            logger.log("upgrade_discard", {
                "round": round_no + 1,
                "discarded": revealed[:],
                "deck_remaining": len(upgrade_deck.deck),
                "discard_pile": len(upgrade_deck.discard),
            })

        fourth = ranked[-1]
        before_gold = fourth.gold
        before_grace = fourth.grace_points
        bonus_choice = choose_4th_place_bonus(fourth, logger, round_no)
        if bonus_choice == "GOLD":
            print(f"\n救済: {fourth.name} が +{RESCUE_GOLD_FOR_4TH} 金貨を獲得 (4位ボーナス)")
        else:
            print(f"\n救済: {fourth.name} が +{GRACE_4TH_PLACE_BONUS} 恩寵を獲得 (4位ボーナス)")
        logger.log("rescue", {
            "round": round_no + 1,
            "player": fourth.name,
            "choice": bonus_choice,
            "gold_before": before_gold,
            "gold_after": fourth.gold,
            "grace_before": before_grace,
            "grace_after": fourth.grace_points,
        })

        logger.log("wp_start", {"round": round_no + 1, "players": snapshot_players(players)})
        run_worker_placement_round(players, round_no, leader_index, is_interactive=True, logger=logger, grace_priority=grace_priority)
        for p in players:
            print(f"{p.name} => Gold={p.gold}, VP={p.vp}, NewHires={p.basic_workers_new_hires}")
            logger.log("wp_result", {
                "round": round_no + 1,
                "player": p.name,
                "state": snapshot_players([p])[0],
            })

        initial_rate = WAGE_CURVE[round_no]
        print(f"\n--- 給料支払い (初期ワーカー={initial_rate}金/人) ---")
        logger.log("wage_phase_start", {"round": round_no + 1, "initial_wage_rate": initial_rate, "players": snapshot_players(players)})

        for p in players:
            res = pay_wages_and_debt(p, round_no)
            debt_info = f" 累積負債={p.accumulated_debt}" if p.accumulated_debt > 0 else ""
            print(f"{p.name}: Gold {res['gold_before']}->{res['gold_after']}{debt_info}")
            logger.log("wage_result", {
                "round": round_no + 1,
                "player": p.name,
                "result": res,
                "state": snapshot_players([p])[0],
            })

        # Activate hires next round
        for p in players:
            if p.basic_workers_new_hires > 0:
                before_workers = p.basic_workers_total
                activated = p.basic_workers_new_hires
                p.basic_workers_total += activated
                p.basic_workers_new_hires = 0
                logger.log("hire_activation", {
                    "round": round_no + 1,
                    "player": p.name,
                    "workers_before": before_workers,
                    "workers_after": p.basic_workers_total,
                    "activated": activated,
                })

        # WITCH_BLESSING: 毎ラウンド終了時+1恩寵
        if GRACE_ENABLED:
            for p in players:
                if "WITCH_BLESSING" in p.witches:
                    p.grace_points += 1
                    logger.log("witch_blessing_grace", {
                        "round": round_no + 1,
                        "player": p.name,
                        "grace_gained": 1,
                    })

        logger.log("round_end", {"round": round_no + 1, "players": snapshot_players(players)})



    # ゲーム終了時: 金貨→恩寵変換（恩寵→VP変換の前に適用）
    if GRACE_ENABLED and GOLD_TO_GRACE_RATE > 0:
        print("\n--- 金貨→恩寵変換 ---")
        for p in players:
            grace_gained = p.gold // GOLD_TO_GRACE_RATE
            if grace_gained > 0:
                gold_spent = grace_gained * GOLD_TO_GRACE_RATE
                p.gold -= gold_spent
                p.grace_points += grace_gained
                print(f"{p.name}: {gold_spent}G → +{grace_gained}恩寵 (残{p.gold}G)")
            else:
                print(f"{p.name}: {p.gold}G ({GOLD_TO_GRACE_RATE}G未満)")
            logger.log("gold_to_grace", {
                "player": p.name,
                "gold_spent": grace_gained * GOLD_TO_GRACE_RATE if grace_gained > 0 else 0,
                "grace_gained": grace_gained,
            })

    # 恩寵ポイント閾値ボーナス（ゲーム終了時）
    if GRACE_ENABLED:
        print("\n--- 恩寵→VP変換 ---")
        for p in players:
            grace_bonus = (p.grace_points // GRACE_VP_PER_N) * GRACE_VP_AMOUNT
            if grace_bonus > 0:
                p.vp += grace_bonus
                print(f"{p.name}: 恩寵{p.grace_points}点 ({p.grace_points // GRACE_VP_PER_N}×{GRACE_VP_AMOUNT}) → +{grace_bonus}VP")
            else:
                print(f"{p.name}: 恩寵{p.grace_points}点 ({GRACE_VP_PER_N}未満)")
            logger.log("grace_bonus", {
                "player": p.name,
                "grace_points": p.grace_points,
                "bonus_vp": grace_bonus,
            })

    # ゲーム終了時: 金貨をVPに変換（恩寵変換後の残り金貨）
    print("\n--- 金貨→VP変換 ---")
    for p in players:
        bonus_vp = p.gold // GOLD_TO_VP_RATE
        if bonus_vp > 0:
            print(f"{p.name}: {p.gold}G → +{bonus_vp}VP")
            p.vp += bonus_vp

    # ゲーム終了時: 負債ペナルティ適用
    print("\n--- 負債ペナルティ ---")
    for p in players:
        if p.accumulated_debt > 0:
            penalty = calculate_debt_penalty(p.accumulated_debt)
            p.vp -= penalty
            print(f"{p.name}: 累積負債{p.accumulated_debt}金 → -{penalty}VP")
            logger.log("debt_penalty", {
                "player": p.name,
                "accumulated_debt": p.accumulated_debt,
                "penalty_vp": penalty,
            })
        else:
            print(f"{p.name}: 負債なし")

    players_sorted = sorted(players, key=lambda p: (p.vp, p.gold), reverse=True)
    logger.log("game_end", {
        "final_ranking": [{"rank": i+1, "name": p.name, "vp": p.vp, "gold": p.gold} for i, p in enumerate(players_sorted)],
        "players": snapshot_players(players),
    })
    logger.close()

    print("\n=== ゲーム終了 ===")
    for i, p in enumerate(players_sorted, start=1):
        grace_info = f" 恩寵={p.grace_points}" if GRACE_ENABLED else ""
        debt_info = f" 負債={p.accumulated_debt}" if p.accumulated_debt > 0 else ""
        print(f"{i}. {p.name} VP={p.vp} 金貨={p.gold} ワーカー={p.basic_workers_total} "
              f"スポット={len(p.personal_spots)} "
              f"魔女={p.permanent_witch_count()}{grace_info}{debt_info}")
    print(f"\n勝者: {players_sorted[0].name}")
    print(f"\nLog written to: {LOG_PATH}")


# ======= GameEngine for GUI =======

@dataclass
class InputRequest:
    """Represents a request for human input."""
    type: str  # "declaration", "grace_hand_swap", "seal", "choose_card", "upgrade", "fourth_place_bonus", "grace_priority", "worker_actions"
    player: Player
    context: Dict[str, Any]


class GameEngine:
    """State-machine based game engine for GUI integration."""

    def __init__(self, seed: int = 42, config: Optional[GameConfig] = None, all_bots: bool = False, human_slots: Optional[List[int]] = None):
        self.rng = random.Random(seed)
        self.deal_seed = seed
        self.config = config if config is not None else GameConfig()

        # Determine which slots are human
        if human_slots is not None:
            human_set = set(human_slots)
        elif all_bots:
            human_set = set()
        else:
            human_set = {0}  # Default: P1 is human

        # CPUにランダムな性格を割り当て
        bot_rng = random.Random()
        self.players = []
        for i in range(4):
            is_bot = i not in human_set
            name = f"P{i+1}"
            strategy = assign_random_strategy(bot_rng) if is_bot else None
            self.players.append(Player(name, is_bot=is_bot, rng=random.Random(i+1), strategy=strategy))

        # 設定値でプレイヤーの初期状態を上書き
        for p in self.players:
            p.gold = self.config.start_gold
            p.basic_workers_total = self.config.initial_workers

        # カードはラウンド開始時にdeal_round_cardsで配る（deal_fixed_setsはデッキ枚数不足のため使用しない）

        # アップグレードデッキを初期化
        self.upgrade_deck = UpgradeDeck(self.rng, self.config.enabled_upgrades)

        self.round_no = 0
        self.phase = "round_start"  # Current phase
        self.sub_phase = None  # Sub-phase within a phase
        self.revealed_upgrades: List[str] = []
        self.ranked_players: List[Player] = []
        self.upgrade_pick_index = 0

        # Trick-taking state
        self.set_index = 0
        self.leader_index = 0
        self.full_hands: Dict[str, List[Card]] = {}
        self.playable_hands: Dict[str, List[Card]] = {}
        self.sealed_by_player: Dict[str, List[Card]] = {}
        self.remaining_deck: List[Card] = []  # ラウンド配札後の残りデッキ
        self.current_trick = 0
        self.trick_plays: List[Tuple[Player, Card]] = []
        self.last_trick_plays: List[Tuple[Player, Card]] = []  # 直前のトリックのプレイ（表示用）
        self.lead_card: Optional[Card] = None
        self.trick_leader = 0
        self.trick_player_offset = 0
        self.trick_play_just_happened = False  # Animation flag: True after any card play in a trick

        # Worker placement state (ナショエコ式)
        self.wp_player_index = 0
        self.wp_actions: List[str] = []
        self.wp_placement_state: Optional[PlacementState] = None
        self.wp_order: List[Player] = []
        self.wp_order_idx = 0  # round-robin index within order
        self.wp_grace_priority: Set[str] = set()

        # Trick history for display (current round)
        self.trick_history: List[Dict[str, Any]] = []

        # Game log for display
        self.log_messages: List[str] = []

        self._pending_input: Optional[InputRequest] = None
        self._pending_ritual_action: Optional[str] = None

    def _log(self, msg: str):
        self.log_messages.append(msg)

    def _build_shared_board(self) -> List[Dict[str, Any]]:
        """共有ボードの状態を返す"""
        board = []
        for p in self.players:
            seen_leveled: Set[str] = set()
            for idx, spot in enumerate(p.personal_spots):
                if spot in p.leveled_spots:
                    if spot in seen_leveled:
                        continue
                    seen_leveled.add(spot)
                    board.append({"owner": p.name, "type": spot, "level": 2})
                else:
                    board.append({"owner": p.name, "type": spot, "level": 1})
        return board

    def get_state(self) -> Dict[str, Any]:
        """Return current game state for display."""
        # 現在のトリックのプレイのみ表示（完了トリックはクライアント側ポップアップで表示）
        if self.phase == "trick":
            display_plays = self.trick_plays
        else:
            display_plays = []
        return {
            "round_no": self.round_no,
            "rounds": self.config.rounds,
            "phase": self.phase,
            "sub_phase": self.sub_phase,
            "players": snapshot_players(self.players),
            "revealed_upgrades": self.revealed_upgrades[:],
            "trick_history": self.trick_history[:],
            "current_trick": self.current_trick,
            "current_trick_plays": [(p.name, c) for p, c in display_plays],
            "trick_play_just_happened": self.trick_play_just_happened,
            "trick_leader": self.trick_leader,
            "sealed_by_player": {name: [str(c) for c in cards] for name, cards in self.sealed_by_player.items()},
            "log": self.log_messages[-20:],  # Last 20 messages
            "game_over": self.phase == "game_end",
            "shared_board": self._build_shared_board(),
        }

    def get_pending_input(self) -> Optional[InputRequest]:
        """Return pending input request, or None if no input needed."""
        return self._pending_input

    def provide_input(self, response: Any) -> None:
        """Provide response to pending input request."""
        if self._pending_input is None:
            return

        req_type = self._pending_input.type
        player = self._pending_input.player

        if req_type == "declaration":
            player.declared_tricks = response
            self._log(f"{player.name} が {response} トリックを宣言")
            self._pending_input = None

        elif req_type == "seal":
            # response is list of Card objects
            for c in response:
                self.full_hands[player.name].remove(c)
            self.sealed_by_player[player.name] = response
            self.playable_hands[player.name] = self.full_hands[player.name][:]
            self._log(f"{player.name} 公開封印: {', '.join(str(c) for c in response)}")
            self._pending_input = None

        elif req_type == "choose_card":
            hand = self.playable_hands[player.name]
            hand.remove(response)
            self.trick_plays.append((player, response))
            if self.lead_card is None:
                self.lead_card = response
            self._pending_input = None
            self.trick_play_just_happened = True

        elif req_type == "upgrade":
            # response is upgrade string or "GOLD"
            if response == "GOLD":
                gold_amount = self.config.take_gold_instead
                player.gold += gold_amount
                self._log(f"{player.name} が {gold_amount} 金貨を獲得")
                self._pending_input = None
            else:
                # 2枚目の場合はLv2か別枠かを選択させる
                is_second = response in ("UP_TRADE", "UP_HUNT", "UP_PRAY", "UP_RITUAL") and player.personal_spots.count(response) >= 1
                if is_second:
                    self.revealed_upgrades.remove(response)
                    # 次のinputでlevel_up選択を求める
                    self._pending_input = InputRequest(
                        type="upgrade_level_choice",
                        player=player,
                        context={"upgrade": response},
                    )
                else:
                    self.revealed_upgrades.remove(response)
                    apply_upgrade(player, response)
                    self._log(f"{player.name} 獲得: {upgrade_name(response)}")
                    self._pending_input = None

        elif req_type == "upgrade_level_choice":
            # response is True (Lv2) or False (別枠)
            upgrade = self._pending_input.context["upgrade"]
            apply_upgrade(player, upgrade, response)
            lv_info = " → Lv2" if response else " → 別枠"
            self._log(f"{player.name} 獲得: {upgrade_name(upgrade)}{lv_info}")
            self._pending_input = None

        elif req_type == "fourth_place_bonus":
            # response is "GOLD" or "GRACE"
            if response == "GOLD":
                player.gold += self.config.rescue_gold_for_4th
                self._log(f"救済: {player.name} +{self.config.rescue_gold_for_4th} 金貨")
            else:  # GRACE
                player.grace_points += GRACE_4TH_PLACE_BONUS
                self._log(f"救済: {player.name} +{GRACE_4TH_PLACE_BONUS} 恩寵")
            self._pending_input = None
            # Move to worker_placement phase
            self.phase = "worker_placement"
            self.wp_placement_state = None  # fresh init in step()

        elif req_type == "grace_hand_swap":
            # response is True for full swap, or None/False to skip
            if response:
                hand = self.full_hands[player.name]
                old_hand = hand[:]
                player.grace_points -= GRACE_HAND_SWAP_COST
                self.remaining_deck.extend(hand)
                hand.clear()
                self.rng.shuffle(self.remaining_deck)
                for _ in range(len(old_hand)):
                    hand.append(self.remaining_deck.pop(0))
                self._log(f"{player.name} 手札全交換: {' '.join(str(c) for c in old_hand)} → {' '.join(str(c) for c in hand)}")
            self._pending_input = None

        elif req_type == "worker_actions":
            # ナショエコ式: response is a single action string
            action = response
            ps = self.wp_placement_state
            if ps is not None:
                # RITUALスポットかチェック（人間プレイヤーの場合は選択UIを表示）
                is_ritual = (action.startswith("SPOT:") and action.split(":", 3)[3] == "UP_RITUAL")
                if is_ritual and not player.is_bot:
                    # RITUALの報酬選択を pending input にする
                    owner_name = action.split(":", 3)[1]
                    owner = next((p for p in ps.all_players if p.name == owner_name), player)
                    level = 2 if "UP_RITUAL" in owner.leveled_spots else 1
                    self._pending_ritual_action = action
                    self._pending_input = InputRequest(
                        type="ritual_choice",
                        player=player,
                        context={
                            "grace_amount": PERSONAL_RITUAL_GRACE + (level - 1),
                            "gold_amount": PERSONAL_RITUAL_GOLD + (level - 1),
                        },
                    )
                    return
                result = resolve_single_action(player, action, ps)
                ps.workers_remaining[player.name] -= 1
                effects_str = ", ".join(result["effects"])
                self._log(f"{player.name}: {result['display']} → {effects_str}")
                self.wp_order_idx += 1
            self._pending_input = None

        elif req_type == "ritual_choice":
            # response: "grace" or "gold"
            action = self._pending_ritual_action
            ps = self.wp_placement_state
            if ps is not None:
                # _choose_ritual_rewardをバイパスして直接解決
                parts = action.split(":", 3)
                owner_name = parts[1]
                idx = int(parts[2])
                owner = next((p for p in ps.all_players if p.name == owner_name), player)
                is_owner = (player.name == owner_name)
                level = 2 if "UP_RITUAL" in owner.leveled_spots else 1
                grace_amount = PERSONAL_RITUAL_GRACE + (level - 1)
                gold_amount = PERSONAL_RITUAL_GOLD + (level - 1)

                result: Dict[str, Any] = {"action": action, "display": _spot_display_name(action, player, ps.all_players), "effects": []}
                used = ps.personal_spots_used.setdefault(owner_name, set())
                used.add(idx)
                if "UP_RITUAL" in owner.leveled_spots:
                    for i2, s2 in enumerate(owner.personal_spots):
                        if s2 == "UP_RITUAL":
                            used.add(i2)
                if not is_owner:
                    owner.gold += 1
                    result["effects"].append(f"({owner_name}に+1金収入)")

                if response == "grace":
                    player.grace_points += grace_amount
                    result["effects"].append(f"+{grace_amount}恩寵")
                else:
                    player.gold += gold_amount
                    result["effects"].append(f"+{gold_amount}金")
                player.basic_workers_total -= 1
                player.ritual_consumed_this_round += 1
                result["effects"].append("ワーカー-1(永久消費)")

                ps.workers_remaining[player.name] -= 1
                effects_str = ", ".join(result["effects"])
                self._log(f"{player.name}: {result['display']} → {effects_str}")
                self.wp_order_idx += 1
            self._pending_ritual_action = None
            self._pending_input = None

        elif req_type == "grace_priority":
            # response: True/False (use grace priority or not)
            if response:
                player.grace_points -= GRACE_PRIORITY_COST
                self.wp_grace_priority.add(player.name)
                self._log(f"{player.name} が先行権を獲得 (恩寵 -{GRACE_PRIORITY_COST})")
            self._grace_priority_idx += 1
            self._pending_input = None

    def step(self) -> bool:
        """
        Advance game state. Returns True if game continues, False if ended.
        Will stop and return True when human input is needed.
        """
        if self._pending_input is not None:
            return True  # Waiting for input

        if self.phase == "game_end":
            return False

        # Phase: round_start
        if self.phase == "round_start":
            if self.round_no >= self.config.rounds:
                self._finish_game()
                return False

            self._log(f"=== ラウンド {self.round_no + 1}/{self.config.rounds} ===")
            self.revealed_upgrades = self.upgrade_deck.reveal(REVEAL_UPGRADES)
            self._log(f"アップグレード: {', '.join(upgrade_name(u) for u in self.revealed_upgrades)}")

            self.set_index = self.round_no % SETS_PER_GAME
            self.leader_index = self.round_no % len(self.players)

            for p in self.players:
                p.tricks_won_this_round = 0
                p.declared_tricks = None
                p.ritual_consumed_this_round = 0
            self.last_trick_plays = []

            # ラウンドごとにカードを配る（デッキをリシャッフル）
            round_hands, self.remaining_deck = deal_round_cards(
                self.players, self.round_no, self.rng, None
            )
            self.full_hands = {p.name: round_hands[p.name][:] for p in self.players}
            self.playable_hands = {}
            self.sealed_by_player = {}
            self.trick_history = []  # Clear trick history for new round

            self.phase = "declaration"
            self.sub_phase = 0  # Player index
            return True

        # Phase: declaration
        if self.phase == "declaration":
            player = self.players[self.sub_phase]
            if player.is_bot:
                player.declared_tricks = declare_tricks(player, self.full_hands[player.name][:], self.set_index)
                self._log(f"{player.name} が {player.declared_tricks} トリックを宣言")
                self.sub_phase += 1
            else:
                self._pending_input = InputRequest(
                    type="declaration",
                    player=player,
                    context={
                        "hand": self.full_hands[player.name][:],
                        "set_index": self.set_index,
                    }
                )
                self.sub_phase += 1
                return True

            if self.sub_phase >= len(self.players):
                self.phase = "grace_hand_swap"
                self.sub_phase = 0
            return True

        # Phase: grace_hand_swap (before seal)
        if self.phase == "grace_hand_swap":
            if not GRACE_ENABLED or len(self.remaining_deck) == 0:
                # 恩寵無効またはデッキが空なら即座にsealフェーズへ
                self.phase = "seal"
                self.sub_phase = 0
                return True

            player = self.players[self.sub_phase]
            hand = self.full_hands[player.name]

            if player.is_bot:
                # ボットの手札全交換ロジック（grace_hand_swap関数と同等）
                if player.grace_points >= GRACE_HAND_SWAP_COST and len(self.remaining_deck) >= len(hand):
                    non_trump = [c for c in hand if not c.is_trump()]
                    if non_trump:
                        avg_rank = sum(c.rank for c in non_trump) / len(non_trump)
                        if avg_rank <= 2.5 and player.grace_points >= GRACE_HAND_SWAP_COST + 1:
                            old_hand = hand[:]
                            self.remaining_deck.extend(hand)
                            hand.clear()
                            self.rng.shuffle(self.remaining_deck)
                            for _ in range(len(old_hand)):
                                hand.append(self.remaining_deck.pop(0))
                            player.grace_points -= GRACE_HAND_SWAP_COST
                            self._log(f"{player.name} 手札全交換: {' '.join(str(c) for c in old_hand)} → {' '.join(str(c) for c in hand)}")
                self.sub_phase += 1
            else:
                # 人間プレイヤー: 恩寵があれば交換の機会を与える
                if player.grace_points >= GRACE_HAND_SWAP_COST and len(self.remaining_deck) > 0:
                    self._pending_input = InputRequest(
                        type="grace_hand_swap",
                        player=player,
                        context={
                            "hand": hand[:],
                            "grace_points": player.grace_points,
                            "cost": GRACE_HAND_SWAP_COST,
                        }
                    )
                    self.sub_phase += 1
                    return True
                else:
                    self.sub_phase += 1

            if self.sub_phase >= len(self.players):
                self.phase = "seal"
                self.sub_phase = 0
            return True

        # Phase: seal
        if self.phase == "seal":
            player = self.players[self.sub_phase]
            hand = self.full_hands[player.name]

            if player.is_bot:
                sealed = seal_cards(player, hand, self.set_index)
                self.sealed_by_player[player.name] = sealed
                self.playable_hands[player.name] = hand[:]
                self._log(f"{player.name} 公開封印: {', '.join(str(c) for c in sealed)}")
                self.sub_phase += 1
            else:
                self._pending_input = InputRequest(
                    type="seal",
                    player=player,
                    context={
                        "hand": hand[:],
                        "need_seal": CARDS_PER_SET - TRICKS_PER_ROUND,
                    }
                )
                self.sub_phase += 1
                return True

            if self.sub_phase >= len(self.players):
                self.phase = "trick"
                self.current_trick = 0
                self.trick_leader = self.leader_index
                self._start_trick()
            return True

        # Phase: trick
        if self.phase == "trick":
            return self._process_trick()

        # Phase: grace_priority
        if self.phase == "grace_priority":
            return self._process_grace_priority()

        # Phase: upgrade_pick
        if self.phase == "upgrade_pick":
            if self.upgrade_pick_index >= len(self.ranked_players):
                # 選ばれなかったカードを捨て札に移動
                if self.revealed_upgrades:
                    self.upgrade_deck.discard_remaining(self.revealed_upgrades)
                    self.revealed_upgrades = []

                # Move to fourth_place_bonus phase
                self.phase = "fourth_place_bonus"
                return True

            player = self.ranked_players[self.upgrade_pick_index]
            available = [u for u in self.revealed_upgrades if can_take_upgrade(player, u)]

            if player.is_bot:
                choice = choose_upgrade_or_gold(player, self.revealed_upgrades, self.round_no)
                if choice == "GOLD":
                    gold_amount = self.config.take_gold_instead
                    player.gold += gold_amount
                    self._log(f"{player.name} が {gold_amount} 金貨を獲得")
                else:
                    self.revealed_upgrades.remove(choice)
                    level_up = None
                    if choice in ("UP_TRADE", "UP_HUNT", "UP_PRAY", "UP_RITUAL") and player.personal_spots.count(choice) >= 1:
                        level_up = _bot_choose_level_up(player, choice)
                    apply_upgrade(player, choice, level_up)
                    lv_info = " → Lv2" if level_up is True else (" → 別枠" if level_up is False else "")
                    self._log(f"{player.name} 獲得: {upgrade_name(choice)}{lv_info}")
                self.upgrade_pick_index += 1
            else:
                self._pending_input = InputRequest(
                    type="upgrade",
                    player=player,
                    context={
                        "available": available,
                        "revealed": self.revealed_upgrades[:],
                    }
                )
                self.upgrade_pick_index += 1
                return True
            return True

        # Phase: fourth_place_bonus
        if self.phase == "fourth_place_bonus":
            fourth = self.ranked_players[-1]

            if fourth.is_bot:
                # ボットのロジック（CLIと同じ）
                strat = STRATEGIES.get(fourth.strategy, STRATEGIES['BALANCED'])
                chose_grace = False

                # 恩寵特化は常に恩寵を選択
                if GRACE_ENABLED and strat.get('prefer_grace', False):
                    fourth.grace_points += GRACE_4TH_PLACE_BONUS
                    self._log(f"救済: {fourth.name} +{GRACE_4TH_PLACE_BONUS} 恩寵")
                    chose_grace = True
                elif GRACE_ENABLED:
                    # 次の5恩寵境界に近い場合は恩寵を選択
                    next_boundary = (fourth.grace_points // GRACE_VP_PER_N + 1) * GRACE_VP_PER_N
                    diff = next_boundary - fourth.grace_points
                    if 0 < diff <= 2:  # 次の5恩寵境界まであと2点以内
                        fourth.grace_points += GRACE_4TH_PLACE_BONUS
                        self._log(f"救済: {fourth.name} +{GRACE_4TH_PLACE_BONUS} 恩寵")
                        chose_grace = True

                if not chose_grace:
                    # 金貨を選択
                    fourth.gold += self.config.rescue_gold_for_4th
                    self._log(f"救済: {fourth.name} +{self.config.rescue_gold_for_4th} 金貨")

                self.phase = "worker_placement"
                self.wp_placement_state = None
            else:
                # 人間プレイヤー
                if GRACE_ENABLED:
                    self._pending_input = InputRequest(
                        type="fourth_place_bonus",
                        player=fourth,
                        context={
                            "gold_amount": self.config.rescue_gold_for_4th,
                            "grace_amount": GRACE_4TH_PLACE_BONUS,
                        }
                    )
                    return True
                else:
                    # 恩寵無効時は金貨のみ
                    fourth.gold += self.config.rescue_gold_for_4th
                    self._log(f"救済: {fourth.name} +{self.config.rescue_gold_for_4th} 金貨")
                    self.phase = "worker_placement"
                    self.wp_placement_state = None
            return True

        # Phase: worker_placement (ナショエコ式ラウンドロビン)
        if self.phase == "worker_placement":
            # 初回: PlacementState初期化
            if self.wp_placement_state is None:
                self.wp_placement_state = PlacementState()
                self.wp_placement_state.all_players = self.players
                self.wp_order = determine_placement_order(self.players, self.leader_index, self.wp_grace_priority)
                self.wp_placement_state.placement_order = self.wp_order
                for p in self.players:
                    self.wp_placement_state.workers_remaining[p.name] = p.basic_workers_total
                    self.wp_placement_state.personal_spots_used[p.name] = set()
                self.wp_order_idx = 0
                self._log(f"配置順: {' → '.join(p.name for p in self.wp_order)}")

            ps = self.wp_placement_state

            # 全員配置完了チェック
            if not any(ps.workers_remaining[p.name] > 0 for p in self.wp_order):
                self.wp_placement_state = None  # reset for next round
                self.phase = "wage_payment"
                return True

            # 現在のプレイヤーを見つける（ワーカー残りがある次のプレイヤー）
            player = None
            for _ in range(len(self.wp_order)):
                candidate = self.wp_order[self.wp_order_idx % len(self.wp_order)]
                if ps.workers_remaining[candidate.name] > 0:
                    player = candidate
                    break
                self.wp_order_idx += 1

            if player is None:
                self.wp_placement_state = None
                self.phase = "wage_payment"
                return True

            available = get_available_actions(player, ps)

            if not available:
                # PASS
                ps.workers_remaining[player.name] = 0
                self._log(f"{player.name}: PASS（配置先なし）")
                self.wp_order_idx += 1
                return True

            if player.is_bot:
                action = bot_choose_single_action(player, available, ps, self.round_no)
                result = resolve_single_action(player, action, ps)
                ps.workers_remaining[player.name] -= 1
                effects_str = ", ".join(result["effects"])
                self._log(f"{player.name}: {result['display']} → {effects_str}")
                self.wp_order_idx += 1
            else:
                self._pending_input = InputRequest(
                    type="worker_actions",
                    player=player,
                    context={
                        "num_workers": ps.workers_remaining[player.name],
                        "available_actions": available,
                        "placement_state": ps,
                        "player_name": player.name,
                    }
                )
                return True
            return True

        # Phase: wage_payment
        if self.phase == "wage_payment":
            initial_rate = WAGE_CURVE[self.round_no]
            self._log(f"--- 給料支払い (初期ワーカー={initial_rate}金/人) ---")

            for p in self.players:
                res = pay_wages_and_debt(
                    p, self.round_no,
                    debt_multiplier=self.config.debt_penalty_multiplier,
                    debt_cap=self.config.debt_penalty_cap,
                    initial_workers_config=self.config.initial_workers,
                )
                self._log(f"{p.name}: Gold {res['gold_before']}->{res['gold_after']}, VP {res['vp_before']}->{res['vp_after']}")

            # Activate new hires
            for p in self.players:
                if p.basic_workers_new_hires > 0:
                    p.basic_workers_total += p.basic_workers_new_hires
                    p.basic_workers_new_hires = 0

            # WITCH_BLESSING: 毎ラウンド終了時+1恩寵
            if GRACE_ENABLED:
                for p in self.players:
                    if "WITCH_BLESSING" in p.witches:
                        p.grace_points += 1
                        self._log(f"{p.name}: 《祈祷の魔女》+1恩寵")

            self.round_no += 1
            self.phase = "round_start"
            return True

        return True

    def _start_trick(self):
        """Initialize a new trick."""
        self.last_trick_plays = self.trick_plays[:]  # 直前のトリックを保存
        self.trick_plays = []
        self.lead_card = None
        self.trick_player_offset = 0

    def _process_trick(self) -> bool:
        """Process trick phase. Returns True to continue."""
        if self.trick_player_offset >= len(self.players):
            # Trick complete
            assert self.lead_card is not None
            winner = trick_winner(self.lead_card.suit, self.trick_plays)
            winner.tricks_won_this_round += 1
            plays_str = " | ".join(f"{pl.name}:{c}" for pl, c in self.trick_plays)
            self._log(f"トリック {self.current_trick + 1}: {plays_str} -> {winner.name} 勝利")

            # Save trick history for display
            self.trick_history.append({
                "trick_no": self.current_trick + 1,
                "plays": [(pl.name, str(c)) for pl, c in self.trick_plays],
                "winner": winner.name,
                "lead_suit": self.lead_card.suit,
            })

            self.trick_leader = next(i for i, p in enumerate(self.players) if p.name == winner.name)
            self.current_trick += 1

            if self.current_trick >= TRICKS_PER_ROUND:
                # All tricks done, show summary and apply declaration bonus
                self._log("--- トリック結果 ---")
                for p in self.players:
                    status = "✓" if p.tricks_won_this_round == p.declared_tricks else ""
                    self._log(f"  {p.name}: {p.tricks_won_this_round} トリック (宣言 {p.declared_tricks}) {status}")
                self._apply_declaration_bonus()
                # Grace priority
                self.wp_grace_priority = set()
                if GRACE_ENABLED:
                    self._grace_priority_pending_players = self._get_grace_priority_candidates()
                    self._grace_priority_idx = 0
                    if self._grace_priority_pending_players:
                        self.phase = "grace_priority"
                        return True
                self._finish_tricks_to_upgrade()
            else:
                self._start_trick()
            return True

        idx = (self.trick_leader + self.trick_player_offset) % len(self.players)
        player = self.players[idx]
        hand = self.playable_hands[player.name]

        if player.is_bot:
            chosen = choose_card(player, self.lead_card, hand)
            hand.remove(chosen)
            self.trick_plays.append((player, chosen))
            if self.lead_card is None:
                self.lead_card = chosen
            self.trick_player_offset += 1
            self.trick_play_just_happened = True
        else:
            legal = legal_cards(hand, self.lead_card)
            self._pending_input = InputRequest(
                type="choose_card",
                player=player,
                context={
                    "hand": hand[:],
                    "legal": legal,
                    "lead_card": self.lead_card,
                    "plays_so_far": [(p.name, str(c)) for p, c in self.trick_plays],
                }
            )
            self.trick_player_offset += 1
            return True
        return True

    def _get_grace_priority_candidates(self) -> List[Player]:
        """恩寵先行権の候補プレイヤーを返す"""
        trick_counts = [p.tricks_won_this_round for p in self.players]
        has_ties = len(trick_counts) != len(set(trick_counts))
        if not has_ties:
            return []
        candidates = []
        for p in self.players:
            if p.grace_points < GRACE_PRIORITY_COST:
                continue
            tied = [q for q in self.players if q.name != p.name and q.tricks_won_this_round == p.tricks_won_this_round]
            if tied:
                candidates.append(p)
        return candidates

    def _process_grace_priority(self) -> bool:
        """恩寵先行権フェーズの処理"""
        while self._grace_priority_idx < len(self._grace_priority_pending_players):
            p = self._grace_priority_pending_players[self._grace_priority_idx]
            if p.is_bot:
                # Bot: 恩寵に余裕があれば先行権を使う
                if p.grace_points >= GRACE_PRIORITY_COST + 2:
                    p.grace_points -= GRACE_PRIORITY_COST
                    self.wp_grace_priority.add(p.name)
                    self._log(f"{p.name} が先行権を獲得 (恩寵 -{GRACE_PRIORITY_COST})")
                self._grace_priority_idx += 1
            else:
                # Human: pending input
                self._pending_input = InputRequest(
                    type="grace_priority",
                    player=p,
                    context={
                        "cost": GRACE_PRIORITY_COST,
                        "grace": p.grace_points,
                    },
                )
                return True
        # All done
        self._finish_tricks_to_upgrade()
        return True

    def _finish_tricks_to_upgrade(self):
        """トリック終了後、アップグレード選択フェーズへ移行"""
        self.ranked_players = rank_players_for_upgrade(self.players, self.leader_index, self.wp_grace_priority)
        self.upgrade_pick_index = 0
        self.phase = "upgrade_pick"

    def _apply_declaration_bonus(self):
        """Apply declaration bonus to players who matched their declaration."""
        bonus_vp = self.config.declaration_bonus_vp
        for p in self.players:
            if p.tricks_won_this_round == p.declared_tricks:
                p.vp += bonus_vp
                self._log(f"宣言成功: {p.name} が {p.declared_tricks} を的中 -> +{bonus_vp} VP")
                # ピタリ賞: 宣言成功で+1恩寵
                if GRACE_ENABLED:
                    p.grace_points += 1
                    self._log(f"  (ピタリ賞: +1恩寵)")
                # 宣言0成功で追加恩寵ボーナス
                if GRACE_ENABLED and p.declared_tricks == 0:
                    if "WITCH_ZERO_MASTER" in p.witches:
                        # 慎重な予言者: GameEngineではBot AIで自動選択
                        choice = _choose_zero_master_reward(p, force_bot=True)
                        if choice == "GRACE":
                            p.grace_points += WITCH_ZERO_GRACE
                            self._log(f"  (《慎重な予言者》効果: +{WITCH_ZERO_GRACE}恩寵)")
                        elif choice == "GOLD":
                            p.gold += WITCH_ZERO_GOLD
                            self._log(f"  (《慎重な予言者》効果: +{WITCH_ZERO_GOLD}金)")
                        elif choice == "VP":
                            p.vp += WITCH_ZERO_VP
                            self._log(f"  (《慎重な予言者》効果: +{WITCH_ZERO_VP}VP)")
        # WITCH_MIRROR: 他プレイヤーの宣言成功時+1金
        others_success_count = sum(1 for p in self.players if p.tricks_won_this_round == p.declared_tricks)
        for p in self.players:
            if "WITCH_MIRROR" in p.witches:
                own_success = 1 if p.tricks_won_this_round == p.declared_tricks else 0
                mirror_gold = others_success_count - own_success
                if mirror_gold > 0:
                    p.gold += mirror_gold
                    self._log(f"《鏡の魔女》効果: {p.name} → 他者{mirror_gold}人成功 → +{mirror_gold}金")

    def _finish_game(self):
        """Finalize game and determine winner."""
        # 金貨→恩寵変換（恩寵→VP変換の前に適用）
        if GRACE_ENABLED and GOLD_TO_GRACE_RATE > 0:
            self._log("--- 金貨→恩寵変換 ---")
            for p in self.players:
                grace_gained = p.gold // GOLD_TO_GRACE_RATE
                if grace_gained > 0:
                    gold_spent = grace_gained * GOLD_TO_GRACE_RATE
                    p.gold -= gold_spent
                    p.grace_points += grace_gained
                    self._log(f"{p.name}: {gold_spent}G → +{grace_gained}恩寵 (残{p.gold}G)")
                else:
                    self._log(f"{p.name}: {p.gold}G ({GOLD_TO_GRACE_RATE}G未満)")

        # 恩寵→VP変換（ゲーム終了時）
        if GRACE_ENABLED:
            self._log("--- 恩寵→VP変換 ---")
            for p in self.players:
                grace_bonus = (p.grace_points // GRACE_VP_PER_N) * GRACE_VP_AMOUNT
                if grace_bonus > 0:
                    p.vp += grace_bonus
                    self._log(f"{p.name}: 恩寵{p.grace_points}点 ({p.grace_points // GRACE_VP_PER_N}×{GRACE_VP_AMOUNT}) → +{grace_bonus}VP")
                else:
                    self._log(f"{p.name}: 恩寵{p.grace_points}点 ({GRACE_VP_PER_N}未満)")

        # 金貨→VP変換（恩寵変換後の残り金貨）
        gold_to_vp_rate = self.config.gold_to_vp_rate
        self._log("--- 金貨→VP変換 ---")
        for p in self.players:
            bonus_vp = p.gold // gold_to_vp_rate if gold_to_vp_rate > 0 else 0
            if bonus_vp > 0:
                self._log(f"{p.name}: {p.gold}金貨 -> +{bonus_vp}VP")
                p.vp += bonus_vp

        # 負債ペナルティ（ゲーム終了時）
        self._log("--- 負債ペナルティ ---")
        for p in self.players:
            if p.accumulated_debt > 0:
                penalty = calculate_debt_penalty(p.accumulated_debt)
                p.vp -= penalty
                self._log(f"{p.name}: 累積負債{p.accumulated_debt}金 → -{penalty}VP")
            else:
                self._log(f"{p.name}: 負債なし")

        self.phase = "game_end"
        players_sorted = sorted(self.players, key=lambda p: (p.vp, p.gold), reverse=True)
        self._log("=== ゲーム終了 ===")
        for i, p in enumerate(players_sorted, start=1):
            debt_info = f" 負債={p.accumulated_debt}" if p.accumulated_debt > 0 else ""
            self._log(f"{i}. {p.name} VP={p.vp} 金貨={p.gold}{debt_info}")
        self._log(f"勝者: {players_sorted[0].name}")


# ======= Simulation =======

def run_single_game_quiet(
    seed: int,
    max_rank: int = 5,
    num_decks: int = NUM_DECKS,
    gold_to_grace_rate: int = GOLD_TO_GRACE_RATE,
    zero_tricks_gold: int = 0,
) -> Dict[str, Any]:
    """Run a single game with all bots, no output. Returns final scores."""
    rng = random.Random(seed)

    # CPUにランダムな性格を割り当て
    bot_rng = random.Random(seed + 100)
    players = [
        Player("P1", is_bot=True, rng=random.Random(seed + 1), strategy=assign_random_strategy(bot_rng)),
        Player("P2", is_bot=True, rng=random.Random(seed + 2), strategy=assign_random_strategy(bot_rng)),
        Player("P3", is_bot=True, rng=random.Random(seed + 3), strategy=assign_random_strategy(bot_rng)),
        Player("P4", is_bot=True, rng=random.Random(seed + 4), strategy=assign_random_strategy(bot_rng)),
    ]

    # プレイヤーのsetsを空リストで初期化
    for p in players:
        p.sets = []

    # アップグレードデッキを初期化
    upgrade_deck = UpgradeDeck(rng)

    # 魔女デッキを作成（ラウンド3用）
    witch_pool: List[str] = []
    for w in ALL_WITCHES:
        count = WITCH_POOL_COUNTS.get(w, 1)
        witch_pool.extend([w] * count)
    rng.shuffle(witch_pool)

    for round_no in range(ROUNDS):
        # ラウンド毎にデッキをリシャッフルして配札
        _, _ = deal_round_cards(players, round_no, rng, None, max_rank, num_decks)

        # ラウンド3は魔女、それ以外は通常アップグレード
        is_witch_round = (round_no == WITCH_ROUND)
        if is_witch_round:
            revealed = witch_pool[:REVEAL_UPGRADES]
            witch_pool = witch_pool[REVEAL_UPGRADES:]
        else:
            revealed = upgrade_deck.reveal(REVEAL_UPGRADES)

        set_index = round_no % SETS_PER_GAME
        leader_index = round_no % len(players)

        for p in players:
            p.tricks_won_this_round = 0
            p.ritual_consumed_this_round = 0

        # Declaration
        full_hands = {p.name: p.sets[set_index][:] for p in players}
        for p in players:
            p.declared_tricks = declare_tricks(p, full_hands[p.name][:], set_index)

        # Seal
        playable_hands = {}
        for p in players:
            hand = full_hands[p.name]
            seal_cards(p, hand, set_index)
            playable_hands[p.name] = hand[:]

        # Play tricks
        leader = leader_index
        for trick_idx in range(TRICKS_PER_ROUND):
            plays: List[Tuple[Player, Card]] = []
            lead_card: Optional[Card] = None
            for offset in range(len(players)):
                idx = (leader + offset) % len(players)
                pl = players[idx]
                hand = playable_hands[pl.name]
                chosen = choose_card(pl, lead_card, hand)
                hand.remove(chosen)
                plays.append((pl, chosen))
                if lead_card is None:
                    lead_card = chosen
            assert lead_card is not None
            winner = trick_winner(lead_card.suit, plays)
            winner.tricks_won_this_round += 1
            leader = next(i for i, pp in enumerate(players) if pp.name == winner.name)

        # Declaration bonus
        for p in players:
            if p.tricks_won_this_round == p.declared_tricks:
                p.vp += DECLARATION_BONUS_VP
                # ピタリ賞: 宣言成功で+1恩寵
                if GRACE_ENABLED:
                    p.grace_points += 1
                # 宣言0成功で追加恩寵ボーナス
                if GRACE_ENABLED and p.declared_tricks == 0:
                    if "WITCH_ZERO_MASTER" in p.witches:
                        choice = _choose_zero_master_reward(p)
                        if choice == "GRACE":
                            p.grace_points += WITCH_ZERO_GRACE
                        elif choice == "GOLD":
                            p.gold += WITCH_ZERO_GOLD
                        elif choice == "VP":
                            p.vp += WITCH_ZERO_VP

        # WITCH_MIRROR: 他プレイヤーの宣言成功時+1金
        others_success_count = sum(1 for p in players if p.tricks_won_this_round == p.declared_tricks)
        for p in players:
            if "WITCH_MIRROR" in p.witches:
                own_success = 1 if p.tricks_won_this_round == p.declared_tricks else 0
                mirror_gold = others_success_count - own_success
                if mirror_gold > 0:
                    p.gold += mirror_gold

        # 0トリックボーナス（宣言に関わらず0勝で恩寵+金貨獲得）
        if GRACE_ENABLED:
            for p in players:
                if p.tricks_won_this_round == 0:
                    p.grace_points += GRACE_ZERO_TRICKS_BONUS
                    p.gold += zero_tricks_gold if zero_tricks_gold > 0 else ZERO_TRICKS_GOLD_BONUS

        # Grace priority
        grace_priority: Set[str] = set()
        if GRACE_ENABLED:
            grace_priority = _offer_grace_priority(players, leader_index, None, round_no)

        # Upgrade pick
        ranked = rank_players_for_upgrade(players, leader_index, grace_priority)
        for p in ranked:
            choice = choose_upgrade_or_gold(p, revealed, round_no)
            if choice == "GOLD":
                p.gold += TAKE_GOLD_INSTEAD
            else:
                revealed.remove(choice)
                level_up = None
                if choice in ("UP_TRADE", "UP_HUNT", "UP_PRAY", "UP_RITUAL") and p.personal_spots.count(choice) >= 1:
                    level_up = _bot_choose_level_up(p, choice)
                apply_upgrade(p, choice, level_up)

        # 選ばれなかったカードを捨て札に移動（魔女ラウンドは捨てない）
        if revealed and not is_witch_round:
            upgrade_deck.discard_remaining(revealed)

        fourth = ranked[-1]
        choose_4th_place_bonus(fourth, None, round_no)

        # Worker placement（ナショエコ式）
        run_worker_placement_round(players, round_no, leader_index, grace_priority=grace_priority)

        # Wage payment
        for p in players:
            pay_wages_and_debt(p, round_no)

        # Activate hires
        for p in players:
            if p.basic_workers_new_hires > 0:
                p.basic_workers_total += p.basic_workers_new_hires
                p.basic_workers_new_hires = 0

    # Gold to Grace conversion at end (before grace→VP)
    gold_converted = []
    if gold_to_grace_rate > 0:
        for p in players:
            grace_gained = p.gold // gold_to_grace_rate
            gold_spent = grace_gained * gold_to_grace_rate
            p.gold -= gold_spent
            p.grace_points += grace_gained
            gold_converted.append(grace_gained)
    else:
        gold_converted = [0] * len(players)

    # Grace bonus at game end (5恩寵毎→3VP)
    grace_stats = {"points": [], "bonus_vp": []}
    if GRACE_ENABLED:
        for p in players:
            grace_stats["points"].append(p.grace_points)
            grace_bonus = (p.grace_points // GRACE_VP_PER_N) * GRACE_VP_AMOUNT
            p.vp += grace_bonus
            grace_stats["bonus_vp"].append(grace_bonus)

    # Gold to VP conversion at end
    for p in players:
        bonus_vp = p.gold // GOLD_TO_VP_RATE
        p.vp += bonus_vp

    # Debt penalty at game end
    for p in players:
        if p.accumulated_debt > 0:
            penalty = calculate_debt_penalty(p.accumulated_debt)
            p.vp -= penalty

    # Return results
    players_sorted = sorted(players, key=lambda p: (p.vp, p.gold), reverse=True)
    vps = [p.vp for p in players_sorted]
    grace_points = [p.grace_points for p in players_sorted]

    # Witch stats: for each player, record witches owned and their ranking
    witch_stats = []
    for rank, p in enumerate(players_sorted, start=1):
        witch_stats.append({
            "rank": rank,
            "vp": p.vp,
            "witches": list(p.witches),
        })

    return {
        "winner": players_sorted[0].name,
        "vps": vps,
        "vp_diff_1st_2nd": vps[0] - vps[1],
        "vp_diff_1st_last": vps[0] - vps[-1],
        "grace_points": grace_points,
        "grace_stats": grace_stats,
        "witch_stats": witch_stats,
        "gold_converted_to_grace": gold_converted,
    }


def run_simulation(max_rank: int, num_games: int = 100) -> Dict[str, Any]:
    """Run multiple games with specified max rank and collect statistics."""
    results = []
    for game_id in range(num_games):
        seed = game_id * 1000 + max_rank
        result = run_single_game_quiet(seed, max_rank)
        results.append(result)

    # Calculate statistics
    vp_diffs = [r["vp_diff_1st_2nd"] for r in results]
    avg_diff = sum(vp_diffs) / len(vp_diffs)
    std_diff = (sum((x - avg_diff) ** 2 for x in vp_diffs) / len(vp_diffs)) ** 0.5

    return {
        "max_rank": max_rank,
        "num_games": num_games,
        "avg_vp_diff": avg_diff,
        "std_vp_diff": std_diff,
        "min_diff": min(vp_diffs),
        "max_diff": max(vp_diffs),
    }


def run_all_simulations():
    """Run simulations for rank ranges 5-10, 100 games each.

    Note: max_rank must be at least 5 for 2 decks to have enough cards.
    2 decks * 4 suits * 5 ranks = 40 cards + 2 trump = 42 total (need 20 for 4p*5c)
    """
    print("=== カードランク最適化シミュレーション ===")
    print(f"各設定で100ゲーム実行中...\n")

    results = []
    for max_rank in range(5, 11):
        print(f"ランク1-{max_rank} をテスト中...", end=" ", flush=True)
        result = run_simulation(max_rank, num_games=100)
        results.append(result)
        print(f"完了 (平均VP差: {result['avg_vp_diff']:.2f})")

    print("\n" + "=" * 50)
    print("=== シミュレーション結果 ===")
    print("=" * 50)
    print(f"{'ランク範囲':<12} {'平均VP差':<10} {'標準偏差':<10} {'最小':<6} {'最大':<6}")
    print("-" * 50)

    best = min(results, key=lambda r: r["avg_vp_diff"])
    for r in results:
        marker = " ★" if r == best else ""
        print(f"1-{r['max_rank']:<10} {r['avg_vp_diff']:<10.2f} {r['std_vp_diff']:<10.2f} {r['min_diff']:<6} {r['max_diff']:<6}{marker}")

    print("-" * 50)
    print(f"\n推奨: ランク 1-{best['max_rank']} (最小平均VP差: {best['avg_vp_diff']:.2f})")


def run_deck_simulation(num_decks: int, num_games: int = 100) -> Dict[str, Any]:
    """Run simulation with specified deck count. Trump is fixed at 2 cards (no rank)."""
    results = []
    for game_id in range(num_games):
        seed = game_id * 1000 + num_decks * 100
        result = run_single_game_quiet(seed, max_rank=5, num_decks=num_decks)
        results.append(result)

    vp_diffs = [r["vp_diff_1st_2nd"] for r in results]
    avg_diff = sum(vp_diffs) / len(vp_diffs)
    std_diff = (sum((x - avg_diff) ** 2 for x in vp_diffs) / len(vp_diffs)) ** 0.5

    return {
        "num_decks": num_decks,
        "total_cards": num_decks * 20 + TRUMP_COUNT,  # 4suits * 5ranks = 20, plus 2 trumps
        "num_games": num_games,
        "avg_vp_diff": avg_diff,
        "std_vp_diff": std_diff,
    }


def run_all_deck_simulations():
    """Run simulations for different deck counts. Trump is fixed at 2 cards (no rank)."""
    print("=== デッキ数最適化シミュレーション ===")
    print("(切り札は2枚固定、ランクなし)")
    print(f"各設定で100ゲーム実行中...\n")

    # テスト設定: デッキ3-5
    configs = [3, 4, 5]

    results = []
    for num_decks in configs:
        total = num_decks * 20 + TRUMP_COUNT
        print(f"{num_decks}デッキ (計{total}枚) をテスト中...", end=" ", flush=True)
        result = run_deck_simulation(num_decks, num_games=100)
        results.append(result)
        print(f"完了 (平均VP差: {result['avg_vp_diff']:.2f})")

    print("\n" + "=" * 60)
    print("=== シミュレーション結果 ===")
    print("=" * 60)
    print(f"{'設定':<20} {'総枚数':<8} {'平均VP差':<10} {'標準偏差':<10}")
    print("-" * 60)

    best = min(results, key=lambda r: r["avg_vp_diff"])
    for r in results:
        marker = " ★" if r == best else ""
        config = f"{r['num_decks']}デッキ"
        print(f"{config:<20} {r['total_cards']:<8} {r['avg_vp_diff']:<10.2f} {r['std_vp_diff']:<10.2f}{marker}")

    print("-" * 60)
    print(f"\n推奨: {best['num_decks']}デッキ")


# ======= Debt Penalty Simulation =======

def choose_actions_smart_bot(
    player: Player,
    round_no: int,
    debt_multiplier: int,
    debt_cap: Optional[int],
) -> List[str]:
    """
    賢いボット: 給料支払いを考慮してアクション選択。

    戦略:
    1. 今ラウンドの給料を計算
    2. TRADEで稼げる額を計算
    3. 借金回避に必要なTRADE数を決定
    4. 余ったワーカーでHUNT/RECRUITを選択（VP期待値 vs 借金ペナルティ）
    """
    n = player.basic_workers_total
    actions: List[str] = []

    # 現在のゴールド
    current_gold = player.gold

    # 今ラウンドの給料を予測（初期ワーカーのみ給料発生）
    initial_wage_rate = WAGE_CURVE[round_no]
    initial_workers_count = min(INITIAL_WORKERS, n)
    initial_workers_count = max(0, initial_workers_count)
    expected_wage = initial_workers_count * initial_wage_rate

    # TRADEで稼げる額（共通スポット基準）
    trade_yield = SHARED_TRADE_GOLD

    # HUNTで稼げるVP（共通スポット基準）
    hunt_yield = SHARED_HUNT_VP

    # 借金1金あたりのペナルティ
    penalty_per_gold = debt_multiplier

    # 給料を払うために必要なTRADE数
    gold_needed = max(0, expected_wage - current_gold)
    trades_needed = (gold_needed + trade_yield - 1) // trade_yield if trade_yield > 0 else n
    trades_needed = min(trades_needed, n)

    # 戦略決定: HUNT vs TRADE の損益分岐
    # HUNT: +hunt_yield VP
    # TRADE: +trade_yield gold (借金回避)
    # 借金1金 = -penalty_per_gold VP
    #
    # HUNTが得になる条件: hunt_yield > trade_yield * penalty_per_gold / (実際に節約できるペナルティ)

    for i in range(n):
        if i < trades_needed:
            # 必要最低限のTRADE
            actions.append("TRADE")
        else:
            # 余剰ワーカー: HUNT vs 追加TRADE
            # HUNTのVP vs 追加で借金を減らせる価値
            #
            # 現在の予測: trades_needed回TRADEした後のゴールド
            projected_gold = current_gold + trades_needed * trade_yield
            projected_shortfall = max(0, expected_wage - projected_gold)

            if projected_shortfall > 0:
                # まだ借金が発生する → 追加TRADEの価値を計算
                # 追加TRADE: 借金がtrade_yield減る → ペナルティがtrade_yield * penalty_per_gold減る
                saved_penalty = min(trade_yield, projected_shortfall) * penalty_per_gold
                if debt_cap is not None:
                    # 上限ありの場合、すでに上限に達していたら追加TRADEの価値は低い
                    current_penalty = min(projected_shortfall * penalty_per_gold, debt_cap)
                    new_shortfall = max(0, projected_shortfall - trade_yield)
                    new_penalty = min(new_shortfall * penalty_per_gold, debt_cap) if new_shortfall > 0 else 0
                    saved_penalty = current_penalty - new_penalty

                if hunt_yield > saved_penalty:
                    # HUNTの方が得
                    actions.append("HUNT")
                else:
                    # TRADEの方が得
                    actions.append("TRADE")
                    trades_needed += 1  # 次のループ用に更新
            else:
                # 借金なし → HUNT or RECRUIT
                # 簡易判定: HUNTを優先（VPが直接増える）
                if player.rng.random() < 0.8:
                    actions.append("HUNT")
                else:
                    actions.append("RECRUIT")

    return actions


def run_single_game_with_debt_config(
    seed: int,
    debt_multiplier: int = 1,
    debt_cap: Optional[int] = None,
    use_tiered: bool = False,
) -> Dict[str, Any]:
    """Run a single game with configurable debt penalty. Returns detailed stats."""
    rng = random.Random(seed)

    # CPUにランダムな性格を割り当て
    bot_rng = random.Random(seed + 100)
    players = [
        Player("P1", is_bot=True, rng=random.Random(seed + 1), strategy=assign_random_strategy(bot_rng)),
        Player("P2", is_bot=True, rng=random.Random(seed + 2), strategy=assign_random_strategy(bot_rng)),
        Player("P3", is_bot=True, rng=random.Random(seed + 3), strategy=assign_random_strategy(bot_rng)),
        Player("P4", is_bot=True, rng=random.Random(seed + 4), strategy=assign_random_strategy(bot_rng)),
    ]

    # プレイヤーのsetsを空リストで初期化
    for p in players:
        p.sets = []

    # アップグレードデッキを初期化
    upgrade_deck = UpgradeDeck(rng)

    # 魔女デッキを作成（ラウンド3用）
    witch_pool: List[str] = []
    for w in ALL_WITCHES:
        count = WITCH_POOL_COUNTS.get(w, 1)
        witch_pool.extend([w] * count)
    rng.shuffle(witch_pool)

    # Track debt occurrences
    total_debt_events = 0
    total_debt_amount = 0
    total_debt_penalty = 0

    for round_no in range(ROUNDS):
        # ラウンド毎にデッキをリシャッフルして配札
        _, _ = deal_round_cards(players, round_no, rng, None)

        # ラウンド3は魔女、それ以外は通常アップグレード
        is_witch_round = (round_no == WITCH_ROUND)
        if is_witch_round:
            revealed = witch_pool[:REVEAL_UPGRADES]
            witch_pool = witch_pool[REVEAL_UPGRADES:]
        else:
            revealed = upgrade_deck.reveal(REVEAL_UPGRADES)

        set_index = round_no % SETS_PER_GAME
        leader_index = round_no % len(players)

        for p in players:
            p.tricks_won_this_round = 0
            p.ritual_consumed_this_round = 0

        # Declaration
        full_hands = {p.name: p.sets[set_index][:] for p in players}
        for p in players:
            p.declared_tricks = declare_tricks(p, full_hands[p.name][:], set_index)

        # Seal
        playable_hands = {}
        for p in players:
            hand = full_hands[p.name]
            seal_cards(p, hand, set_index)
            playable_hands[p.name] = hand[:]

        # Play tricks
        leader = leader_index
        for trick_idx in range(TRICKS_PER_ROUND):
            plays: List[Tuple[Player, Card]] = []
            lead_card: Optional[Card] = None
            for offset in range(len(players)):
                idx = (leader + offset) % len(players)
                pl = players[idx]
                hand = playable_hands[pl.name]
                chosen = choose_card(pl, lead_card, hand)
                hand.remove(chosen)
                plays.append((pl, chosen))
                if lead_card is None:
                    lead_card = chosen
            assert lead_card is not None
            winner = trick_winner(lead_card.suit, plays)
            winner.tricks_won_this_round += 1
            leader = next(i for i, pp in enumerate(players) if pp.name == winner.name)

        # Declaration bonus
        for p in players:
            if p.tricks_won_this_round == p.declared_tricks:
                p.vp += DECLARATION_BONUS_VP
                # ピタリ賞: 宣言成功で+1恩寵
                if GRACE_ENABLED:
                    p.grace_points += 1
                # 宣言0成功
                if GRACE_ENABLED and p.declared_tricks == 0:
                    if "WITCH_ZERO_MASTER" in p.witches:
                        choice = _choose_zero_master_reward(p)
                        if choice == "GRACE":
                            p.grace_points += WITCH_ZERO_GRACE
                        elif choice == "GOLD":
                            p.gold += WITCH_ZERO_GOLD
                        elif choice == "VP":
                            p.vp += WITCH_ZERO_VP

        # WITCH_MIRROR: 他プレイヤーの宣言成功時+1金
        others_success_count = sum(1 for p in players if p.tricks_won_this_round == p.declared_tricks)
        for p in players:
            if "WITCH_MIRROR" in p.witches:
                own_success = 1 if p.tricks_won_this_round == p.declared_tricks else 0
                mirror_gold = others_success_count - own_success
                if mirror_gold > 0:
                    p.gold += mirror_gold

        # Grace priority
        grace_priority_d: Set[str] = set()
        if GRACE_ENABLED:
            grace_priority_d = _offer_grace_priority(players, leader_index, None, round_no)

        # Upgrade pick
        ranked = rank_players_for_upgrade(players, leader_index, grace_priority_d)
        for p in ranked:
            choice = choose_upgrade_or_gold(p, revealed, round_no)
            if choice == "GOLD":
                p.gold += TAKE_GOLD_INSTEAD
            else:
                revealed.remove(choice)
                level_up = None
                if choice in ("UP_TRADE", "UP_HUNT", "UP_PRAY", "UP_RITUAL") and p.personal_spots.count(choice) >= 1:
                    level_up = _bot_choose_level_up(p, choice)
                apply_upgrade(p, choice, level_up)

        # 選ばれなかったカードを捨て札に移動（魔女ラウンドは捨てない）
        if revealed and not is_witch_round:
            upgrade_deck.discard_remaining(revealed)

        fourth = ranked[-1]
        choose_4th_place_bonus(fourth, None, round_no)

        # Worker placement（ナショエコ式）
        run_worker_placement_round(players, round_no, leader_index, grace_priority=grace_priority_d)

        # Wage payment with configurable debt penalty
        # 初期ワーカーのみ給料発生（アップグレードワーカーは給料なし）
        for p in players:
            workers_active = p.basic_workers_total
            workers_hired_this_round = p.basic_workers_new_hires

            initial_wage_rate = WAGE_CURVE[round_no]
            # 儀式消費ワーカーも給料対象
            workers_for_wage = workers_active + p.ritual_consumed_this_round
            initial_workers_count = min(INITIAL_WORKERS, workers_for_wage)
            initial_workers_count = max(0, initial_workers_count)

            wage_gross = initial_workers_count * initial_wage_rate

            discount = 0
            if "WITCH_HERD" in p.witches:
                discount += 1

            wage_net = max(0, wage_gross - discount)
            short = max(0, wage_net - p.gold)

            if p.gold >= wage_net:
                p.gold -= wage_net
            else:
                p.gold = 0
                # 負債を累積（ゲーム終了時にペナルティ適用）
                p.accumulated_debt += short
                total_debt_events += 1
                total_debt_amount += short

        # Activate hires
        for p in players:
            if p.basic_workers_new_hires > 0:
                p.basic_workers_total += p.basic_workers_new_hires
                p.basic_workers_new_hires = 0

    # Gold to Grace conversion at end (before grace→VP)
    if GRACE_ENABLED and GOLD_TO_GRACE_RATE > 0:
        for p in players:
            grace_gained = p.gold // GOLD_TO_GRACE_RATE
            if grace_gained > 0:
                p.gold -= grace_gained * GOLD_TO_GRACE_RATE
                p.grace_points += grace_gained

    # Grace bonus at game end (5恩寵毎→3VP)
    if GRACE_ENABLED:
        for p in players:
            grace_bonus = (p.grace_points // GRACE_VP_PER_N) * GRACE_VP_AMOUNT
            p.vp += grace_bonus

    # Gold to VP conversion at end
    for p in players:
        bonus_vp = p.gold // GOLD_TO_VP_RATE
        p.vp += bonus_vp

    # Debt penalty at game end (configurable)
    for p in players:
        if p.accumulated_debt > 0:
            debt_penalty = calculate_debt_penalty_configurable(
                p.accumulated_debt, debt_multiplier, debt_cap, use_tiered
            )
            p.vp -= debt_penalty
            total_debt_penalty += debt_penalty

    # Return results
    players_sorted = sorted(players, key=lambda p: (p.vp, p.gold), reverse=True)
    vps = [p.vp for p in players_sorted]
    return {
        "winner": players_sorted[0].name,
        "vps": vps,
        "winner_vp": vps[0],
        "vp_diff_1st_2nd": vps[0] - vps[1],
        "vp_diff_1st_last": vps[0] - vps[-1],
        "debt_events": total_debt_events,
        "total_debt_amount": total_debt_amount,
        "total_debt_penalty": total_debt_penalty,
    }


def run_debt_penalty_simulation(
    debt_multiplier: int,
    debt_cap: Optional[int],
    use_tiered: bool,
    num_games: int = 100
) -> Dict[str, Any]:
    """Run simulation with specific debt penalty config."""
    results = []
    for game_id in range(num_games):
        seed = game_id * 1000
        result = run_single_game_with_debt_config(
            seed, debt_multiplier, debt_cap, use_tiered
        )
        results.append(result)

    # Calculate statistics
    winner_vps = [r["winner_vp"] for r in results]
    vp_diffs = [r["vp_diff_1st_2nd"] for r in results]
    debt_events = [r["debt_events"] for r in results]
    debt_amounts = [r["total_debt_amount"] for r in results]

    games_with_debt = sum(1 for d in debt_events if d > 0)

    return {
        "debt_multiplier": debt_multiplier,
        "debt_cap": debt_cap,
        "use_tiered": use_tiered,
        "num_games": num_games,
        "avg_winner_vp": sum(winner_vps) / len(winner_vps),
        "avg_vp_diff": sum(vp_diffs) / len(vp_diffs),
        "std_vp_diff": (sum((x - sum(vp_diffs)/len(vp_diffs)) ** 2 for x in vp_diffs) / len(vp_diffs)) ** 0.5,
        "debt_rate": games_with_debt / num_games,
        "avg_debt_events": sum(debt_events) / len(debt_events),
        "avg_debt_amount": sum(debt_amounts) / len(debt_amounts) if sum(debt_amounts) > 0 else 0,
    }


def run_all_debt_penalty_simulations():
    """Run simulations for different debt penalty configurations."""
    print("=== 負債ペナルティ最適化シミュレーション ===")
    print(f"各設定で100ゲーム実行中...\n")

    configs = [
        {"name": "現行(段階式)", "multiplier": 0, "cap": None, "use_tiered": True},
        {"name": "1x無制限", "multiplier": 1, "cap": None, "use_tiered": False},
        {"name": "2x無制限", "multiplier": 2, "cap": None, "use_tiered": False},
        {"name": "3x無制限", "multiplier": 3, "cap": None, "use_tiered": False},
        {"name": "3x上限9", "multiplier": 3, "cap": 9, "use_tiered": False},
        {"name": "3x上限12", "multiplier": 3, "cap": 12, "use_tiered": False},
        {"name": "4x無制限", "multiplier": 4, "cap": None, "use_tiered": False},
        {"name": "5x無制限", "multiplier": 5, "cap": None, "use_tiered": False},
    ]

    results = []
    for cfg in configs:
        print(f"{cfg['name']} をテスト中...", end=" ", flush=True)
        result = run_debt_penalty_simulation(
            cfg["multiplier"], cfg["cap"], cfg["use_tiered"], num_games=100
        )
        result["name"] = cfg["name"]
        results.append(result)
        print(f"完了 (勝者VP: {result['avg_winner_vp']:.1f}, VP差: {result['avg_vp_diff']:.1f}, 負債率: {result['debt_rate']*100:.0f}%)")

    print("\n" + "=" * 90)
    print("=== シミュレーション結果 ===")
    print("=" * 90)
    print(f"{'設定':<14} {'勝者VP':<10} {'1-2位差':<10} {'標準偏差':<10} {'負債率':<10} {'平均負債額':<10}")
    print("-" * 90)

    # Best = lowest VP diff with reasonable debt rate (10-40%)
    viable = [r for r in results if 0.05 <= r["debt_rate"] <= 0.50]
    if viable:
        best = min(viable, key=lambda r: r["avg_vp_diff"])
    else:
        best = min(results, key=lambda r: r["avg_vp_diff"])

    for r in results:
        marker = " ★" if r == best else ""
        cap_str = str(r["debt_cap"]) if r["debt_cap"] else "∞"
        print(f"{r['name']:<14} {r['avg_winner_vp']:<10.1f} {r['avg_vp_diff']:<10.1f} {r['std_vp_diff']:<10.1f} {r['debt_rate']*100:<9.0f}% {r['avg_debt_amount']:<10.1f}{marker}")

    print("-" * 90)
    print(f"\n推奨: {best['name']}")
    print(f"  - 勝者平均VP: {best['avg_winner_vp']:.1f}")
    print(f"  - 1-2位VP差: {best['avg_vp_diff']:.1f}")
    print(f"  - 負債発生率: {best['debt_rate']*100:.0f}%")


# ======= Grace Point Simulation =======

def run_grace_simulation(num_games: int = 100) -> Dict[str, Any]:
    """Run simulation and collect grace system statistics."""
    results = []
    for game_id in range(num_games):
        seed = game_id * 1000
        result = run_single_game_quiet(seed, max_rank=5)
        results.append(result)

    # Aggregate grace statistics
    all_grace_points = []
    all_bonus_vp = []

    for r in results:
        all_grace_points.extend(r.get("grace_points", [0, 0, 0, 0]))
        stats = r.get("grace_stats", {})
        all_bonus_vp.extend(stats.get("bonus_vp", [0, 0, 0, 0]))

    # Calculate VP diff statistics
    vp_diffs = [r["vp_diff_1st_2nd"] for r in results]
    avg_vp_diff = sum(vp_diffs) / len(vp_diffs) if vp_diffs else 0
    std_vp_diff = (sum((x - avg_vp_diff) ** 2 for x in vp_diffs) / len(vp_diffs)) ** 0.5 if vp_diffs else 0

    # Grace statistics
    avg_grace = sum(all_grace_points) / len(all_grace_points) if all_grace_points else 0
    max_grace = max(all_grace_points) if all_grace_points else 0
    min_grace = min(all_grace_points) if all_grace_points else 0
    total_players = len(all_grace_points)

    # Bonus VP statistics
    avg_bonus_vp = sum(all_bonus_vp) / len(all_bonus_vp) if all_bonus_vp else 0
    players_with_bonus = sum(1 for b in all_bonus_vp if b > 0)

    return {
        "num_games": num_games,
        "avg_vp_diff": avg_vp_diff,
        "std_vp_diff": std_vp_diff,
        "avg_grace_points": avg_grace,
        "max_grace_points": max_grace,
        "min_grace_points": min_grace,
        "avg_bonus_vp": avg_bonus_vp,
        "bonus_rate": players_with_bonus / total_players if total_players > 0 else 0,
    }


def run_gold_to_grace_simulation(num_games: int = 500):
    """金→恩寵変換レートの最適値をシミュレーションで算出する。"""
    print("=== 金→恩寵変換レート シミュレーション ===")
    print(f"{num_games}ゲーム × 各レート 実行中...\n")

    # テストするレート: 0(変換なし), 1(1金=1恩寵), 2(2金=1恩寵), 3(3金=1恩寵), 4, 5
    rates = [0, 1, 2, 3, 4, 5]

    print(f"{'レート':>6} {'平均VP差':>10} {'VP差σ':>8} {'平均恩寵':>10} {'恩寵ボーナス率':>14} {'平均変換恩寵':>12} {'1位VP':>8} {'4位VP':>8} {'VP幅':>8}")
    print("-" * 100)

    all_results = {}
    for rate in rates:
        results = []
        for game_id in range(num_games):
            seed = game_id * 1000
            result = run_single_game_quiet(seed, max_rank=5, gold_to_grace_rate=rate)
            results.append(result)

        # Aggregate
        vp_diffs = [r["vp_diff_1st_2nd"] for r in results]
        vp_diffs_last = [r["vp_diff_1st_last"] for r in results]
        avg_vp_diff = sum(vp_diffs) / len(vp_diffs)
        std_vp_diff = (sum((x - avg_vp_diff) ** 2 for x in vp_diffs) / len(vp_diffs)) ** 0.5

        all_grace = []
        all_bonus_vp = []
        all_converted = []
        all_1st_vp = []
        all_4th_vp = []
        for r in results:
            all_grace.extend(r.get("grace_points", [0, 0, 0, 0]))
            stats = r.get("grace_stats", {})
            all_bonus_vp.extend(stats.get("bonus_vp", [0, 0, 0, 0]))
            all_converted.extend(r.get("gold_converted_to_grace", [0, 0, 0, 0]))
            all_1st_vp.append(r["vps"][0])
            all_4th_vp.append(r["vps"][-1])

        avg_grace = sum(all_grace) / len(all_grace)
        bonus_rate = sum(1 for b in all_bonus_vp if b > 0) / len(all_bonus_vp) if all_bonus_vp else 0
        avg_converted = sum(all_converted) / len(all_converted) if all_converted else 0
        avg_1st = sum(all_1st_vp) / len(all_1st_vp)
        avg_4th = sum(all_4th_vp) / len(all_4th_vp)
        vp_spread = avg_1st - avg_4th

        label = "変換なし" if rate == 0 else f"{rate}金=1恩寵"
        print(f"{label:>6} {avg_vp_diff:>10.2f} {std_vp_diff:>8.2f} {avg_grace:>10.2f} {bonus_rate:>13.1%} {avg_converted:>12.2f} {avg_1st:>8.2f} {avg_4th:>8.2f} {vp_spread:>8.2f}")

        all_results[rate] = {
            "avg_vp_diff_1st_2nd": avg_vp_diff,
            "std_vp_diff": std_vp_diff,
            "avg_grace": avg_grace,
            "bonus_rate": bonus_rate,
            "avg_converted": avg_converted,
            "avg_1st_vp": avg_1st,
            "avg_4th_vp": avg_4th,
            "vp_spread": vp_spread,
        }

    # 推奨レートの選定
    print("\n" + "=" * 100)
    print("【分析】")
    print("- VP差(1-2位)が小さいほど接戦 = バランス良好")
    print("- VP幅(1-4位)が適度に広い = 実力差が反映される")
    print("- 恩寵ボーナス獲得率が高すぎると恩寵インフレ")
    print("- 変換なし(0)との比較で改善度を確認")

    return all_results


def run_shared_spots_simulation(num_games: int = 500):
    """共有スポット方式のシミュレーション（検証済み・所有者収入方式を採用）。
    ※ 現在は共有スポット＋所有者収入方式が本番実装済み。このシミュレーションは参考用。
    """
    print("=== 共有スポット方式 シミュレーション ===")
    print(f"{num_games}ゲーム × 各モード 実行中...\n")

    modes = [
        ("personal",     "現行（個人スポット）"),
        ("shared_bonus", "共有＋所有者ボーナス（自分使用時+1効果）"),
        ("shared_income", "共有＋所有者収入（他人使用時+1金）"),
        ("shared_cost",  "共有＋使用コスト（他人使用時1金支払い→所有者）"),
    ]

    print(f"{'モード':<20} {'平均VP差':>8} {'VP差σ':>7} {'VP幅':>7} {'1位VP':>7} {'4位VP':>7} {'平均WP数':>8} {'平均金':>7} {'平均恩寵':>8}")
    print("-" * 100)

    for mode_id, mode_name in modes:
        results = []
        for game_id in range(num_games):
            seed = game_id * 1000
            result = _run_shared_spots_game(seed, mode_id)
            results.append(result)

        vp_diffs = [r["vp_diff_1st_2nd"] for r in results]
        vp_spreads = [r["vp_spread"] for r in results]
        avg_vp_diff = sum(vp_diffs) / len(vp_diffs)
        std_vp_diff = (sum((x - avg_vp_diff) ** 2 for x in vp_diffs) / len(vp_diffs)) ** 0.5
        avg_spread = sum(vp_spreads) / len(vp_spreads)
        avg_1st = sum(r["vps"][0] for r in results) / len(results)
        avg_4th = sum(r["vps"][-1] for r in results) / len(results)
        avg_wp = sum(r["avg_wp_actions"] for r in results) / len(results)
        avg_gold = sum(r["avg_end_gold"] for r in results) / len(results)
        avg_grace = sum(r["avg_end_grace"] for r in results) / len(results)

        print(f"{mode_name:<20} {avg_vp_diff:>8.2f} {std_vp_diff:>7.2f} {avg_spread:>7.2f} {avg_1st:>7.2f} {avg_4th:>7.2f} {avg_wp:>8.2f} {avg_gold:>7.2f} {avg_grace:>8.2f}")

    print("\n" + "=" * 100)
    print("【分析】")
    print("- VP差(1-2位)が小さいほど接戦 = バランス良好")
    print("- VP幅(1-4位)が適度: 狭すぎると実力差が出ない、広すぎると一方的")
    print("- 平均WP数: ワーカー配置のアクション数（多いほどスポットが活用されている）")
    print("- 所有者ボーナス: 自分使用時に効果+1（建設者メリット大）")
    print("- 所有者収入: 他人使用時に所有者+1金（ナショエコ方式、間接収入）")
    print("- 使用コスト: 他人使用時に1金支払い→所有者（使用者にコスト）")


@dataclass
class SharedSpot:
    """共有スポットの情報"""
    spot_type: str       # UP_TRADE, UP_HUNT, etc.
    owner: str           # 設置したプレイヤー名
    level: int = 1       # 1 or 2
    used_this_round: bool = False


@dataclass
class SharedPlacementState:
    """共有スポット方式のワーカー配置状態"""
    shared_trade_taken: bool = False
    shared_hunt_taken: bool = False
    shared_pray_taken: bool = False
    shared_spots: List[SharedSpot] = field(default_factory=list)
    shared_spots_used: Set[int] = field(default_factory=set)  # 使用済みスポットindex
    workers_remaining: Dict[str, int] = field(default_factory=dict)


def _get_shared_available_actions(
    player: Player, sps: SharedPlacementState, mode: str
) -> List[str]:
    """共有スポット方式で利用可能なアクション一覧"""
    available: List[str] = []

    if not sps.shared_trade_taken:
        available.append("TRADE")
    if not sps.shared_hunt_taken:
        available.append("HUNT")
    if GRACE_ENABLED and not sps.shared_pray_taken:
        available.append("PRAY")

    total_workers = player.basic_workers_total + player.basic_workers_new_hires
    if total_workers < MAX_WORKERS and player.gold >= RECRUIT_COST:
        available.append("RECRUIT")

    # 共有スポット: 全プレイヤーが使用可能
    for idx, spot in enumerate(sps.shared_spots):
        if idx in sps.shared_spots_used:
            continue
        # コストチェック
        if spot.spot_type == "WITCH_NEGOTIATE" and player.grace_points < WITCH_NEGOTIATE_GRACE_COST:
            continue
        # 共有コストモード: 他人のスポット使用にはコストが必要
        if mode == "shared_cost" and spot.owner != player.name:
            if player.gold < 1:
                continue
        available.append(f"SHARED:{idx}:{spot.spot_type}:{spot.owner}")

    return available


def _resolve_shared_action(
    player: Player, action: str, sps: SharedPlacementState,
    mode: str, players_by_name: Dict[str, 'Player']
) -> Dict[str, Any]:
    """共有スポット方式のアクション解決"""
    result: Dict[str, Any] = {"action": action, "effects": []}

    if action == "TRADE":
        player.gold += SHARED_TRADE_GOLD
        sps.shared_trade_taken = True
        result["effects"].append(f"+{SHARED_TRADE_GOLD}金")
    elif action == "HUNT":
        player.vp += SHARED_HUNT_VP
        sps.shared_hunt_taken = True
        result["effects"].append(f"+{SHARED_HUNT_VP}VP")
    elif action == "PRAY":
        player.grace_points += SHARED_PRAY_GRACE
        sps.shared_pray_taken = True
        result["effects"].append(f"+{SHARED_PRAY_GRACE}恩寵")
    elif action == "RECRUIT":
        player.gold -= RECRUIT_COST
        player.basic_workers_new_hires += 1
        result["effects"].append(f"-{RECRUIT_COST}金, +1人(次R)")
    elif action.startswith("SHARED:"):
        parts = action.split(":", 3)
        idx = int(parts[1])
        spot_type = parts[2]
        owner_name = parts[3]
        sps.shared_spots_used.add(idx)

        spot = sps.shared_spots[idx]
        is_owner = (player.name == owner_name)
        level = spot.level

        # 所有者ボーナスモード: 自分のスポット使用時+1
        owner_bonus = 0
        if mode == "shared_bonus" and is_owner:
            owner_bonus = 1

        # 使用コスト/収入モード
        if not is_owner:
            if mode == "shared_cost":
                player.gold -= 1
                players_by_name[owner_name].gold += 1
                result["effects"].append(f"-1金(使用料→{owner_name})")
            elif mode == "shared_income":
                players_by_name[owner_name].gold += 1
                result["effects"].append(f"({owner_name}+1金収入)")

        # 効果解決
        if spot_type == "UP_TRADE":
            gold = PERSONAL_TRADE_GOLD + (level - 1) + owner_bonus
            if "WITCH_BLACKROAD" in player.witches:
                gold += 1
            player.gold += gold
            result["effects"].append(f"+{gold}金")
        elif spot_type == "UP_HUNT":
            vp = PERSONAL_HUNT_VP + (level - 1) + owner_bonus
            if "WITCH_BLOODHUNT" in player.witches:
                vp += 1
            player.vp += vp
            result["effects"].append(f"+{vp}VP")
        elif spot_type == "UP_PRAY":
            grace = PERSONAL_PRAY_GRACE + (level - 1) + owner_bonus
            player.grace_points += grace
            result["effects"].append(f"+{grace}恩寵")
        elif spot_type == "UP_RITUAL":
            grace_amount = PERSONAL_RITUAL_GRACE + (level - 1) + owner_bonus
            gold_amount = PERSONAL_RITUAL_GOLD + (level - 1) + owner_bonus
            choice = _choose_ritual_reward(player, grace_amount, gold_amount)
            if choice == "grace":
                player.grace_points += grace_amount
                result["effects"].append(f"+{grace_amount}恩寵")
            else:
                player.gold += gold_amount
                result["effects"].append(f"+{gold_amount}金")
            player.basic_workers_total -= 1
            player.ritual_consumed_this_round += 1
            result["effects"].append("ワーカー-1")
        elif spot_type == "WITCH_NEGOTIATE":
            player.grace_points -= WITCH_NEGOTIATE_GRACE_COST
            player.gold += WITCH_NEGOTIATE_GOLD
            result["effects"].append(f"-{WITCH_NEGOTIATE_GRACE_COST}恩寵, +{WITCH_NEGOTIATE_GOLD}金")

    return result


def _bot_choose_shared_action(
    player: Player, available: List[str], sps: SharedPlacementState,
    round_no: int, mode: str
) -> str:
    """共有スポット方式のBot AI"""
    if not available:
        return "PASS"

    strat = STRATEGIES.get(player.strategy, STRATEGIES['BALANCED'])
    expected_wage = calc_expected_wage(player, round_no)
    gold_deficit = max(0, expected_wage - player.gold)
    grace_awareness = strat.get('grace_awareness', 0.5)

    scores: List[Tuple[float, str]] = []
    for action in available:
        score = 50.0
        is_shared = action.startswith("SHARED:")
        spot_type = ""
        is_own_spot = False
        if is_shared:
            parts = action.split(":", 3)
            spot_type = parts[2]
            is_own_spot = (parts[3] == player.name)

        if action == "TRADE" or (is_shared and spot_type == "UP_TRADE"):
            score += 20
            if gold_deficit > 0:
                score += 35
            if strat.get('prefer_gold', False):
                score += 15
            if action == "TRADE":
                score += 5
            # 所有者ボーナスの場合、自分のスポットを優先
            if is_shared and is_own_spot and mode == "shared_bonus":
                score += 10
            # コストモードでは他人のスポット使用にペナルティ
            if is_shared and not is_own_spot and mode == "shared_cost":
                score -= 8
        elif action == "HUNT" or (is_shared and spot_type == "UP_HUNT"):
            score += 15
            score += strat['hunt_ratio'] * 40
            if action == "HUNT":
                score += 5
            if is_shared and is_own_spot and mode == "shared_bonus":
                score += 10
            if is_shared and not is_own_spot and mode == "shared_cost":
                score -= 8
        elif action == "PRAY" or (is_shared and spot_type == "UP_PRAY"):
            score += grace_awareness * 25
            if action == "PRAY":
                score += 5
            if is_shared and is_own_spot and mode == "shared_bonus":
                score += 8
        elif is_shared and spot_type == "WITCH_NEGOTIATE":
            if gold_deficit > 0:
                score += 35
            else:
                score += 10
        elif is_shared and spot_type == "UP_RITUAL":
            if player.basic_workers_total <= 2:
                score -= 30
            else:
                score += 25
                if gold_deficit > 0:
                    score += 15
        elif action == "RECRUIT":
            total_spots = len(sps.shared_spots) + 3
            if (round_no < 3 and player.basic_workers_total < strat.get('max_workers', 4)
                    and player.basic_workers_total < total_spots
                    and player.gold >= RECRUIT_COST + expected_wage):
                score += 15
            else:
                score += 2

        score += player.rng.random() * 10
        scores.append((score, action))

    scores.sort(key=lambda x: -x[0])
    return scores[0][1]


def _run_shared_spots_game(seed: int, mode: str) -> Dict[str, Any]:
    """共有スポット方式で1ゲームを実行する。mode: personal/shared_bonus/shared_income/shared_cost"""
    rng = random.Random(seed)
    bot_rng = random.Random(seed + 100)
    players = [
        Player("P1", is_bot=True, rng=random.Random(seed + 1), strategy=assign_random_strategy(bot_rng)),
        Player("P2", is_bot=True, rng=random.Random(seed + 2), strategy=assign_random_strategy(bot_rng)),
        Player("P3", is_bot=True, rng=random.Random(seed + 3), strategy=assign_random_strategy(bot_rng)),
        Player("P4", is_bot=True, rng=random.Random(seed + 4), strategy=assign_random_strategy(bot_rng)),
    ]
    for p in players:
        p.sets = []
    players_by_name = {p.name: p for p in players}

    upgrade_deck = UpgradeDeck(rng)
    witch_pool: List[str] = []
    for w in ALL_WITCHES:
        witch_pool.extend([w] * WITCH_POOL_COUNTS.get(w, 1))
    rng.shuffle(witch_pool)

    # 共有スポットボード（全ラウンド通して蓄積）
    shared_board: List[SharedSpot] = []

    total_wp_actions = 0

    for round_no in range(ROUNDS):
        _, _ = deal_round_cards(players, round_no, rng, None)

        is_witch_round = (round_no == WITCH_ROUND)
        if is_witch_round:
            revealed = witch_pool[:REVEAL_UPGRADES]
            witch_pool = witch_pool[REVEAL_UPGRADES:]
        else:
            revealed = upgrade_deck.reveal(REVEAL_UPGRADES)

        set_index = round_no % SETS_PER_GAME
        leader_index = round_no % len(players)

        for p in players:
            p.tricks_won_this_round = 0
            p.ritual_consumed_this_round = 0

        # Declaration
        full_hands = {p.name: p.sets[set_index][:] for p in players}
        for p in players:
            p.declared_tricks = declare_tricks(p, full_hands[p.name][:], set_index)

        # Seal
        playable_hands = {}
        for p in players:
            hand = full_hands[p.name]
            seal_cards(p, hand, set_index)
            playable_hands[p.name] = hand[:]

        # Play tricks
        leader = leader_index
        for trick_idx in range(TRICKS_PER_ROUND):
            plays_t: List[Tuple[Player, Card]] = []
            lead_card: Optional[Card] = None
            for offset in range(len(players)):
                idx = (leader + offset) % len(players)
                pl = players[idx]
                hand = playable_hands[pl.name]
                chosen = choose_card(pl, lead_card, hand)
                hand.remove(chosen)
                plays_t.append((pl, chosen))
                if lead_card is None:
                    lead_card = chosen
            assert lead_card is not None
            winner = trick_winner(lead_card.suit, plays_t)
            winner.tricks_won_this_round += 1
            leader = next(i for i, pp in enumerate(players) if pp.name == winner.name)

        # Declaration bonus
        for p in players:
            if p.tricks_won_this_round == p.declared_tricks:
                p.vp += DECLARATION_BONUS_VP
                if GRACE_ENABLED:
                    p.grace_points += 1
                if GRACE_ENABLED and p.declared_tricks == 0:
                    if "WITCH_ZERO_MASTER" in p.witches:
                        choice = _choose_zero_master_reward(p)
                        if choice == "GRACE":
                            p.grace_points += WITCH_ZERO_GRACE
                        elif choice == "GOLD":
                            p.gold += WITCH_ZERO_GOLD
                        elif choice == "VP":
                            p.vp += WITCH_ZERO_VP

        # WITCH_MIRROR
        others_success_count = sum(1 for p in players if p.tricks_won_this_round == p.declared_tricks)
        for p in players:
            if "WITCH_MIRROR" in p.witches:
                own_success = 1 if p.tricks_won_this_round == p.declared_tricks else 0
                mirror_gold = others_success_count - own_success
                if mirror_gold > 0:
                    p.gold += mirror_gold

        # 0トリックボーナス（恩寵+金貨）
        if GRACE_ENABLED:
            for p in players:
                if p.tricks_won_this_round == 0:
                    p.grace_points += GRACE_ZERO_TRICKS_BONUS
                    p.gold += ZERO_TRICKS_GOLD_BONUS
                    self._log(f"0勝ボーナス: {p.name} +{GRACE_ZERO_TRICKS_BONUS}恩寵, +{ZERO_TRICKS_GOLD_BONUS}金")

        # Grace priority
        grace_priority: Set[str] = set()
        if GRACE_ENABLED:
            grace_priority = _offer_grace_priority(players, leader_index, None, round_no)

        # Upgrade pick
        ranked = rank_players_for_upgrade(players, leader_index, grace_priority)

        if mode == "personal":
            # 現行方式: 個人スポットとして獲得
            for p in ranked:
                choice = choose_upgrade_or_gold(p, revealed, round_no)
                if choice == "GOLD":
                    p.gold += TAKE_GOLD_INSTEAD
                else:
                    revealed.remove(choice)
                    level_up = None
                    if choice in ("UP_TRADE", "UP_HUNT", "UP_PRAY", "UP_RITUAL") and p.personal_spots.count(choice) >= 1:
                        level_up = _bot_choose_level_up(p, choice)
                    apply_upgrade(p, choice, level_up)
        else:
            # 共有スポット方式: アップグレードを共有ボードに配置
            for p in ranked:
                available_upgrades = [u for u in revealed if u not in ("WITCH_BLACKROAD", "WITCH_BLOODHUNT",
                                      "WITCH_HERD", "WITCH_BLESSING", "WITCH_MIRROR", "WITCH_ZERO_MASTER")]
                # 魔女カードはパッシブなので従来通り個人取得
                witch_choices = [u for u in revealed if u.startswith("WITCH_") and u not in available_upgrades]

                choice = choose_upgrade_or_gold(p, revealed, round_no)
                if choice == "GOLD":
                    p.gold += TAKE_GOLD_INSTEAD
                elif choice.startswith("WITCH_") and choice != "WITCH_NEGOTIATE":
                    # パッシブ魔女は個人取得
                    revealed.remove(choice)
                    apply_upgrade(p, choice, None)
                else:
                    # アクション系カード（UP_*, WITCH_NEGOTIATE）は共有ボードに配置
                    revealed.remove(choice)
                    # 既存の同種スポットをLv2にするか、新規追加か
                    existing = [i for i, s in enumerate(shared_board)
                                if s.spot_type == choice and s.owner == p.name and s.level == 1]
                    if existing and choice in ("UP_TRADE", "UP_HUNT", "UP_PRAY", "UP_RITUAL"):
                        # Lv2化
                        shared_board[existing[0]].level = 2
                    else:
                        shared_board.append(SharedSpot(spot_type=choice, owner=p.name))

        if revealed and not is_witch_round:
            upgrade_deck.discard_remaining(revealed)

        fourth = ranked[-1]
        choose_4th_place_bonus(fourth, None, round_no)

        # Worker placement
        if mode == "personal":
            run_worker_placement_round(players, round_no, leader_index, grace_priority=grace_priority)
            for p in players:
                total_wp_actions += p.basic_workers_total
        else:
            # 共有スポット方式のワーカー配置
            sps = SharedPlacementState()
            sps.shared_spots = shared_board
            sps.shared_spots_used = set()
            order = determine_placement_order(players, leader_index, grace_priority)
            for p in players:
                sps.workers_remaining[p.name] = p.basic_workers_total

            while any(sps.workers_remaining[p.name] > 0 for p in order):
                for p in order:
                    if sps.workers_remaining[p.name] <= 0:
                        continue
                    avail = _get_shared_available_actions(p, sps, mode)
                    if not avail:
                        sps.workers_remaining[p.name] = 0
                        continue
                    action = _bot_choose_shared_action(p, avail, sps, round_no, mode)
                    if action == "PASS":
                        sps.workers_remaining[p.name] = 0
                        continue
                    _resolve_shared_action(p, action, sps, mode, players_by_name)
                    sps.workers_remaining[p.name] -= 1
                    total_wp_actions += 1

            # ラウンド終了: 共有スポットの使用状態をリセット
            for spot in shared_board:
                spot.used_this_round = False

        # Wage payment
        for p in players:
            pay_wages_and_debt(p, round_no)

        # Activate hires
        for p in players:
            if p.basic_workers_new_hires > 0:
                p.basic_workers_total += p.basic_workers_new_hires
                p.basic_workers_new_hires = 0

    # End-game scoring
    if GRACE_ENABLED and GOLD_TO_GRACE_RATE > 0:
        for p in players:
            grace_gained = p.gold // GOLD_TO_GRACE_RATE
            if grace_gained > 0:
                p.gold -= grace_gained * GOLD_TO_GRACE_RATE
                p.grace_points += grace_gained

    if GRACE_ENABLED:
        for p in players:
            grace_bonus = (p.grace_points // GRACE_VP_PER_N) * GRACE_VP_AMOUNT
            p.vp += grace_bonus

    for p in players:
        bonus_vp = p.gold // GOLD_TO_VP_RATE
        p.vp += bonus_vp

    for p in players:
        if p.accumulated_debt > 0:
            penalty = calculate_debt_penalty(p.accumulated_debt)
            p.vp -= penalty

    players_sorted = sorted(players, key=lambda p: (p.vp, p.gold), reverse=True)
    vps = [p.vp for p in players_sorted]

    return {
        "vps": vps,
        "vp_diff_1st_2nd": vps[0] - vps[1],
        "vp_spread": vps[0] - vps[-1],
        "avg_wp_actions": total_wp_actions / len(players),
        "avg_end_gold": sum(p.gold for p in players) / len(players),
        "avg_end_grace": sum(p.grace_points for p in players) / len(players),
    }


def run_witch_simulation(num_games: int = 1000) -> Dict[str, Any]:
    """Run simulation and collect witch balance statistics."""
    # Track stats per witch
    witch_names = {
        "WITCH_BLACKROAD": "《黒路の魔女》",
        "WITCH_BLOODHUNT": "《血誓の討伐官》",
        "WITCH_HERD": "《群導の魔女》",
        "WITCH_NEGOTIATE": "《交渉の魔女》",
        "WITCH_BLESSING": "《祈祷の魔女》",
        "WITCH_MIRROR": "《鏡の魔女》",
        "WITCH_ZERO_MASTER": "《慎重な予言者》",
    }

    # Initialize stats: for each witch, track VP totals, win count, ownership count
    witch_data: Dict[str, Dict[str, Any]] = {}
    for witch_id in witch_names:
        witch_data[witch_id] = {
            "name": witch_names[witch_id],
            "total_vp": 0,
            "count": 0,
            "wins": 0,
            "rank_sum": 0,
        }

    # Also track players without any witch
    no_witch_data = {
        "total_vp": 0,
        "count": 0,
        "wins": 0,
        "rank_sum": 0,
    }

    # Run games
    for game_id in range(num_games):
        seed = game_id * 1000 + 999
        result = run_single_game_quiet(seed, max_rank=5)

        for player_stat in result["witch_stats"]:
            rank = player_stat["rank"]
            vp = player_stat["vp"]
            witches = player_stat["witches"]

            if len(witches) == 0:
                no_witch_data["total_vp"] += vp
                no_witch_data["count"] += 1
                no_witch_data["rank_sum"] += rank
                if rank == 1:
                    no_witch_data["wins"] += 1
            else:
                for w in witches:
                    if w in witch_data:
                        witch_data[w]["total_vp"] += vp
                        witch_data[w]["count"] += 1
                        witch_data[w]["rank_sum"] += rank
                        if rank == 1:
                            witch_data[w]["wins"] += 1

    return {
        "num_games": num_games,
        "witch_data": witch_data,
        "no_witch_data": no_witch_data,
    }


def run_all_witch_simulations(num_games: int = 1000):
    """Run witch balance simulation and print results."""
    print("=== 魔女バランスシミュレーション ===")
    print(f"{num_games}ゲーム実行中...\n")

    result = run_witch_simulation(num_games=num_games)

    print("=" * 70)
    print("=== シミュレーション結果 ===")
    print("=" * 70)

    print("\n【魔女別統計】")
    print("-" * 70)
    print(f"{'魔女名':<20} {'平均VP':>8} {'勝率':>8} {'平均順位':>8} {'所持数':>8}")
    print("-" * 70)

    witch_data = result["witch_data"]
    no_witch = result["no_witch_data"]

    # Sort by average VP descending
    sorted_witches = sorted(
        witch_data.items(),
        key=lambda x: x[1]["total_vp"] / x[1]["count"] if x[1]["count"] > 0 else 0,
        reverse=True
    )

    for witch_id, data in sorted_witches:
        if data["count"] > 0:
            avg_vp = data["total_vp"] / data["count"]
            win_rate = data["wins"] / data["count"] * 100
            avg_rank = data["rank_sum"] / data["count"]
            print(f"{data['name']:<20} {avg_vp:>8.1f} {win_rate:>7.1f}% {avg_rank:>8.2f} {data['count']:>8}")

    # No witch stats
    if no_witch["count"] > 0:
        avg_vp = no_witch["total_vp"] / no_witch["count"]
        win_rate = no_witch["wins"] / no_witch["count"] * 100
        avg_rank = no_witch["rank_sum"] / no_witch["count"]
        print("-" * 70)
        print(f"{'（魔女なし）':<20} {avg_vp:>8.1f} {win_rate:>7.1f}% {avg_rank:>8.2f} {no_witch['count']:>8}")

    print("-" * 70)

    # Balance evaluation
    print("\n【バランス評価】")

    # Calculate overall stats
    all_avg_vp = []
    for witch_id, data in witch_data.items():
        if data["count"] > 0:
            all_avg_vp.append(data["total_vp"] / data["count"])

    if all_avg_vp:
        overall_avg = sum(all_avg_vp) / len(all_avg_vp)
        vp_range = max(all_avg_vp) - min(all_avg_vp)

        print(f"  魔女間VP差: {vp_range:.1f}VP (平均: {overall_avg:.1f}VP)")

        if vp_range <= 3:
            print("  ✓ 魔女間のバランスは良好です（VP差3以下）")
        elif vp_range <= 5:
            print("  △ 魔女間にやや差があります（VP差3-5）")
        else:
            print("  ⚠️ 魔女間のバランスに問題があります（VP差5超）")

        # Check if any witch is too strong or too weak
        for witch_id, data in witch_data.items():
            if data["count"] > 0:
                avg = data["total_vp"] / data["count"]
                if avg > overall_avg + 3:
                    print(f"  ⚠️ {data['name']}が強すぎる可能性 (+{avg - overall_avg:.1f}VP)")
                elif avg < overall_avg - 3:
                    print(f"  ⚠️ {data['name']}が弱すぎる可能性 ({avg - overall_avg:.1f}VP)")

    print("\n" + "=" * 70)


def run_all_grace_simulations(num_games: int = 1000):
    """Run grace point system analysis simulation."""
    print("=== 恩寵ポイントシステム分析シミュレーション ===")
    print(f"{num_games}ゲーム実行中...\n")

    result = run_grace_simulation(num_games=num_games)

    print("=" * 60)
    print("=== シミュレーション結果 ===")
    print("=" * 60)

    print(f"\n【VP差統計】")
    print(f"  1-2位平均VP差: {result['avg_vp_diff']:.2f}")
    print(f"  標準偏差: {result['std_vp_diff']:.2f}")

    print(f"\n【恩寵ポイント統計】")
    print(f"  平均恩寵ポイント: {result['avg_grace_points']:.2f}")
    print(f"  最小: {result['min_grace_points']}")
    print(f"  最大: {result['max_grace_points']}")

    print(f"\n【恩寵ボーナス統計】（{GRACE_VP_PER_N}恩寵毎→{GRACE_VP_AMOUNT}VP）")
    print(f"  ボーナス獲得率: {result['bonus_rate']*100:.1f}%")
    print(f"  平均ボーナスVP: {result['avg_bonus_vp']:.2f}")

    print("\n" + "=" * 60)

    # バランス評価
    print("\n【バランス評価】")
    if result['avg_grace_points'] < 3:
        print("  ⚠️ 恩寵獲得量が少なすぎます（平均3点未満）")
        print("     → 獲得手段を増やすか、獲得量を上げることを検討")
    elif result['avg_grace_points'] > 20:
        print("  ⚠️ 恩寵獲得量が多すぎます（平均20点超）")
        print("     → 獲得量を調整することを検討")
    else:
        print("  ✓ 恩寵獲得量は適正範囲内です")

    avg_bonus = result['avg_bonus_vp']
    if avg_bonus < 1:
        print("  ⚠️ 恩寵ボーナスVPが少なすぎます（平均1VP未満）")
    elif avg_bonus > 9:
        print("  ⚠️ 恩寵ボーナスVPが多すぎます（平均9VP超）")
    else:
        print("  ✓ 恩寵ボーナスバランスは適正範囲内です")


def run_auto_game(seed: int = 42, ai_bot: bool = False) -> dict:
    """Run a fully automated game with 4 bots for CI testing.

    Returns a dict with game results for verification.
    """
    bot_type = "AI (Haiku)" if ai_bot else "ルールベース"
    print(f"=== 自動実行モード (seed={seed}, Bot: {bot_type}) ===")
    print("4体のBotでゲームを自動実行します\n")

    engine = GameEngine(seed=seed, all_bots=True)

    # Enable AI for all bots if requested
    if ai_bot:
        for p in engine.players:
            p.ai_bot = True

    # Run until game ends
    while engine.step():
        pass

    state = engine.get_state()

    # Print results
    print("\n=== ゲーム終了 ===")
    print(f"ラウンド数: {engine.config.rounds}")
    print("\n最終結果:")

    sorted_players = sorted(
        state["players"],
        key=lambda p: (p["vp"], p["gold"]),
        reverse=True
    )

    for i, p in enumerate(sorted_players, start=1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "  ")
        grace_str = f"  恩寵: {p.get('grace_points', 0)}" if GRACE_ENABLED else ""
        debt_str = f"  負債: {p.get('accumulated_debt', 0)}" if p.get('accumulated_debt', 0) > 0 else ""
        print(f"{medal} {i}位 {p['name']}: {p['vp']}VP, {p['gold']}G{grace_str}{debt_str}")

    print("\n✅ ゲームが正常に完了しました")

    return {
        "success": True,
        "rounds": engine.config.rounds,
        "players": sorted_players,
        "winner": sorted_players[0]["name"],
        "winner_vp": sorted_players[0]["vp"],
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="魔女協会 Card Game")
    parser.add_argument("--simulate", action="store_true", help="Run rank optimization simulation")
    parser.add_argument("--simulate-deck", action="store_true", help="Run deck/trump count optimization simulation")
    parser.add_argument("--simulate-debt-penalty", action="store_true", help="Run debt penalty optimization simulation")
    parser.add_argument("--simulate-grace", action="store_true", help="Run grace point system simulation")
    parser.add_argument("--simulate-witch", action="store_true", help="Run witch balance simulation")
    parser.add_argument("--simulate-gold-grace", action="store_true", help="Run gold-to-grace conversion rate simulation")
    parser.add_argument("--simulate-shared-spots", action="store_true", help="Run shared spots vs personal spots simulation")
    parser.add_argument("--auto", action="store_true", help="Run automated game with 4 bots (for CI testing)")
    parser.add_argument("--ai-bot", action="store_true", help="Use AI (Anthropic Haiku) for bot decisions")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for --auto mode")
    parser.add_argument("--rich-ui", action="store_true", help="Run Rich UI server (browser-based)")
    parser.add_argument("--port", type=int, default=8080, help="Port for Rich UI server")
    args = parser.parse_args()

    try:
        if args.simulate:
            run_all_simulations()
        elif args.simulate_deck:
            run_all_deck_simulations()
        elif args.simulate_debt_penalty:
            run_all_debt_penalty_simulations()
        elif args.simulate_grace:
            run_all_grace_simulations()
        elif args.simulate_witch:
            run_all_witch_simulations()
        elif args.simulate_gold_grace:
            run_gold_to_grace_simulation()
        elif args.simulate_shared_spots:
            run_shared_spots_simulation()
        elif args.auto:
            result = run_auto_game(seed=args.seed, ai_bot=args.ai_bot)
            sys.exit(0 if result["success"] else 1)
        elif args.rich_ui:
            from rich_ui_server import run_server
            print(f"Starting Rich UI server on port {args.port}...")
            print(f"Open http://127.0.0.1:{args.port} in your browser")
            run_server(host="127.0.0.1", port=args.port)
        else:
            main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
