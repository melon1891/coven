# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

基本的な使い方やゲームルールについては [README.md](./README.md) を参照してください。

## Project Overview

魔女協会（Coven）は、トリックテイキングとワーカープレイスメントを組み合わせたCLIベースのカードゲームプロトタイプです。4人プレイ（1人+Bot3人、または全員Bot）で遊べます。

## Development Commands

```bash
# CLIモード（対人）
uv run python main.py

# 自動実行モード（CI/動作確認用）
uv run python main.py --auto

# Streamlit GUI
uv run streamlit run streamlit_app.py

# シミュレーション
uv run python main.py --simulate          # カードランク
uv run python main.py --simulate-deck     # デッキ枚数
uv run python main.py --simulate-debt-penalty  # 負債ペナルティ
uv run python main.py --simulate-grace    # 恩寵ポイント
```

## Architecture

### Core Files

- `main.py` - ゲームロジック・CLI・シミュレーション
- `streamlit_app.py` - Streamlit GUI

### Key Classes

- `GameEngine` - ステートマシンベースのゲームエンジン（GUI用）
- `GameConfig` - ゲーム設定（ラウンド数、初期金貨など）
- `Card(suit, rank)` - カードを表すfrozen dataclass
- `Player` - プレイヤーの状態（金貨、VP、ワーカーなど）
- `UpgradeDeck` - アップグレードカードのデッキ管理

### Game Configuration Constants

```python
ROUNDS = 6              # 固定ラウンド数
TRICKS_PER_ROUND = 4    # 1ラウンドのトリック数
CARDS_PER_SET = 5       # 配られる手札枚数
NUM_DECKS = 2           # デッキ数（96通常カード + 4切り札）
START_GOLD = 5          # 初期金貨
INITIAL_WORKERS = 2     # 初期ワーカー数
WAGE_CURVE = [1, 1, 2, 2, 2, 3]  # ラウンドごとの給料
UPGRADE_WORKER_COST = 2 # 雇用ワーカーの初期コスト
WITCH_ROUND = 2         # 魔女が出現するラウンド（0-indexed、R3）
```

### Grace System Constants (恩寵システム)

```python
GRACE_ENABLED = True              # 恩寵機能のON/OFF
GRACE_THRESHOLD_BONUS = [         # 閾値ボーナス（最高のみ適用）
    (13, 8),  # 13点以上 → +8VP
    (10, 5),  # 10点以上 → +5VP
]
GRACE_HAND_SWAP_COST = 1          # 手札交換コスト
GRACE_PRAY_GAIN = 1               # 祈り基礎獲得量（Lv0）
GRACE_DONATE_COST = 2             # 寄付アクション消費金
GRACE_DONATE_GAIN = 1             # 寄付獲得量
GRACE_RITUAL_GAIN = 1             # 儀式アクション獲得量
GRACE_DECLARATION_ZERO_BONUS = 1  # 宣言0成功ボーナス
GRACE_ZERO_TRICKS_BONUS = 1       # トリック0勝ボーナス
GRACE_4TH_PLACE_BONUS = 2         # 4位救済ボーナス
```

### Grace Actions (恩寵アクション)

| アクション | 種別 | 効果 |
|-----------|------|------|
| PRAY | 初期アクション | 1ワーカー → 1+pray_level恩寵 |
| DONATE | UP_DONATEで解放 | 1ワーカー + 2金 → 1恩寵 |
| RITUAL | UP_RITUALで解放 | 1ワーカー → 1恩寵 |

### Game Flow (per round)

1. **Card Deal** - 5枚配布
2. **Upgrade Reveal** - アップグレード公開（R3は魔女）
3. **Trick-Taking** - 宣言→封印1枚→4トリック
4. **Upgrade Selection** - トリック獲得順に選択
5. **Worker Placement** - TRADE/HUNT/RECRUIT/PRAY（+DONATE/RITUAL）実行
6. **Wage Payment** - 初期ワーカーのみ給料支払い

### Card Input Format (CLI)

`{suit}{rank}` 形式:
- S = Spade, H = Heart, D = Diamond, C = Club, T = Trump
- 例: `S06`, `H03`, `D01`, `T` (切り札はランクなし)
