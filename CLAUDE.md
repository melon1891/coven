# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

witchASC is a CLI-based card game prototype combining trick-taking mechanics with worker placement, themed around a Witch Guild. The game is designed for 4 players (1 human + 3 bots).

## Running the Game

```bash
# Using uv (recommended)
uv run python main.py

# Or with standard Python (requires Python 3.11+)
python main.py
```

## Game Architecture

### Core Game Loop (`main.py`)

The game runs 6 rounds, each with these phases:

1. **Card Deal** - Deck reshuffled each round (48 cards + 4 trumps)
2. **Upgrade Reveal** - Upgrades revealed (Round 3 shows witches instead)
3. **Trick-Taking Phase**
   - Players see 5 cards, declare target tricks (0-4)
   - Seal 1 card (unplayable), play 4 tricks with remaining 4 cards
   - Trump cards can win any trick; must follow lead suit if able
   - Declaration bonus (+1 VP) for matching predicted tricks
4. **Upgrade Selection** - Players ranked by tricks won pick upgrades or take gold
5. **Worker Placement** - Assign workers to TRADE/HUNT/RECRUIT actions
6. **Wage Payment** - Pay initial workers only (hired workers paid 2G upfront, no wages)

### Key Data Structures

- `Card(suit, rank)` - Frozen dataclass representing playing cards
- `Player` - Mutable dataclass with gold, VP, workers, action levels, witches
- `JsonlLogger` - Writes game events to `game_log.jsonl` for analysis

### Game Configuration (constants at top of file)

- `ROUNDS = 6`, `TRICKS_PER_ROUND = 4`, `CARDS_PER_SET = 5`
- `NUM_DECKS = 2` - 2 decks (48 cards = 6 ranks × 4 suits × 2)
- `WAGE_CURVE = [1, 1, 2, 2, 2, 3]` - Initial worker wages per round
- `UPGRADE_WORKER_COST = 2` - Cost to hire workers (no wages after)
- `START_GOLD = 5`
- `DECLARATION_BONUS_VP = 1` (no failure penalty)
- `DEBT_PENALTY_MULTIPLIER = 2` - VP penalty per 1 gold debt
- `WITCH_ROUND = 2` - Witches appear in round 3 (0-indexed)
- Trade upgrade: +2 gold/level (base 2, Lv1=4, Lv2=6)
- Hunt upgrade: +1 VP/level (base 1, Lv1=2, Lv2=3)

### Bot Logic

Bots use simple heuristics in `choose_card()`, `declare_tricks()`, `seal_cards()`, and `choose_upgrade_or_gold()`. Human player (P1) receives CLI prompts.

## Card Input Format

When playing as human, enter cards as `{suit}{rank}`:
- S = Spade, H = Heart, D = Diamond, C = Club, T = Trump
- Examples: `S06` (Spade 6), `H03` (Heart 3), `D01` (Diamond Ace), `T01` (Trump)

## Logging

All game events are logged to `game_log.jsonl` in JSONL format with timestamps, game IDs, and full state snapshots. Useful for game balance analysis.

## Simulation Commands

```bash
# Card rank optimization simulation
uv run python main.py --simulate

# Deck count optimization simulation
uv run python main.py --simulate-deck

# Debt penalty optimization simulation
uv run python main.py --simulate-debt-penalty
```
