# game-rule-change

Description: ゲームルール変更を安全に適用する。main.py内のCLI/GameEngine/Simulationの3コードパスを一貫して更新し、関連ファイルも同期する。
User-invocable: true

## Instructions

ゲームルール変更時、ロジックがmain.py内に3箇所重複しているため、変更漏れが起きやすい。このスキルで安全に適用する。

### 重複コードパスの一覧

main.py内で同じゲームロジックが3箇所に実装されている:

| パス | 関数/メソッド | 用途 |
|------|-------------|------|
| CLI | `apply_declaration_bonus()`, `resolve_actions()`, `pay_wages_and_debt()`, ゲーム終了処理 | コマンドラインプレイ |
| GameEngine | `_apply_declaration_bonus()`, `_finish_game()`, worker_placement phase | Streamlit GUI |
| Simulation | `run_single_game_quiet()` 内のインライン処理 | カードランク/恩寵シミュレーション |
| Simulation (debt) | `run_single_game_quiet_debt()` 内のインライン処理 | 負債ペナルティシミュレーション |

### 変更適用手順

1. **影響分析**: ユーザーの変更要求を受け、影響を受けるコードパスを特定する
2. **定数変更**: main.py冒頭の定数セクションを更新
3. **CLI更新**: 関連する関数を更新
4. **GameEngine更新**: 対応するメソッドを更新
5. **Simulation更新**: `run_single_game_quiet()` 内の対応箇所を更新
6. **Simulation (debt)更新**: `run_single_game_quiet_debt()` 内の対応箇所を更新
7. **CLAUDE.md更新**: 定数セクションを更新
8. **streamlit_app.py更新**: import文とUI説明文を更新
9. **動作確認**: `PYTHONIOENCODING=utf-8 uv run python main.py --auto` で確認
10. **制約検証**: GameEngineを使った制約テストを実行

### 検索のコツ

変更対象を見つけるために、以下のパターンでGrepする:
- 定数名そのもの（例: `GRACE_THRESHOLD_BONUS`）
- 関連する日本語キーワード（例: `恩寵`, `閾値`, `宣言成功`）
- 関数名パターン（例: `declaration_bonus`, `grace_bonus`）

### 注意事項
- Bot戦略（`STRATEGIES`辞書）内のパラメータも変更が必要なことがある（例: `max_workers`）
- アップグレード説明文（`upgrade_description()`）も更新が必要なことがある
- streamlit_app.pyのimport文に新しい定数を追加する場合、既存のimport行を確認する
- Rich UI (`static/js/ui.js`) のワーカー配置UI・結果画面も更新が必要
- Rich UIサーバー (`rich_ui_server.py`) のcontext送信も確認
- **共有スポット方式**: アクション文字列は `SPOT:{owner}:{idx}:{type}` 形式
  - `get_available_actions`: 全プレイヤーのスポットを列挙（`ps.all_players`）
  - `resolve_single_action`: 所有者判定・所有者収入（+1金）処理
  - `bot_choose_single_action`: スコアリングは文字列パターンマッチで動作
  - `PlacementState.all_players`: ワーカー配置開始時にセットが必要
