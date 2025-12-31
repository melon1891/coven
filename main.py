#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CLI Prototype: Trick-taking x Worker-placement (Witch Guild theme)

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

START_GOLD = 5
WAGE_CURVE = [1, 1, 2, 3]
DEBT_VP_PENALTY_PER_GOLD = 1
RESCUE_GOLD_FOR_4TH = 2
TAKE_GOLD_INSTEAD = 2
DECLARATION_BONUS_VP = 1

ACTIONS = ["TRADE", "HUNT", "RECRUIT"]

LOG_PATH = "game_log.jsonl"


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
    suit: str
    rank: int  # 1..13

    def __str__(self) -> str:
        return f"{self.suit[0]}{self.rank:02d}"


@dataclass
class Player:
    name: str
    is_bot: bool = False
    rng: random.Random = field(default_factory=random.Random)

    gold: int = START_GOLD
    vp: int = 0

    # Workers
    basic_workers_total: int = 2
    basic_workers_new_hires: int = 0  # hires that become active next round

    # Action levels (incremental improvements, 0..2)
    trade_level: int = 0  # yield 2..4
    hunt_level: int = 0   # yield 1..3

    # Recruit upgrades (pick one of them, overwrite allowed)
    recruit_upgrade: Optional[str] = None  # "RECRUIT_DOUBLE" or "RECRUIT_WAGE_DISCOUNT" or None

    # Permanent witches (flavor for tie-break)
    witches: List[str] = field(default_factory=list)

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

def deal_fixed_sets(players: List[Player], seed: int, logger: Optional[JsonlLogger]) -> None:
    """
    Each player gets (SETS_PER_GAME * CARDS_PER_SET) cards.
    Prototype uses 2 decks (104 cards). For 4p:
      needed = 4 * 4 * 6 = 96 cards => OK.
    """
    rng = random.Random(seed)
    deck = [Card(s, r) for s in SUITS for r in range(1, 14)]
    deck2 = [Card(s, r) for s in SUITS for r in range(1, 14)]
    rng.shuffle(deck)
    rng.shuffle(deck2)
    deck.extend(deck2)

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
        ["RECRUIT_DOUBLE"] * 2 +
        ["RECRUIT_WAGE_DISCOUNT"] * 2 +
        ["WITCH_BLACKROAD", "WITCH_BLOODHUNT", "WITCH_HERD", "WITCH_RITUAL", "WITCH_INSPECT", "WITCH_BARRIER"]
    )
    return [rng.choice(pool) for _ in range(n)]


def upgrade_name(u: str) -> str:
    mapping = {
        "UP_TRADE": "交易拠点 改善（レベル+1）",
        "UP_HUNT": "魔物討伐 改善（レベル+1）",
        "RECRUIT_DOUBLE": "集団育成計画（雇用×2）",
        "RECRUIT_WAGE_DISCOUNT": "育成負担軽減の護符（雇用ターン給料軽減）",
        "WITCH_BLACKROAD": "《黒路の魔女》",
        "WITCH_BLOODHUNT": "《血誓の討伐官》",
        "WITCH_HERD": "《群導の魔女》",
        "WITCH_RITUAL": "《大儀式の執行者》",
        "WITCH_INSPECT": "《巡察の魔女》",
        "WITCH_BARRIER": "《結界織りの魔女》",
    }
    return mapping.get(u, u)


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
    elif u in ("RECRUIT_DOUBLE", "RECRUIT_WAGE_DISCOUNT"):
        player.recruit_upgrade = u
    elif u.startswith("WITCH_"):
        player.witches.append(u)


def choose_upgrade_or_gold(player: Player, revealed: List[str]) -> str:
    available = [u for u in revealed if can_take_upgrade(player, u)]

    if player.is_bot:
        if not available:
            return "GOLD"
        if player.rng.random() < 0.75:
            prefs: List[Tuple[int, str]] = []
            for u in available:
                if u in ("UP_TRADE", "UP_HUNT"):
                    prefs.append((3, u))
                elif u.startswith("RECRUIT"):
                    prefs.append((2, u))
                elif u.startswith("WITCH"):
                    prefs.append((1, u))
                else:
                    prefs.append((0, u))
            prefs.sort(reverse=True)
            return prefs[0][1]
        return "GOLD"

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
        suits = [c.suit for c in round_hand]
        max_same = max(suits.count(s) for s in SUITS)
        # declare 0..4
        if max_same >= 3:
            cand = [2, 2, 3, 1, 4]
        elif max_same == 2:
            cand = [1, 2, 2, 0, 3]
        else:
            cand = [0, 1, 1, 2, 2]
        v = player.rng.choice(cand)
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
        # bot heuristic: seal the two lowest ranks
        sealed = sorted(hand, key=lambda c: c.rank)[:need_seal]
        for c in sealed:
            hand.remove(c)
        return sealed

    print(f"\n{player.name} seal {need_seal} cards (unplayable this round).")
    print("Your hand:", " ".join(str(c) for c in hand))
    sealed: List[Card] = []
    while len(sealed) < need_seal:
        s = input(f"Select card to SEAL ({len(sealed)+1}/{need_seal}) e.g., S13/H07/D01/C10: ").strip().upper()
        suit_map = {"S": "Spade", "H": "Heart", "D": "Diamond", "C": "Club"}
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


# ======= Trick-taking (Normal must-follow, NO TRUMP) =======

def trick_winner(lead_suit: str, plays: List[Tuple[Player, Card]]) -> Player:
    """
    No trump:
      - Highest card in lead suit wins.
      - Other suits cannot win.
    """
    leads = [(p, c) for p, c in plays if c.suit == lead_suit]
    best_p, best_c = leads[0]
    for p, c in leads[1:]:
        if c.rank > best_c.rank:
            best_p, best_c = p, c
    return best_p


def legal_cards(hand: List[Card], lead_card: Optional[Card]) -> List[Card]:
    """
    - If leading: any card.
    - If not leading: must follow lead suit if possible.
      Otherwise any card is legal.
    """
    if lead_card is None:
        return hand[:]

    lead_suit = lead_card.suit
    follow = [c for c in hand if c.suit == lead_suit]
    return follow if follow else hand[:]


def choose_card(player: Player, lead_card: Optional[Card], hand: List[Card]) -> Card:
    legal = legal_cards(hand, lead_card)

    if player.is_bot:
        return player.rng.choice(legal)

    while True:
        print(f"\n{player.name} playable hand: " + " ".join(str(c) for c in hand))
        if lead_card:
            print(f"Lead: {lead_card} | (No trump)")
            if any(c.suit == lead_card.suit for c in hand):
                print(f"Must follow: {lead_card.suit}")
        else:
            print("You are leading | (No trump)")

        print("Legal:", " ".join(str(c) for c in legal))

        s = input("Choose a card (e.g., S13 / H07 / D01 / C10): ").strip().upper()
        suit_map = {"S": "Spade", "H": "Heart", "D": "Diamond", "C": "Club"}
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
            print("Illegal play (must-follow rule).")
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

def choose_actions_for_player(player: Player) -> List[str]:
    n = player.basic_workers_total
    actions: List[str] = []

    if player.is_bot:
        for _ in range(n):
            if player.gold < 3:
                actions.append("TRADE")
            else:
                actions.append(player.rng.choice(["HUNT", "TRADE", "RECRUIT"]))
        return actions

    print(f"\n{player.name} chooses actions for {n} apprentices.")
    for i in range(n):
        a = prompt_choice(f" action for worker {i+1}", ACTIONS, default="TRADE")
        actions.append(a)
    return actions


def resolve_actions(player: Player, actions: List[str]) -> Dict[str, Any]:
    before = {"gold": player.gold, "vp": player.vp, "new_hires": player.basic_workers_new_hires}
    for a in actions:
        if a == "TRADE":
            player.gold += player.trade_yield()
        elif a == "HUNT":
            player.vp += player.hunt_yield()
        elif a == "RECRUIT":
            hires = 1
            if player.recruit_upgrade == "RECRUIT_DOUBLE":
                hires = 2
            player.basic_workers_new_hires += hires
        else:
            raise ValueError(f"Unknown action: {a}")
    after = {"gold": player.gold, "vp": player.vp, "new_hires": player.basic_workers_new_hires}
    return {"before": before, "after": after}


def pay_wages_and_debt(player: Player, wage_rate: int) -> Dict[str, Any]:
    """
    Rule:
    - New hires do NOT act this round
    - BUT their wage IS paid starting this round
    """
    before_gold, before_vp = player.gold, player.vp

    workers_active = player.basic_workers_total
    workers_hired_this_round = player.basic_workers_new_hires
    workers_paid = workers_active + workers_hired_this_round  # include hires in wage

    wage_gross = wage_rate * workers_paid

    discount = 0
    if player.recruit_upgrade == "RECRUIT_WAGE_DISCOUNT":
        # interpret: reduce wage by 1 per hired worker this round
        discount = workers_hired_this_round

    wage_net = max(0, wage_gross - discount)

    paid = min(player.gold, wage_net)
    short = max(0, wage_net - player.gold)

    if player.gold >= wage_net:
        player.gold -= wage_net
    else:
        player.gold = 0
        player.vp -= short * DEBT_VP_PENALTY_PER_GOLD

    return {
        "wage_rate": wage_rate,
        "workers_active": workers_active,
        "workers_hired_this_round": workers_hired_this_round,
        "workers_paid_total": workers_paid,
        "wage_gross": wage_gross,
        "wage_discount": discount,
        "wage_net": wage_net,
        "paid_gold": paid,
        "short_gold": short,
        "gold_before": before_gold,
        "gold_after": player.gold,
        "vp_before": before_vp,
        "vp_after": player.vp,
        "debt_penalty_per_gold": DEBT_VP_PENALTY_PER_GOLD,
    }


# ======= Main =======

def main():
    logger = JsonlLogger(LOG_PATH)

    rng = random.Random(42)
    deal_seed = 42

    players = [
        Player("P1", is_bot=False, rng=random.Random(1)),
        Player("P2", is_bot=True,  rng=random.Random(2)),
        Player("P3", is_bot=True,  rng=random.Random(3)),
        Player("P4", is_bot=True,  rng=random.Random(4)),
    ]

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
            "DEBT_VP_PENALTY_PER_GOLD": DEBT_VP_PENALTY_PER_GOLD,
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
            choice = choose_upgrade_or_gold(p, revealed)

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
            actions = choose_actions_for_player(p)
            delta = resolve_actions(p, actions)
            print(f"{p.name} actions={actions} => Gold={p.gold}, VP={p.vp}, NewHires={p.basic_workers_new_hires}")
            logger.log("wp_actions", {
                "round": round_no + 1,
                "player": p.name,
                "actions": actions,
                "delta": delta,
                "state": snapshot_players([p])[0],
            })

        wage_rate = WAGE_CURVE[round_no]
        print(f"\n--- Wage Payment (rate={wage_rate}) and Debt (-{DEBT_VP_PENALTY_PER_GOLD}VP/gold) ---")
        logger.log("wage_phase_start", {"round": round_no + 1, "wage_rate": wage_rate, "players": snapshot_players(players)})

        for p in players:
            res = pay_wages_and_debt(p, wage_rate)
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


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
