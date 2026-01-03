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

1. **Upgrade Reveal** - Random upgrades revealed for drafting (witches only appear in Round 3)
2. **Trick-Taking Phase**
   - Players see 5 cards, declare target tricks (0-4)
   - Seal 1 card (unplayable), play 4 tricks with remaining 4 cards
   - No trump suit; must follow lead suit if able
   - Declaration bonus (+1 VP) for matching predicted tricks
3. **Upgrade Selection** - Players ranked by tricks won pick upgrades or take gold
4. **Worker Placement** - Assign workers to TRADE/HUNT/RECRUIT actions
5. **Wage Payment** - Pay initial workers only (hired workers already paid at acquisition)

### Key Data Structures

- `Card(suit, rank)` - Frozen dataclass representing playing cards
- `Player` - Mutable dataclass with gold, VP, workers, action levels, witches
- `JsonlLogger` - Writes game events to `game_log.jsonl` for analysis

### Game Configuration (constants at top of file)

- `ROUNDS = 6`, `TRICKS_PER_ROUND = 4`, `CARDS_PER_SET = 5`
- `WAGE_CURVE = [1, 1, 2, 2, 2, 3]` - Initial worker wages per round
- `UPGRADED_WAGE_CURVE = [0, 0, 0, 0, 0, 0]` - Hired workers pay 2 gold at acquisition, no ongoing wages
- `START_GOLD = 7`
- `DECLARATION_BONUS_VP = 1` (no failure penalty)
- `DEBT_PENALTY_MULTIPLIER = 2` - VP penalty per 1 gold debt
- `DEBT_PENALTY_CAP = None` - Max penalty cap (None = unlimited)
- Trade upgrade: +2 gold per level (base 2, max 6 at level 2)
- Hunt upgrade: +1 VP per level (base 1, max 3 at level 2)
- Witches only available in Round 3 (including new WITCH_GOLDCONVERT for 1:1 gold-to-VP conversion)

### Bot Logic

Bots use simple heuristics in `choose_card()`, `declare_tricks()`, `seal_cards()`, and `choose_upgrade_or_gold()`. Human player (P1) receives CLI prompts.

## Card Input Format

When playing as human, enter cards as `{suit}{rank}`:
- S = Spade, H = Heart, D = Diamond, C = Club
- Examples: `S13` (Spade King), `H07` (Heart 7), `D01` (Diamond Ace)

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
