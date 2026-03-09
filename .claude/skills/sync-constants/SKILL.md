# sync-constants

Description: ゲームバランス定数の同期チェック。main.py、CLAUDE.md、streamlit_app.py間の定数不整合を検出する。
User-invocable: true

## Instructions

ゲームバランス定数は以下の3ファイルに散在しており、変更時に同期漏れが発生しやすい。このスキルで不整合を検出する。

### 対象ファイル
1. `main.py` - 定数の正本（ソースオブトゥルース）
2. `CLAUDE.md` - 開発ガイド内の定数記述
3. `streamlit_app.py` - GUI内の説明文・import

### チェック手順

1. **main.pyの定数定義を収集**
   以下のカテゴリの定数を読み取る:
   - ゲーム設定: `ROUNDS`, `TRICKS_PER_ROUND`, `CARDS_PER_SET`, `NUM_DECKS`, `START_GOLD`, `INITIAL_WORKERS`, `MAX_WORKERS`, `WAGE_CURVE`, `UPGRADE_WORKER_COST`
   - 恩寵システム: `GRACE_ENABLED`, `GRACE_VP_PER_N`, `GRACE_VP_AMOUNT`, `GRACE_HAND_SWAP_COST`, `GRACE_PRAY_GAIN`, `GRACE_DONATE_COST`, `GRACE_DONATE_GAIN`, `GRACE_RITUAL_GAIN`, `GRACE_DECLARATION_ZERO_BONUS`, `GRACE_ZERO_TRICKS_BONUS`, `GRACE_4TH_PLACE_BONUS`
   - 宣言・負債: `DECLARATION_BONUS_VP`, `DEBT_PENALTY_MULTIPLIER`, `DEBT_PENALTY_CAP`, `GOLD_TO_VP_RATE`
   - アクション関連: `trade_yield()`, `hunt_yield()` のレベル上限

2. **CLAUDE.mdとの照合**
   - `Game Configuration Constants` セクション内のコードブロックの値と一致しているか
   - `Grace System Constants` セクション内のコードブロックの値と一致しているか

3. **streamlit_app.pyとの照合**
   - importされている定数名が正しいか
   - UI説明文（マークダウン文字列）内の数値が定数と一致しているか
   - 特に恩寵変換ルール、交易/討伐のレベル上限、ワーカー上限の記述

4. **結果報告**
   - 不整合があれば: ファイル名、行番号、期待値 vs 実際値を一覧表示
   - 不整合がなければ: 「全定数同期OK」と報告
