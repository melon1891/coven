# selection-order-change

Description: アップグレード選択順・ワーカー配置順のソートロジックを変更する際の変更箇所チェックリスト。
User-invocable: true

## Instructions

アップグレード選択順とワーカー配置順は別々の関数で管理されているが、同じソート基準を使うことが多い。

### 変更箇所一覧

#### 1. アップグレード選択順 (`rank_players_for_upgrade`, main.py)
検索: `def rank_players_for_upgrade`
- ソートキー定義（`key` 関数）
- 現在の優先度: トリック数 > 恩寵先行権 > 恩寵数 > 座席順
- 全4箇所のコードパス（CLI/GameEngine/Simulation/Simulation Debt）で共通関数を使用

#### 2. ワーカー配置順 (`determine_placement_order`, main.py)
検索: `def determine_placement_order`
- ソートキー定義（lambda式）
- 現在の優先度: トリック数 > 恩寵先行権 > 恩寵数 > 座席順
- CLI/GameEngine/Simulation 全パスで共通関数を使用

#### 3. 表示（CLI, main.py）
検索: `アップグレード選択順`
- `print` 文でのソート順表示内容を更新

### 関連ファイルの更新
- `CLAUDE.md` - Game Flow セクションのUpgrade Selection説明
- `README.md` - ラウンドの流れ（5. アップグレード選択）
- `static/js/ui.js` - Rich UIのルール説明文があれば更新

### 注意事項
- `rank_players_for_upgrade` と `determine_placement_order` は同じソート基準に保つのが望ましい
- 恩寵先行権（`grace_priority`）は2恩寵消費で取得する別機能。ソート基準の恩寵数とは別
- 最終タイブレーカーとして座席順（`order` dict）を残すことで、完全同値時の決定性を保証
