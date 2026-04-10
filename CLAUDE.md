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

# シミュレーション
uv run python main.py --simulate          # カードランク
uv run python main.py --simulate-deck     # デッキ枚数
uv run python main.py --simulate-debt-penalty  # 負債ペナルティ
uv run python main.py --simulate-grace    # 恩寵ポイント
uv run python main.py --simulate-gold-grace  # 金→恩寵変換レート
```

## Architecture

### Core Files

- `main.py` - ゲームロジック・CLI・シミュレーション

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
NUM_DECKS = 2           # デッキ数（40通常カード + 2切り札 = 42枚）
START_GOLD = 5          # 初期金貨
INITIAL_WORKERS = 2     # 初期ワーカー数
MAX_WORKERS = 5         # ワーカー雇用上限
WAGE_CURVE = [1, 1, 1, 1, 2, 2, 2, 3]  # ラウンドごとの給料（8R対応）
WITCH_ROUND = 2         # 魔女が出現するラウンド（0-indexed、R3）
```

### Worker Placement Constants (ナショエコ式)

```python
SHARED_TRADE_GOLD = 2        # 共通Trade獲得金
SHARED_HUNT_VP = 1           # 共通Hunt獲得VP
SHARED_PRAY_GRACE = 1        # 共通Pray獲得恩寵
RECRUIT_COST = 2             # 雇用コスト
PERSONAL_TRADE_GOLD = 2      # 共有Trade獲得金
PERSONAL_HUNT_VP = 1         # 共有Hunt獲得VP
PERSONAL_PRAY_GRACE = 1      # 共有Pray獲得恩寵
PERSONAL_RITUAL_GRACE = 2    # 共有Ritual獲得恩寵
PERSONAL_RITUAL_GOLD = 2     # 共有Ritual獲得金（選択時）
OWNER_INCOME_GOLD = 1        # 他プレイヤーが共有スポット使用時、所有者への収入
WITCH_BLACKROAD_GOLD = 2     # 黒路の魔女 獲得金（※パッシブ化: 個人交易+1金）
WITCH_BLOODHUNT_VP = 1       # 血誓の討伐官 獲得VP（※パッシブ化: 個人討伐+1VP）
WITCH_NEGOTIATE_GRACE_COST = 1  # 交渉の魔女 恩寵消費
WITCH_NEGOTIATE_GOLD = 2       # 交渉の魔女 金獲得
WITCH_ZERO_GRACE = 3           # 予言者 恩寵報酬
WITCH_ZERO_GOLD = 3            # 予言者 金報酬
WITCH_ZERO_VP = 2              # 予言者 VP報酬
WITCH_CHARM_VP_PER_WORKER = 1  # 魅了の魔女 ワーカー1人あたりVP
```

### Grace System Constants (恩寵システム)

```python
GRACE_ENABLED = True              # 恩寵機能のON/OFF
GRACE_VP_PER_N = 5                # N恩寵毎にVP変換
GRACE_VP_AMOUNT = 3               # 変換で得られるVP（5恩寵毎→3VP）
GRACE_HAND_SWAP_COST = 2          # 手札交換コスト（指定枚数、一律2恩寵）
GRACE_PRAY_GAIN = 1               # 祈り基礎獲得量
GRACE_RITUAL_GAIN = 1             # 儀式アクション基礎（参照用）
GRACE_DECLARATION_ZERO_BONUS = 1  # 宣言0成功ボーナス（※廃止: 慎重の予言者の専用効果に統合）
# GRACE_ZERO_TRICKS_BONUS / ZERO_TRICKS_GOLD_BONUS は廃止（0勝ボーナスなし）
GRACE_4TH_PLACE_BONUS = 2         # 4位救済ボーナス
GOLD_TO_GRACE_RATE = 2            # ゲーム終了時、2金=1恩寵に変換（恩寵→VP変換の前に適用）
```

### Worker Placement (ナショエコ式ブロッキング)

| スポット | 種別 | 効果 | ブロッキング |
|---------|------|------|------------|
| 交易 | 共通 | 2金 | 全体で1人のみ |
| 討伐 | 共通 | 1VP | 全体で1人のみ |
| 祈り | 共通 | 1恩寵 | 全体で1人のみ |
| 雇用 | オープン | 2金→+1人 | 制限なし |
| 共有交易 | 共有 | Lv1:2金 / Lv2:3金 | 全員可（他者使用時、所有者+1金） |
| 共有討伐 | 共有 | Lv1:1VP / Lv2:2VP | 全員可（他者使用時、所有者+1金） |
| 共有祈り | 共有 | Lv1:1恩寵 / Lv2:2恩寵 | 全員可（他者使用時、所有者+1金） |
| 共有儀式 | 共有 | Lv1:2恩寵or2金 / Lv2:3恩寵or3金（ワーカー永久消費） | 全員可（他者使用時、所有者+1金） |
| WITCH_NEGOTIATE | 共有 | 1恩寵→2金 | 全員可（他者使用時、所有者+1金） |

**レベルシステム**: 同種のアップグレードは最大2枚まで取得可能（Lv1→Lv2）。Lv2は基本効果+1。

### Witch Cards (魔女カード、R3登場)

| 魔女 | 種別 | 効果 |
|------|------|------|
| WITCH_BLACKROAD | パッシブ | 交易スポット使用時+1金 |
| WITCH_BLOODHUNT | パッシブ | 討伐スポット使用時+1VP |
| WITCH_HERD | パッシブ | 初期ワーカー1人分の給料免除 |
| WITCH_NEGOTIATE | 共有スポット | 1恩寵消費→2金 |
| WITCH_BLESSING | パッシブ | 祈りスポット使用時+1恩寵 |
| WITCH_MIRROR | パッシブ | 他プレイヤー宣言成功時+1金 |
| WITCH_ZERO_MASTER | パッシブ | 0宣言解禁。成功時 3恩寵/3金/2VPから選択 |
| WITCH_CHARM | パッシブ | ゲーム終了時、ワーカー1人=1VP |

### Game Flow (per round)

- **ターン開始**: 恩寵最多プレイヤーがリード（タイブレーク: ラウンドロビン）
- **魔女候補**: ゲーム開始時にR3の魔女候補5枚を全員に公開

1. **Card Deal** - 5枚配布
2. **Upgrade Reveal** - アップグレード公開（R3は魔女）
3. **Trick-Taking** - 宣言（恩寵最多から順に1-4、慎重の予言者所持時のみ0可）→手札交換（2恩寵で指定枚数）→公開封印1枚→4トリック
4. **Upgrade Selection** - トリック獲得順に選択（同数時は恩寵多い方優先、共有ボードに配置）
6. **Worker Placement** - ナショエコ式ラウンドロビン配置
7. **Wage Payment** - 初期ワーカーのみ給料支払い（未払い分は負債として累積、ゲーム終了時にVPペナルティ）
8. **End-of-Game** - WITCH_CHARM VP加算→金→恩寵変換（2金=1恩寵）→恩寵→VP変換（5恩寵=3VP）→残金→VP変換（2金=1VP）→負債ペナルティ

### Key Classes

- `PlacementState` - ワーカー配置の状態管理（共通スポット/共有スポット使用状況）
- `Player.personal_spots` - アップグレードカードから得た共有ワーカースポットのリスト（所有者情報）

### Card Input Format (CLI)

`{suit}{rank}` 形式:
- S = Spade, H = Heart, D = Diamond, C = Club, T = Trump
- 例: `S05`, `H03`, `D01`, `T` (切り札はランクなし)
