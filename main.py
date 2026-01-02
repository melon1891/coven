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
- Incremental action upgrades (UP_TRADE / UP_HUNT => level +1 up to 2)
- Hiring: hires do NOT act this round, BUT wage IS paid starting this round
- JSONL logging to game_log.jsonl
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
import random
import sys
import json
from datetime import datetime

# ======= Core Config =======
SUITS = ["Spade", "Heart", "Diamond", "Club"]

ROUNDS = 4
TRICKS_PER_ROUND = 4               # play 4 tricks
CARDS_PER_SET = 6                  # but see 6 cards, seal 2, play 4
SETS_PER_GAME = 4
REVEAL_UPGRADES = 5                # players + 1 (for 4p => 5)

START_GOLD = 7
WAGE_CURVE = [1, 1, 2, 2]  # 初期ワーカーの給料（R4緩和: 3→2）
UPGRADED_WAGE_CURVE = [1, 2, 3, 4]  # 雇用したワーカーの給料（全体緩和）
INITIAL_WORKERS = 2  # 初期ワーカー数
RESCUE_GOLD_FOR_4TH = 2
TAKE_GOLD_INSTEAD = 2
DECLARATION_BONUS_VP = 1  # 宣言成功ボーナス（失敗ペナルティなし）

# === 金貨→VP変換 ===
GOLD_TO_VP_RATE = 2  # ゲーム終了時、2金貨 = 1VP に変換

# === 負債ペナルティ設定 ===
# 給与未払い1金につき何VPを失うか（2 = 1金不足で-2VP）
DEBT_PENALTY_MULTIPLIER = 2
# ペナルティ上限（None = 無制限）
DEBT_PENALTY_CAP: Optional[int] = None

ACTIONS = ["TRADE", "HUNT", "RECRUIT"]

# === CPU性格定義 ===
STRATEGIES = {
    'CONSERVATIVE': {
        'name': '堅実',
        'name_en': 'Kenjitsu',
        'desc': '安全プレイ、金貨優先',
        'max_workers': 2,
        'prefer_gold': True,
        'hunt_ratio': 0.2,
        'accept_debt': 0,
    },
    'VP_AGGRESSIVE': {
        'name': 'VPつっぱ',
        'name_en': 'VP Toppa',
        'desc': 'ワーカー最大化、VP狩り',
        'max_workers': 99,
        'prefer_gold': False,
        'hunt_ratio': 0.8,
        'accept_debt': 99,
    },
    'BALANCED': {
        'name': 'バランス',
        'name_en': 'Balance',
        'desc': '適度なワーカー、適度な借金',
        'max_workers': 4,
        'prefer_gold': False,
        'hunt_ratio': 0.5,
        'accept_debt': 4,
    },
    'DEBT_AVOID': {
        'name': '借金回避',
        'name_en': 'DebtAvoid',
        'desc': 'ワーカー控えめ、金貨管理',
        'max_workers': 3,
        'prefer_gold': False,
        'hunt_ratio': 0.4,
        'accept_debt': 1,
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
    rank: int  # 1..13 (通常) or 1..4 (切り札)

    def __str__(self) -> str:
        return f"{self.suit[0]}{self.rank:02d}"

    def is_trump(self) -> bool:
        """切り札カードかどうかを判定"""
        return self.suit == "Trump"


@dataclass
class GameConfig:
    """ゲームルールに関わる設定パラメーター"""
    start_gold: int = START_GOLD
    initial_workers: int = INITIAL_WORKERS
    declaration_bonus_vp: int = DECLARATION_BONUS_VP
    debt_penalty_multiplier: int = DEBT_PENALTY_MULTIPLIER
    debt_penalty_cap: Optional[int] = DEBT_PENALTY_CAP
    gold_to_vp_rate: int = GOLD_TO_VP_RATE
    take_gold_instead: int = TAKE_GOLD_INSTEAD
    rescue_gold_for_4th: int = RESCUE_GOLD_FOR_4TH

    def to_dict(self) -> Dict[str, Any]:
        """設定を辞書形式で返す"""
        return {
            "start_gold": self.start_gold,
            "initial_workers": self.initial_workers,
            "declaration_bonus_vp": self.declaration_bonus_vp,
            "debt_penalty_multiplier": self.debt_penalty_multiplier,
            "debt_penalty_cap": self.debt_penalty_cap,
            "gold_to_vp_rate": self.gold_to_vp_rate,
            "take_gold_instead": self.take_gold_instead,
            "rescue_gold_for_4th": self.rescue_gold_for_4th,
        }


@dataclass
class Player:
    name: str
    is_bot: bool = False
    rng: random.Random = field(default_factory=random.Random)
    strategy: Optional[str] = None  # CPU性格: CONSERVATIVE, VP_AGGRESSIVE, BALANCED, DEBT_AVOID

    gold: int = START_GOLD
    vp: int = 0

    # Workers
    basic_workers_total: int = INITIAL_WORKERS
    basic_workers_new_hires: int = 0  # hires that become active next round

    # Action levels (incremental improvements, 0..2)
    trade_level: int = 0  # yield 2..4
    hunt_level: int = 0   # yield 1..3

    # Recruit upgrades (pick one of them, overwrite allowed)
    recruit_upgrade: Optional[str] = None  # "RECRUIT_WAGE_DISCOUNT" or None

    # Permanent witches (flavor for tie-break)
    witches: List[str] = field(default_factory=list)

    # Witch ability usage this round
    ritual_used_this_round: bool = False  # WITCH_RITUAL: アクション再実行

    # Trick-taking round state
    tricks_won_this_round: int = 0
    declared_tricks: int = 0

    # Fixed hand: SETS_PER_GAME sets x CARDS_PER_SET cards
    sets: List[List[Card]] = field(default_factory=list)

    def trade_yield(self) -> int:
        return 2 + self.trade_level

    def hunt_yield(self) -> int:
        return 1 + self.hunt_level

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
            "workers": p.basic_workers_total,
            "new_hires_pending": p.basic_workers_new_hires,
            "trade_level": p.trade_level,
            "hunt_level": p.hunt_level,
            "trade_yield": p.trade_yield(),
            "hunt_yield": p.hunt_yield(),
            "recruit_upgrade": p.recruit_upgrade,
            "witches": p.witches[:],
            "declared_tricks": p.declared_tricks,
            "tricks_won": p.tricks_won_this_round,
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
        print(f"Invalid input: {s}")


def print_state(players: List[Player], round_no: int) -> None:
    print("\n" + "=" * 72)
    print(f"ROUND {round_no+1}/{ROUNDS} STATE")
    print("-" * 72)
    for p in players:
        print(
            f"{p.name:10s} | Gold={p.gold:2d} VP={p.vp:2d} "
            f"Workers={p.basic_workers_total:2d} (pending={p.basic_workers_new_hires:2d}) "
            f"TradeY={p.trade_yield()}(Lv{p.trade_level}) "
            f"HuntY={p.hunt_yield()}(Lv{p.hunt_level}) "
            f"Witches={p.permanent_witch_count()}"
        )
    print("=" * 72)


# ======= Setup =======

def deal_fixed_sets(
    players: List[Player],
    seed: int,
    logger: Optional[JsonlLogger],
    max_rank: int = 6,
    num_decks: int = 4,
) -> None:
    """
    Each player gets (SETS_PER_GAME * CARDS_PER_SET) cards.
    Default: 4 decks (96 cards) + 8 trump cards (T1-T4 x2) = 104 cards total.
    For 4p: needed = 4 * 4 * 6 = 96 cards => 8 cards surplus.
    """
    rng = random.Random(seed)
    deck: List[Card] = []
    for _ in range(num_decks):
        deck.extend([Card(s, r) for s in SUITS for r in range(1, max_rank + 1)])
    # 切り札カード追加（T1〜T4を2枚ずつ、計8枚）
    trumps = [Card("Trump", r) for r in range(1, 5) for _ in range(2)]
    deck.extend(trumps)
    rng.shuffle(deck)

    cards_per_player = SETS_PER_GAME * CARDS_PER_SET

    for p in players:
        cards = [deck.pop() for _ in range(cards_per_player)]
        p.sets = [cards[i*CARDS_PER_SET:(i+1)*CARDS_PER_SET] for i in range(SETS_PER_GAME)]

    if logger:
        hands = {p.name: [[str(c) for c in s] for s in p.sets] for p in players}
        logger.log("deal_hands", {"seed": seed, "hands": hands, "cards_per_set": CARDS_PER_SET})


# ======= Upgrades =======

def reveal_upgrades(rng: random.Random, n: int) -> List[str]:
    pool = (
        ["UP_TRADE"] * 6 +
        ["UP_HUNT"] * 6 +
        ["RECRUIT_INSTANT"] * 2 +
        ["RECRUIT_WAGE_DISCOUNT"] * 2 +
        ["WITCH_BLACKROAD", "WITCH_BLOODHUNT", "WITCH_HERD", "WITCH_RITUAL", "WITCH_BARRIER"]
    )
    return [rng.choice(pool) for _ in range(n)]


def upgrade_name(u: str) -> str:
    mapping = {
        "UP_TRADE": "交易拠点 改善（レベル+1）",
        "UP_HUNT": "魔物討伐 改善（レベル+1）",
        "RECRUIT_INSTANT": "見習い魔女派遣（即座に+2人）",
        "RECRUIT_WAGE_DISCOUNT": "育成負担軽減の護符（雇用ターン給料軽減）",
        "WITCH_BLACKROAD": "《黒路の魔女》",
        "WITCH_BLOODHUNT": "《血誓の討伐官》",
        "WITCH_HERD": "《群導の魔女》",
        "WITCH_RITUAL": "《大儀式の執行者》",
        "WITCH_BARRIER": "《結界織りの魔女》",
    }
    return mapping.get(u, u)


def upgrade_description(u: str) -> str:
    """Return detailed description for an upgrade card."""
    descriptions = {
        "UP_TRADE": "交易アクションの収益が+1金貨増加します。最大レベル2まで強化可能。",
        "UP_HUNT": "討伐アクションの獲得VPが+1増加します。最大レベル2まで強化可能。",
        "RECRUIT_INSTANT": "即座に見習い2人が派遣されます。このターンから行動可能、給料も発生。",
        "RECRUIT_WAGE_DISCOUNT": "雇用したターンの給料支払いが軽減されます。",
        "WITCH_BLACKROAD": "【効果】TRADEを行うたび、追加で+1金",
        "WITCH_BLOODHUNT": "【効果】HUNTを行うたび、追加で+1VP",
        "WITCH_HERD": "【効果】見習いを雇用したラウンド、給料合計-1",
        "WITCH_RITUAL": "【効果】各ラウンド1回、選んだ基本アクションをもう一度実行",
        "WITCH_BARRIER": "【効果】各ラウンド最初にHUNTを行った場合、追加で+1VP",
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

    "WITCH_RITUAL": """《大儀式の執行者》
役割：爆発力・借金前提

協会が「許可した」時にのみ執り行われる儀式。
成功すれば村は救われる。
失敗の記録は、協会の文書には残らない。""",

    "WITCH_BARRIER": """《結界織りの魔女》
役割：防衛・条件付きVP

結界は村を守る。
同時に、外へ出ることも難しくする。""",
}


def can_take_upgrade(player: Player, u: str) -> bool:
    if u == "UP_TRADE":
        return player.trade_level < 2
    if u == "UP_HUNT":
        return player.hunt_level < 2
    return True


def apply_upgrade(player: Player, u: str) -> None:
    if u == "UP_TRADE":
        player.trade_level = min(2, player.trade_level + 1)
    elif u == "UP_HUNT":
        player.hunt_level = min(2, player.hunt_level + 1)
    elif u == "RECRUIT_INSTANT":
        # 即座にワーカー+2（このターンから使用可能、給料も発生）
        player.basic_workers_total += 2
    elif u == "RECRUIT_WAGE_DISCOUNT":
        player.recruit_upgrade = u
    elif u.startswith("WITCH_"):
        player.witches.append(u)


def calc_expected_wage(player: Player, round_no: int) -> int:
    """次のラウンドで発生する給料を計算"""
    workers = player.basic_workers_total + player.basic_workers_new_hires
    init_count = min(INITIAL_WORKERS, workers)
    hired_count = workers - init_count
    return (init_count * WAGE_CURVE[round_no]) + (hired_count * UPGRADED_WAGE_CURVE[round_no])


def choose_upgrade_or_gold(player: Player, revealed: List[str], round_no: int = 0) -> str:
    available = [u for u in revealed if can_take_upgrade(player, u)]

    if player.is_bot:
        if not available:
            return "GOLD"

        # 性格に基づいた選択
        strat = STRATEGIES.get(player.strategy, STRATEGIES['BALANCED'])
        current_workers = player.basic_workers_total + player.basic_workers_new_hires
        expected_wage = calc_expected_wage(player, round_no)

        # 堅実: 常に金貨優先
        if strat['prefer_gold']:
            return "GOLD"

        # VPつっぱ: 常にアップグレード優先
        if player.strategy == 'VP_AGGRESSIVE':
            if 'RECRUIT_INSTANT' in available and current_workers < strat['max_workers']:
                return 'RECRUIT_INSTANT'
            for u in available:
                if u.startswith('UP_') or u.startswith('WITCH_'):
                    return u
            return 'GOLD'

        # 借金回避: 金貨が足りなければ金貨を取る
        if player.strategy == 'DEBT_AVOID':
            if player.gold < expected_wage + 3:
                return 'GOLD'

        # バランス/借金回避: ワーカー上限まで雇用、それ以外はアップグレード
        if current_workers < strat['max_workers']:
            if 'RECRUIT_INSTANT' in available:
                return 'RECRUIT_INSTANT'

        # アップグレード優先度
        for u in available:
            if u.startswith('UP_HUNT'):
                return u
            if u.startswith('UP_TRADE'):
                return u

        for u in available:
            if u.startswith('WITCH_'):
                return u

        return 'GOLD'

    print(f"\n{player.name}, choose your reward:")
    if available:
        for i, u in enumerate(available, start=1):
            print(f"  {i}. {upgrade_name(u)} [{u}]")
    else:
        print("  (No pickable upgrades for you.)")
    print(f"  G. Take {TAKE_GOLD_INSTEAD} gold instead")

    while True:
        s = input("Pick number or G: ").strip().upper()
        if s == "G":
            return "GOLD"
        try:
            idx = int(s)
            if 1 <= idx <= len(available):
                return available[idx - 1]
        except ValueError:
            pass
        print("Invalid choice.")


# ======= Declaration (SEE 6 cards -> declare -> seal 2 -> play 4) =======

def declare_tricks(player: Player, round_hand: List[Card], set_index: int) -> int:
    if player.is_bot:
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

    print(f"\n{player.name} Round hand (set #{set_index+1}, {CARDS_PER_SET} cards): " + " ".join(str(c) for c in round_hand))
    while True:
        s = input(f"{player.name} declare tricks (0-{TRICKS_PER_ROUND}): ").strip()
        try:
            v = int(s)
            if 0 <= v <= TRICKS_PER_ROUND:
                return v
        except ValueError:
            pass
        print("Invalid declaration.")


def apply_declaration_bonus(players: List[Player], logger: Optional[JsonlLogger], round_no: int) -> None:
    for p in players:
        if p.tricks_won_this_round == p.declared_tricks:
            before = p.vp
            p.vp += DECLARATION_BONUS_VP
            print(f"Declaration success: {p.name} matched {p.declared_tricks} -> +{DECLARATION_BONUS_VP} VP")
            if logger:
                logger.log("declaration_bonus", {
                    "round": round_no + 1,
                    "player": p.name,
                    "declared": p.declared_tricks,
                    "tricks_won": p.tricks_won_this_round,
                    "vp_before": before,
                    "vp_after": p.vp,
                    "bonus_vp": DECLARATION_BONUS_VP,
                })


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

    print(f"\n{player.name} seal {need_seal} cards (unplayable this round).")
    print("Your hand:", " ".join(str(c) for c in hand))
    sealed: List[Card] = []
    while len(sealed) < need_seal:
        s = input(f"Select card to SEAL ({len(sealed)+1}/{need_seal}) e.g., S13/H07/D01/C10/T01: ").strip().upper()
        suit_map = {"S": "Spade", "H": "Heart", "D": "Diamond", "C": "Club", "T": "Trump"}
        if len(s) < 2 or s[0] not in suit_map:
            print("Invalid.")
            continue
        try:
            rank = int(s[1:])
        except ValueError:
            print("Invalid.")
            continue
        chosen = Card(suit_map[s[0]], rank)
        if chosen not in hand:
            print("You don't have that card.")
            continue
        hand.remove(chosen)
        sealed.append(chosen)
        print("Remaining:", " ".join(str(c) for c in hand))
    return sealed


# ======= Trick-taking (with Trump cards) =======

def trick_winner(lead_suit: str, plays: List[Tuple[Player, Card]]) -> Player:
    """
    Trump rules:
      - If any trump card is played, highest trump wins.
      - Otherwise, highest card in lead suit wins.
    Tiebreaker (same rank):
      - Leader wins if tied.
      - Otherwise, player closest to leader (clockwise) wins.
    plays[0] is the leader, plays order is clockwise.
    """
    # 切り札が出ているか確認
    trumps = [(i, p, c) for i, (p, c) in enumerate(plays) if c.is_trump()]
    if trumps:
        # 切り札の中で最高ランクを探す
        max_rank = max(c.rank for _, _, c in trumps)
        # 同ランクの場合、親に近い人（インデックスが小さい方）が勝ち
        for i, p, c in trumps:
            if c.rank == max_rank:
                return p

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


def choose_card(player: Player, lead_card: Optional[Card], hand: List[Card]) -> Card:
    legal = legal_cards(hand, lead_card)

    if player.is_bot:
        return player.rng.choice(legal)

    while True:
        print(f"\n{player.name} playable hand: " + " ".join(str(c) for c in hand))
        if lead_card:
            print(f"Lead: {lead_card}")
            if any(c.suit == lead_card.suit for c in hand):
                print(f"Must follow: {lead_card.suit}")
            else:
                trump_in_hand = [c for c in hand if c.is_trump()]
                if trump_in_hand:
                    print("Cannot follow - Trump available!")
        else:
            print("You are leading (Trump cards cannot lead)")

        print("Legal:", " ".join(str(c) for c in legal))

        s = input("Choose a card (e.g., S13 / H07 / D01 / C10 / T01): ").strip().upper()
        suit_map = {"S": "Spade", "H": "Heart", "D": "Diamond", "C": "Club", "T": "Trump"}
        if len(s) < 2 or s[0] not in suit_map:
            print("Invalid.")
            continue
        try:
            rank = int(s[1:])
        except ValueError:
            print("Invalid.")
            continue

        chosen = Card(suit_map[s[0]], rank)
        if chosen not in hand:
            print("You don't have that card.")
            continue
        if chosen not in legal:
            print("Illegal play (must-follow rule or cannot lead with trump).")
            continue
        return chosen


def run_trick_taking(players: List[Player], round_no: int, rng: random.Random, logger: Optional[JsonlLogger]) -> int:
    """
    Flow:
      - Prepare 6-card round hand (set_index)
      - Declaration after seeing round hand
      - Seal 2 cards (unplayable), leaving 4
      - Play 4 tricks with normal must-follow (NO TRUMP)
      - Declaration bonus
    Returns leader_index used for tie-break ordering.
    """
    set_index = round_no % SETS_PER_GAME
    leader_index = round_no % len(players)

    for p in players:
        p.tricks_won_this_round = 0
        p.ritual_used_this_round = False

    full_hands: Dict[str, List[Card]] = {p.name: players[i].sets[set_index][:] for i, p in enumerate(players)}

    print("\n--- Declaration (after seeing round hand) ---")
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

    print("Declarations:", ", ".join(f"{p.name}:{p.declared_tricks}" for p in players))

    print("\n--- Sealing cards (choose 2 to be unplayable this round) ---")
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

    # 他プレイヤーのシールカードを表示
    print("\n--- Sealed Cards (All Players) ---")
    for p in players:
        print(f"  {p.name}: {', '.join(str(c) for c in sealed_by_player[p.name])}")

    print(f"\n--- Trick-taking Round {round_no+1}: Using set #{set_index+1} (6 -> seal 2 -> play 4) ---")
    print(f"Leader this round: {players[leader_index].name} | (No trump)")

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

        print("Plays:", " | ".join(f"{pl.name}:{c}" for pl, c in plays))
        print(f"Trick winner: {winner.name} (lead suit {lead_card.suit})")

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

    print("\n--- Trick Results ---")
    print("-" * 40)
    for p in players:
        status = "✓" if p.tricks_won_this_round == p.declared_tricks else ""
        print(f"  {p.name}: {p.tricks_won_this_round} tricks (declared {p.declared_tricks}) {status}")
    print("-" * 40)

    print("\n--- Declaration Bonus ---")
    apply_declaration_bonus(players, logger, round_no)

    return leader_index


def rank_players_for_upgrade(players: List[Player], leader_index: int) -> List[Player]:
    """
    Rank by:
      1) tricks won
      2) permanent witch count
      3) seat order from leader (earlier is better)
    """
    order = {players[(leader_index + i) % 4].name: i for i in range(4)}

    def key(p: Player):
        return (p.tricks_won_this_round, p.permanent_witch_count(), -order[p.name])

    return sorted(players, key=key, reverse=True)


# ======= Worker Placement =======

def choose_actions_for_player(player: Player, round_no: int = 0) -> List[str]:
    n = player.basic_workers_total
    actions: List[str] = []

    if player.is_bot:
        strat = STRATEGIES.get(player.strategy, STRATEGIES['BALANCED'])
        expected_wage = calc_expected_wage(player, round_no)
        gold_needed = expected_wage - player.gold

        for _ in range(n):
            if player.strategy == 'CONSERVATIVE':
                # 堅実: 常にTRADE
                actions.append("TRADE")
            elif player.strategy == 'VP_AGGRESSIVE':
                # VPつっぱ: 高確率でHUNT
                if player.rng.random() < strat['hunt_ratio']:
                    actions.append("HUNT")
                else:
                    actions.append("TRADE")
            elif player.strategy == 'DEBT_AVOID':
                # 借金回避: まず給料分を確保、余剰でHUNT
                if gold_needed > 0:
                    actions.append("TRADE")
                    gold_needed -= player.trade_yield()
                else:
                    if player.rng.random() < strat['hunt_ratio']:
                        actions.append("HUNT")
                    else:
                        actions.append("TRADE")
            else:  # BALANCED
                # バランス: 確率でHUNT/TRADE
                if player.rng.random() < strat['hunt_ratio']:
                    actions.append("HUNT")
                else:
                    actions.append("TRADE")
        return actions

    print(f"\n{player.name} chooses actions for {n} apprentices.")
    for i in range(n):
        a = prompt_choice(f" action for worker {i+1}", ACTIONS, default="TRADE")
        actions.append(a)
    return actions


def resolve_actions(player: Player, actions: List[str]) -> Dict[str, Any]:
    before = {"gold": player.gold, "vp": player.vp, "new_hires": player.basic_workers_new_hires}
    first_hunt_done = False  # Track for WITCH_BARRIER
    witch_bonuses: List[str] = []

    for a in actions:
        if a == "TRADE":
            player.gold += player.trade_yield()
            # WITCH_BLACKROAD: TRADEで+1金
            if "WITCH_BLACKROAD" in player.witches:
                player.gold += 1
                witch_bonuses.append("黒路の魔女: +1金")
        elif a == "HUNT":
            player.vp += player.hunt_yield()
            # WITCH_BLOODHUNT: HUNTで+1VP
            if "WITCH_BLOODHUNT" in player.witches:
                player.vp += 1
                witch_bonuses.append("血誓の討伐官: +1VP")
            # WITCH_BARRIER: 最初のHUNTで+1VP
            if not first_hunt_done and "WITCH_BARRIER" in player.witches:
                player.vp += 1
                witch_bonuses.append("結界織りの魔女: +1VP (初回HUNT)")
            first_hunt_done = True
        elif a == "RECRUIT":
            player.basic_workers_new_hires += 1
        else:
            raise ValueError(f"Unknown action: {a}")

    after = {"gold": player.gold, "vp": player.vp, "new_hires": player.basic_workers_new_hires}
    return {"before": before, "after": after, "witch_bonuses": witch_bonuses}


def pay_wages_and_debt(
    player: Player,
    round_no: int,
    debt_multiplier: Optional[int] = None,
    debt_cap: Optional[int] = None,
    initial_workers_config: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Rule:
    - New hires do NOT act this round
    - BUT their wage IS paid starting this round
    - Initial workers use WAGE_CURVE, hired workers use UPGRADED_WAGE_CURVE

    Args:
        debt_multiplier: Override for debt penalty multiplier (None = use global)
        debt_cap: Override for debt penalty cap (None = use global)
        initial_workers_config: Override for initial workers count (None = use global)
    """
    before_gold, before_vp = player.gold, player.vp

    workers_active = player.basic_workers_total
    workers_hired_this_round = player.basic_workers_new_hires
    workers_paid = workers_active + workers_hired_this_round  # include hires in wage

    # Calculate wages: initial workers vs upgraded (hired) workers
    initial_wage_rate = WAGE_CURVE[round_no]
    upgraded_wage_rate = UPGRADED_WAGE_CURVE[round_no]

    initial_workers_base = initial_workers_config if initial_workers_config is not None else INITIAL_WORKERS
    initial_workers_count = min(initial_workers_base, workers_paid)
    upgraded_workers_count = workers_paid - initial_workers_count

    wage_gross = (initial_workers_count * initial_wage_rate) + (upgraded_workers_count * upgraded_wage_rate)

    discount = 0
    witch_wage_bonus = ""
    if player.recruit_upgrade == "RECRUIT_WAGE_DISCOUNT":
        # interpret: reduce wage by 1 per hired worker this round
        discount = workers_hired_this_round

    # WITCH_HERD: 見習いを雇用したラウンド、給料合計-1
    if "WITCH_HERD" in player.witches and workers_hired_this_round > 0:
        discount += 1
        witch_wage_bonus = "群導の魔女: 給料-1"

    wage_net = max(0, wage_gross - discount)

    paid = min(player.gold, wage_net)
    short = max(0, wage_net - player.gold)

    debt_penalty = 0
    if player.gold >= wage_net:
        player.gold -= wage_net
    else:
        player.gold = 0
        # Use config overrides if provided, otherwise use global
        actual_multiplier = debt_multiplier if debt_multiplier is not None else DEBT_PENALTY_MULTIPLIER
        actual_cap = debt_cap if debt_cap is not None else DEBT_PENALTY_CAP
        debt_penalty = calculate_debt_penalty_configurable(short, actual_multiplier, actual_cap)
        player.vp -= debt_penalty

    return {
        "initial_wage_rate": initial_wage_rate,
        "upgraded_wage_rate": upgraded_wage_rate,
        "initial_workers": initial_workers_count,
        "upgraded_workers": upgraded_workers_count,
        "workers_active": workers_active,
        "workers_hired_this_round": workers_hired_this_round,
        "workers_paid_total": workers_paid,
        "wage_gross": wage_gross,
        "wage_discount": discount,
        "wage_net": wage_net,
        "paid_gold": paid,
        "short_gold": short,
        "debt_penalty": debt_penalty,
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
            "UPGRADED_WAGE_CURVE": UPGRADED_WAGE_CURVE,
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

    deal_fixed_sets(players, seed=deal_seed, logger=logger)

    for round_no in range(ROUNDS):
        print_state(players, round_no)

        revealed = reveal_upgrades(rng, REVEAL_UPGRADES)
        print("\nRevealed Upgrades:")
        for u in revealed:
            print(" -", upgrade_name(u), f"[{u}]")
        logger.log("reveal_upgrades", {"round": round_no + 1, "revealed": revealed[:]})

        leader_index = run_trick_taking(players, round_no, rng, logger)

        ranked = rank_players_for_upgrade(players, leader_index)
        logger.log("upgrade_pick_order", {
            "round": round_no + 1,
            "order": [p.name for p in ranked],
            "tricks_won": {p.name: p.tricks_won_this_round for p in players},
            "witches": {p.name: p.permanent_witch_count() for p in players},
            "declared": {p.name: p.declared_tricks for p in players},
        })

        print("\nRanking for upgrade pick:")
        for i, p in enumerate(ranked, start=1):
            print(f" {i}. {p.name} tricks={p.tricks_won_this_round} witches={p.permanent_witch_count()} declared={p.declared_tricks}")

        for p in ranked:
            before = snapshot_players([p])[0]
            choice = choose_upgrade_or_gold(p, revealed, round_no)

            if choice == "GOLD":
                p.gold += TAKE_GOLD_INSTEAD
                print(f"{p.name} takes {TAKE_GOLD_INSTEAD} gold.")
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
                apply_upgrade(p, choice)
                print(f"{p.name} takes upgrade: {upgrade_name(choice)}")
                logger.log("upgrade_pick", {
                    "round": round_no + 1,
                    "player": p.name,
                    "choice": choice,
                    "choice_name": upgrade_name(choice),
                    "revealed_remaining": revealed[:],
                    "before": before,
                    "after": snapshot_players([p])[0],
                })

        fourth = ranked[-1]
        before_gold = fourth.gold
        fourth.gold += RESCUE_GOLD_FOR_4TH
        print(f"\nRescue: {fourth.name} gains +{RESCUE_GOLD_FOR_4TH} gold (4th place).")
        logger.log("rescue", {
            "round": round_no + 1,
            "player": fourth.name,
            "gold_before": before_gold,
            "gold_after": fourth.gold,
            "amount": RESCUE_GOLD_FOR_4TH,
        })

        print("\n--- Worker Placement ---")
        logger.log("wp_start", {"round": round_no + 1, "players": snapshot_players(players)})
        for p in players:
            actions = choose_actions_for_player(p, round_no)
            delta = resolve_actions(p, actions)
            print(f"{p.name} actions={actions} => Gold={p.gold}, VP={p.vp}, NewHires={p.basic_workers_new_hires}")
            logger.log("wp_actions", {
                "round": round_no + 1,
                "player": p.name,
                "actions": actions,
                "delta": delta,
                "state": snapshot_players([p])[0],
            })

        initial_rate = WAGE_CURVE[round_no]
        upgraded_rate = UPGRADED_WAGE_CURVE[round_no]
        cap_info = f"上限{DEBT_PENALTY_CAP}" if DEBT_PENALTY_CAP else "無制限"
        print(f"\n--- Wage Payment (初期={initial_rate}, 雇用={upgraded_rate}) and Debt (-{DEBT_PENALTY_MULTIPLIER}VP/金, {cap_info}) ---")
        logger.log("wage_phase_start", {"round": round_no + 1, "initial_wage_rate": initial_rate, "upgraded_wage_rate": upgraded_rate, "players": snapshot_players(players)})

        for p in players:
            res = pay_wages_and_debt(p, round_no)
            print(f"{p.name}: Gold {res['gold_before']}->{res['gold_after']}, VP {res['vp_before']}->{res['vp_after']}")
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

        logger.log("round_end", {"round": round_no + 1, "players": snapshot_players(players)})

    # ゲーム終了時: 金貨をVPに変換
    print("\n--- 金貨→VP変換 ---")
    for p in players:
        bonus_vp = p.gold // GOLD_TO_VP_RATE
        if bonus_vp > 0:
            print(f"{p.name}: {p.gold}G → +{bonus_vp}VP")
            p.vp += bonus_vp

    players_sorted = sorted(players, key=lambda p: (p.vp, p.gold), reverse=True)
    logger.log("game_end", {
        "final_ranking": [{"rank": i+1, "name": p.name, "vp": p.vp, "gold": p.gold} for i, p in enumerate(players_sorted)],
        "players": snapshot_players(players),
    })
    logger.close()

    print("\n=== GAME OVER ===")
    for i, p in enumerate(players_sorted, start=1):
        print(f"{i}. {p.name} VP={p.vp} Gold={p.gold} Workers={p.basic_workers_total} "
              f"TradeY={p.trade_yield()}(Lv{p.trade_level}) HuntY={p.hunt_yield()}(Lv{p.hunt_level}) "
              f"Witches={p.permanent_witch_count()}")
    print(f"\nWinner: {players_sorted[0].name}")
    print(f"\nLog written to: {LOG_PATH}")


# ======= GameEngine for GUI =======

@dataclass
class InputRequest:
    """Represents a request for human input."""
    type: str  # "declaration", "seal", "choose_card", "upgrade", "worker_actions"
    player: Player
    context: Dict[str, Any]


class GameEngine:
    """State-machine based game engine for GUI integration."""

    def __init__(self, seed: int = 42, config: Optional[GameConfig] = None):
        self.rng = random.Random(seed)
        self.deal_seed = seed
        self.config = config if config is not None else GameConfig()

        # CPUにランダムな性格を割り当て
        bot_rng = random.Random()
        self.players = [
            Player("P1", is_bot=False, rng=random.Random(1)),
            Player("P2", is_bot=True, rng=random.Random(2), strategy=assign_random_strategy(bot_rng)),
            Player("P3", is_bot=True, rng=random.Random(3), strategy=assign_random_strategy(bot_rng)),
            Player("P4", is_bot=True, rng=random.Random(4), strategy=assign_random_strategy(bot_rng)),
        ]

        # 設定値でプレイヤーの初期状態を上書き
        for p in self.players:
            p.gold = self.config.start_gold
            p.basic_workers_total = self.config.initial_workers

        deal_fixed_sets(self.players, seed=self.deal_seed, logger=None)

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
        self.current_trick = 0
        self.trick_plays: List[Tuple[Player, Card]] = []
        self.lead_card: Optional[Card] = None
        self.trick_leader = 0
        self.trick_player_offset = 0

        # Worker placement state
        self.wp_player_index = 0
        self.wp_actions: List[str] = []

        # Trick history for display (current round)
        self.trick_history: List[Dict[str, Any]] = []

        # Game log for display
        self.log_messages: List[str] = []

        self._pending_input: Optional[InputRequest] = None

    def _log(self, msg: str):
        self.log_messages.append(msg)

    def get_state(self) -> Dict[str, Any]:
        """Return current game state for display."""
        return {
            "round_no": self.round_no,
            "phase": self.phase,
            "sub_phase": self.sub_phase,
            "players": snapshot_players(self.players),
            "revealed_upgrades": self.revealed_upgrades[:],
            "trick_history": self.trick_history[:],
            "current_trick": self.current_trick,
            "sealed_by_player": {name: [str(c) for c in cards] for name, cards in self.sealed_by_player.items()},
            "log": self.log_messages[-20:],  # Last 20 messages
            "game_over": self.phase == "game_end",
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
            self._log(f"{player.name} declares {response} tricks")
            self._pending_input = None

        elif req_type == "seal":
            # response is list of Card objects
            for c in response:
                self.full_hands[player.name].remove(c)
            self.sealed_by_player[player.name] = response
            self.playable_hands[player.name] = self.full_hands[player.name][:]
            self._log(f"{player.name} sealed: {', '.join(str(c) for c in response)}")
            self._pending_input = None

        elif req_type == "choose_card":
            hand = self.playable_hands[player.name]
            hand.remove(response)
            self.trick_plays.append((player, response))
            if self.lead_card is None:
                self.lead_card = response
            self._pending_input = None

        elif req_type == "upgrade":
            # response is upgrade string or "GOLD"
            if response == "GOLD":
                gold_amount = self.config.take_gold_instead
                player.gold += gold_amount
                self._log(f"{player.name} takes {gold_amount} gold")
            else:
                self.revealed_upgrades.remove(response)
                apply_upgrade(player, response)
                self._log(f"{player.name} takes: {upgrade_name(response)}")
            self._pending_input = None

        elif req_type == "worker_actions":
            # response can be list of actions or dict with additional witch abilities
            if isinstance(response, dict):
                actions = response.get("actions", [])
                ritual_action = response.get("ritual_action")

                # Resolve main actions
                delta = resolve_actions(player, actions)
                self._log(f"{player.name} actions: {actions}")

                # Apply WITCH_RITUAL (extra action)
                if ritual_action:
                    extra_delta = resolve_actions(player, [ritual_action])
                    player.ritual_used_this_round = True
                    self._log(f"  《大儀式の執行者》: 追加{ritual_action}")
            else:
                # Backward compatibility: response is just a list
                actions = response
                delta = resolve_actions(player, actions)
                self._log(f"{player.name} actions: {actions}")

            self.wp_actions = actions
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
            if self.round_no >= ROUNDS:
                self._finish_game()
                return False

            self._log(f"=== Round {self.round_no + 1}/{ROUNDS} ===")
            self.revealed_upgrades = reveal_upgrades(self.rng, REVEAL_UPGRADES)
            self._log(f"Upgrades: {', '.join(upgrade_name(u) for u in self.revealed_upgrades)}")

            self.set_index = self.round_no % SETS_PER_GAME
            self.leader_index = self.round_no % len(self.players)

            for p in self.players:
                p.tricks_won_this_round = 0
                p.ritual_used_this_round = False

            self.full_hands = {p.name: p.sets[self.set_index][:] for p in self.players}
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
                self._log(f"{player.name} declares {player.declared_tricks} tricks")
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
                self._log(f"{player.name} sealed: {', '.join(str(c) for c in sealed)}")
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

        # Phase: upgrade_pick
        if self.phase == "upgrade_pick":
            if self.upgrade_pick_index >= len(self.ranked_players):
                # Give 4th place rescue gold
                fourth = self.ranked_players[-1]
                rescue_gold = self.config.rescue_gold_for_4th
                fourth.gold += rescue_gold
                self._log(f"Rescue: {fourth.name} +{rescue_gold} gold")
                self.phase = "worker_placement"
                self.wp_player_index = 0
                return True

            player = self.ranked_players[self.upgrade_pick_index]
            available = [u for u in self.revealed_upgrades if can_take_upgrade(player, u)]

            if player.is_bot:
                choice = choose_upgrade_or_gold(player, self.revealed_upgrades, self.round_no)
                if choice == "GOLD":
                    gold_amount = self.config.take_gold_instead
                    player.gold += gold_amount
                    self._log(f"{player.name} takes {gold_amount} gold")
                else:
                    self.revealed_upgrades.remove(choice)
                    apply_upgrade(player, choice)
                    self._log(f"{player.name} takes: {upgrade_name(choice)}")
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

        # Phase: worker_placement
        if self.phase == "worker_placement":
            if self.wp_player_index >= len(self.players):
                self.phase = "wage_payment"
                return True

            player = self.players[self.wp_player_index]

            if player.is_bot:
                actions = choose_actions_for_player(player, self.round_no)
                resolve_actions(player, actions)
                self._log(f"{player.name} actions: {actions}")
                self.wp_player_index += 1
            else:
                self._pending_input = InputRequest(
                    type="worker_actions",
                    player=player,
                    context={
                        "num_workers": player.basic_workers_total,
                        "witches": player.witches[:],
                        "can_use_ritual": "WITCH_RITUAL" in player.witches and not player.ritual_used_this_round,
                    }
                )
                self.wp_player_index += 1
                return True
            return True

        # Phase: wage_payment
        if self.phase == "wage_payment":
            initial_rate = WAGE_CURVE[self.round_no]
            upgraded_rate = UPGRADED_WAGE_CURVE[self.round_no]
            self._log(f"--- Wage Payment (初期={initial_rate}, 雇用={upgraded_rate}) ---")

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

            self.round_no += 1
            self.phase = "round_start"
            return True

        return True

    def _start_trick(self):
        """Initialize a new trick."""
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
            self._log(f"Trick {self.current_trick + 1}: {plays_str} -> {winner.name} wins")

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
                self._log("--- Trick Results ---")
                for p in self.players:
                    status = "✓" if p.tricks_won_this_round == p.declared_tricks else ""
                    self._log(f"  {p.name}: {p.tricks_won_this_round} tricks (declared {p.declared_tricks}) {status}")
                self._apply_declaration_bonus()
                self.ranked_players = rank_players_for_upgrade(self.players, self.leader_index)
                self.upgrade_pick_index = 0
                self.phase = "upgrade_pick"
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

    def _apply_declaration_bonus(self):
        """Apply declaration bonus to players who matched their declaration."""
        bonus_vp = self.config.declaration_bonus_vp
        for p in self.players:
            if p.tricks_won_this_round == p.declared_tricks:
                p.vp += bonus_vp
                self._log(f"Declaration success: {p.name} matched {p.declared_tricks} -> +{bonus_vp} VP")

    def _finish_game(self):
        """Finalize game and determine winner."""
        # 金貨→VP変換
        gold_to_vp_rate = self.config.gold_to_vp_rate
        self._log("--- Gold to VP conversion ---")
        for p in self.players:
            bonus_vp = p.gold // gold_to_vp_rate if gold_to_vp_rate > 0 else 0
            if bonus_vp > 0:
                self._log(f"{p.name}: {p.gold}G -> +{bonus_vp}VP")
                p.vp += bonus_vp

        self.phase = "game_end"
        players_sorted = sorted(self.players, key=lambda p: (p.vp, p.gold), reverse=True)
        self._log("=== GAME OVER ===")
        for i, p in enumerate(players_sorted, start=1):
            self._log(f"{i}. {p.name} VP={p.vp} Gold={p.gold}")
        self._log(f"Winner: {players_sorted[0].name}")


# ======= Simulation =======

def run_single_game_quiet(
    seed: int,
    max_rank: int = 6,
    num_decks: int = 4,
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

    deal_fixed_sets(players, seed=seed, logger=None, max_rank=max_rank,
                    num_decks=num_decks)

    for round_no in range(ROUNDS):
        revealed = reveal_upgrades(rng, REVEAL_UPGRADES)
        set_index = round_no % SETS_PER_GAME
        leader_index = round_no % len(players)

        for p in players:
            p.tricks_won_this_round = 0

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

        # Upgrade pick
        ranked = rank_players_for_upgrade(players, leader_index)
        for p in ranked:
            choice = choose_upgrade_or_gold(p, revealed, round_no)
            if choice == "GOLD":
                p.gold += TAKE_GOLD_INSTEAD
            else:
                revealed.remove(choice)
                apply_upgrade(p, choice)

        fourth = ranked[-1]
        fourth.gold += RESCUE_GOLD_FOR_4TH

        # Worker placement
        for p in players:
            actions = choose_actions_for_player(p, round_no)
            resolve_actions(p, actions)

        # Wage payment
        for p in players:
            pay_wages_and_debt(p, round_no)

        # Activate hires
        for p in players:
            if p.basic_workers_new_hires > 0:
                p.basic_workers_total += p.basic_workers_new_hires
                p.basic_workers_new_hires = 0

    # Gold to VP conversion at end
    for p in players:
        bonus_vp = p.gold // GOLD_TO_VP_RATE
        p.vp += bonus_vp

    # Return results
    players_sorted = sorted(players, key=lambda p: (p.vp, p.gold), reverse=True)
    vps = [p.vp for p in players_sorted]
    return {
        "winner": players_sorted[0].name,
        "vps": vps,
        "vp_diff_1st_2nd": vps[0] - vps[1],
        "vp_diff_1st_last": vps[0] - vps[-1],
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
    """Run simulations for rank ranges 6-10, 100 games each.

    Note: max_rank must be at least 6 for 4 decks to have enough cards.
    4 decks * 4 suits * 6 ranks = 96 cards + 8 trump = 104 total (need 96 for 4p*4r*6c)
    """
    print("=== カードランク最適化シミュレーション ===")
    print(f"各設定で100ゲーム実行中...\n")

    results = []
    for max_rank in range(6, 11):
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
    """Run simulation with specified deck count. Trump is fixed at T1-T4 x2 = 8 cards."""
    results = []
    for game_id in range(num_games):
        seed = game_id * 1000 + num_decks * 100
        result = run_single_game_quiet(seed, max_rank=6, num_decks=num_decks)
        results.append(result)

    vp_diffs = [r["vp_diff_1st_2nd"] for r in results]
    avg_diff = sum(vp_diffs) / len(vp_diffs)
    std_diff = (sum((x - avg_diff) ** 2 for x in vp_diffs) / len(vp_diffs)) ** 0.5

    return {
        "num_decks": num_decks,
        "total_cards": num_decks * 24 + 8,  # 4suits * 6ranks = 24, plus 8 trumps
        "num_games": num_games,
        "avg_vp_diff": avg_diff,
        "std_vp_diff": std_diff,
    }


def run_all_deck_simulations():
    """Run simulations for different deck counts. Trump is fixed at T1-T4 x2."""
    print("=== デッキ数最適化シミュレーション ===")
    print("(切り札は T1〜T4 x 2枚 = 8枚固定)")
    print(f"各設定で100ゲーム実行中...\n")

    # テスト設定: デッキ3-5
    configs = [3, 4, 5]

    results = []
    for num_decks in configs:
        total = num_decks * 24 + 8
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

    # 今ラウンドの給料を予測（新規雇用なしと仮定）
    initial_wage_rate = WAGE_CURVE[round_no]
    upgraded_wage_rate = UPGRADED_WAGE_CURVE[round_no]
    initial_workers_count = min(INITIAL_WORKERS, n)
    upgraded_workers_count = n - initial_workers_count
    expected_wage = (initial_workers_count * initial_wage_rate) + (upgraded_workers_count * upgraded_wage_rate)

    # TRADEで稼げる額
    trade_yield = player.trade_yield()
    if "WITCH_BLACKROAD" in player.witches:
        trade_yield += 1

    # HUNTで稼げるVP
    hunt_yield = player.hunt_yield()
    if "WITCH_BLOODHUNT" in player.witches:
        hunt_yield += 1

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

    deal_fixed_sets(players, seed=seed, logger=None, max_rank=6, num_decks=4)

    # Track debt occurrences
    total_debt_events = 0
    total_debt_amount = 0
    total_debt_penalty = 0

    for round_no in range(ROUNDS):
        revealed = reveal_upgrades(rng, REVEAL_UPGRADES)
        set_index = round_no % SETS_PER_GAME
        leader_index = round_no % len(players)

        for p in players:
            p.tricks_won_this_round = 0

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

        # Upgrade pick
        ranked = rank_players_for_upgrade(players, leader_index)
        for p in ranked:
            choice = choose_upgrade_or_gold(p, revealed, round_no)
            if choice == "GOLD":
                p.gold += TAKE_GOLD_INSTEAD
            else:
                revealed.remove(choice)
                apply_upgrade(p, choice)

        fourth = ranked[-1]
        fourth.gold += RESCUE_GOLD_FOR_4TH

        # Worker placement (with smart bot that considers debt penalty)
        for p in players:
            if use_tiered:
                # 段階式の場合、ペナルティが軽いので借金回避意識が低い
                actions = choose_actions_smart_bot(p, round_no, 1, 3)  # 実質max 3VP
            else:
                actions = choose_actions_smart_bot(p, round_no, debt_multiplier, debt_cap)
            resolve_actions(p, actions)

        # Wage payment with configurable debt penalty
        for p in players:
            workers_active = p.basic_workers_total
            workers_hired_this_round = p.basic_workers_new_hires
            workers_paid = workers_active + workers_hired_this_round

            initial_wage_rate = WAGE_CURVE[round_no]
            upgraded_wage_rate = UPGRADED_WAGE_CURVE[round_no]

            initial_workers_count = min(INITIAL_WORKERS, workers_paid)
            upgraded_workers_count = workers_paid - initial_workers_count

            wage_gross = (initial_workers_count * initial_wage_rate) + (upgraded_workers_count * upgraded_wage_rate)

            discount = 0
            if p.recruit_upgrade == "RECRUIT_WAGE_DISCOUNT":
                discount = workers_hired_this_round
            if "WITCH_HERD" in p.witches and workers_hired_this_round > 0:
                discount += 1

            wage_net = max(0, wage_gross - discount)
            short = max(0, wage_net - p.gold)

            if p.gold >= wage_net:
                p.gold -= wage_net
            else:
                p.gold = 0
                # Use configurable debt penalty
                debt_penalty = calculate_debt_penalty_configurable(
                    short, debt_multiplier, debt_cap, use_tiered
                )
                p.vp -= debt_penalty
                total_debt_events += 1
                total_debt_amount += short
                total_debt_penalty += debt_penalty

        # Activate hires
        for p in players:
            if p.basic_workers_new_hires > 0:
                p.basic_workers_total += p.basic_workers_new_hires
                p.basic_workers_new_hires = 0

    # Gold to VP conversion at end
    for p in players:
        bonus_vp = p.gold // GOLD_TO_VP_RATE
        p.vp += bonus_vp

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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="魔女協会 Card Game")
    parser.add_argument("--simulate", action="store_true", help="Run rank optimization simulation")
    parser.add_argument("--simulate-deck", action="store_true", help="Run deck/trump count optimization simulation")
    parser.add_argument("--simulate-debt-penalty", action="store_true", help="Run debt penalty optimization simulation")
    args = parser.parse_args()

    try:
        if args.simulate:
            run_all_simulations()
        elif args.simulate_deck:
            run_all_deck_simulations()
        elif args.simulate_debt_penalty:
            run_all_debt_penalty_simulations()
        else:
            main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
