# end-game-scoring-change

Description: ゲーム終了時の得点計算（金→恩寵変換、恩寵→VP変換、負債ペナルティ等）を変更する際の変更箇所チェックリスト。
User-invocable: true

## Instructions

ゲーム終了時のスコアリング処理は4箇所に重複実装されている。変更時は全箇所を同期すること。

### 変更箇所一覧

#### 1. 定数（main.py 冒頭）
- `GOLD_TO_GRACE_RATE` - 金→恩寵変換レート
- `GOLD_TO_VP_RATE` - 金→VP変換レート
- `GRACE_VP_PER_N` / `GRACE_VP_AMOUNT` - 恩寵→VP変換
- `DEBT_PENALTY_MULTIPLIER` / `DEBT_PENALTY_CAP` - 負債ペナルティ

#### 2. CLI (`play_game` 関数, main.py)
検索: `ゲーム終了時` or `金貨→恩寵変換` or `恩寵→VP変換` or `金貨→VP変換` or `負債ペナルティ`
- 金→恩寵変換
- 恩寵→VP変換
- 金→VP変換（残り金貨）
- 負債ペナルティ

#### 3. GameEngine (`_finish_game` メソッド, main.py)
検索: `def _finish_game`
- 金→恩寵変換
- 恩寵→VP変換
- 金→VP変換
- 負債ペナルティ

#### 4. Simulation (`run_single_game_quiet` 関数, main.py)
検索: `def run_single_game_quiet`
- 関数パラメータにレート追加（シミュレーション用に可変にする場合）
- 金→恩寵変換
- 恩寵→VP変換
- 金→VP変換
- 負債ペナルティ

#### 5. Simulation Debt (`run_single_game_quiet_debt` 関数, main.py)
検索: `def run_single_game_quiet_debt`
- 金→恩寵変換
- 恩寵→VP変換
- 金→VP変換
- 負債ペナルティ（configurable版）

### 処理順序（重要）
以下の順序で適用すること。順序を変えるとVP計算が変わる。
1. 金→恩寵変換（GOLD_TO_GRACE_RATE）
2. 恩寵→VP変換（GRACE_VP_PER_N / GRACE_VP_AMOUNT）
3. 残り金→VP変換（GOLD_TO_VP_RATE）
4. 負債ペナルティ

### 関連ファイルの更新
- `CLAUDE.md` - Grace System Constants セクション、Game Flow セクション
- `README.md` - 恩寵システムの説明、ラウンドの流れ
- `streamlit_app.py` - 恩寵システムの説明文（expander内）
- `static/js/ui.js` - ゲーム結果画面（`showResult` メソッド）
- `static/css/main.css` - 結果画面のスタイル（ranking-detail等）

### シミュレーション
変換レートの最適値を求めるには:
```bash
uv run python main.py --simulate-gold-grace
```
