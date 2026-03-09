# リッチUI実装計画書

## 概要

魔女協会（Coven）のブラウザベースリッチUIを実装する。現在のStreamlit UIを維持しつつ、新しいモダンなWebアプリケーションUIを追加する。

## 目標

- ブラウザで有人対戦が可能なリッチUI
- カードイラストは後で差し替え可能
- シンプルだがインタラクションが分かりやすいデザイン
- 既存UIとスイッチで切り替え可能
- まずはPL1人+CPU3人の対戦をリッチUIで実現

---

## フェーズ1: インフラストラクチャ

### 1.1 技術スタック

| レイヤー | 技術 | 理由 |
|---------|------|------|
| バックエンド | FastAPI + WebSocket | 既存GameEngineとの統合が容易、リアルタイム通信 |
| フロントエンド | HTML/CSS/JavaScript (Vanilla) | 依存関係最小化、カスタマイズ容易 |
| 状態管理 | サーバーサイド (GameEngine) | 既存ロジック活用 |
| スタイリング | CSS Variables + Flexbox/Grid | テーマ切り替え対応 |

### 1.2 ディレクトリ構造

```
witchASC/
├── main.py                    # 既存（変更なし）
├── streamlit_app.py           # 既存Streamlit UI（変更なし）
├── rich_ui_server.py          # 新規: FastAPI サーバー
├── static/
│   ├── css/
│   │   ├── main.css           # メインスタイル
│   │   ├── cards.css          # カード表示用
│   │   └── animations.css     # アニメーション
│   ├── js/
│   │   ├── app.js             # メインアプリ
│   │   ├── game.js            # ゲームロジック
│   │   ├── ui.js              # UI更新
│   │   └── websocket.js       # WebSocket通信
│   └── images/
│       └── cards/             # カード画像（差し替え可能）
│           ├── placeholder/   # プレースホルダー画像
│           └── README.md      # 画像差し替え手順
├── templates/
│   └── index.html             # メインHTMLテンプレート
└── run_rich_ui.py             # 起動スクリプト
```

---

## フェーズ2: バックエンド実装

### 2.1 API エンドポイント

| エンドポイント | メソッド | 説明 |
|---------------|---------|------|
| `/` | GET | メインページ表示 |
| `/api/game/new` | POST | 新規ゲーム開始 |
| `/api/game/state` | GET | 現在の状態取得 |
| `/api/game/input` | POST | ユーザー入力送信 |
| `/ws` | WebSocket | リアルタイム更新 |

### 2.2 WebSocket イベント

```javascript
// サーバー → クライアント
{
  "type": "state_update",
  "data": { /* GameEngine.get_state() */ }
}

{
  "type": "input_required",
  "data": { /* InputRequest */ }
}

{
  "type": "animation",
  "data": { "type": "card_play", "card": "S06", "player": "P1" }
}

// クライアント → サーバー
{
  "type": "input",
  "data": { "response": /* 選択結果 */ }
}
```

---

## フェーズ3: フロントエンド実装

### 3.1 画面レイアウト

```
┌─────────────────────────────────────────────────────────┐
│ ヘッダー: ラウンド表示 | フェーズ表示 | 設定ボタン      │
├───────────────────────┬─────────────────────────────────┤
│                       │                                 │
│   対戦相手エリア       │    ゲームログ                   │
│   (CPU 3人の情報)      │    (スクロール可能)             │
│                       │                                 │
├───────────────────────┤                                 │
│                       │                                 │
│   プレイエリア         │                                 │
│   (トリック表示)       │                                 │
│   (カード選択UI)       │                                 │
│                       │                                 │
├───────────────────────┤                                 │
│                       │                                 │
│   自分の手札           │    プレイヤー情報               │
│   (インタラクティブ)   │    (金貨/VP/恩寵/ワーカー)       │
│                       │                                 │
└───────────────────────┴─────────────────────────────────┘
```

### 3.2 カード表示システム

```css
/* カード基本スタイル */
.card {
  --card-width: 80px;
  --card-height: 112px;
  --card-border-radius: 8px;

  width: var(--card-width);
  height: var(--card-height);
  border-radius: var(--card-border-radius);
  background: var(--card-bg-url, linear-gradient(135deg, #fff 0%, #f0f0f0 100%));
}

/* スート別カラー */
.card[data-suit="spade"] { --suit-color: #1a1a2e; }
.card[data-suit="heart"] { --suit-color: #e74c3c; }
.card[data-suit="diamond"] { --suit-color: #3498db; }
.card[data-suit="club"] { --suit-color: #27ae60; }
.card[data-suit="trump"] { --suit-color: #f39c12; }
```

### 3.3 インタラクション定義

| フェーズ | 入力タイプ | UI要素 |
|---------|-----------|--------|
| declaration | セレクト | スライダー + 数字表示 |
| seal | カード選択 | 手札からドラッグ or クリック |
| choose_card | カード選択 | 手札クリック（合法カードハイライト） |
| grace_hand_swap | カード選択 | チェックボックス付きカード |
| upgrade | 選択 | カードグリッド（効果説明付き） |
| fourth_place_bonus | 選択 | 2つの大きなボタン |
| worker_actions | 複数選択 | ドラッグ&ドロップ or ボタン |

---

## フェーズ4: ゲーム正常動作確認項目

### 4.1 カード処理

- [ ] カード配布（5枚×4人）が正しく行われる
- [ ] 切り札（Trump）が正しく1枚ずつ配布される
- [ ] 手札が正しく表示される
- [ ] 封印カードが正しく除外される

### 4.2 トリックテイキング

- [ ] リードスート判定が正しい
- [ ] マストフォロー判定が正しい
- [ ] 合法カードのみ選択可能
- [ ] トリック勝者判定が正しい（最高ランク、同ランクは親優先）
- [ ] トリック履歴が正しく記録される

### 4.3 宣言システム

- [ ] 0-4の範囲で宣言可能
- [ ] 宣言成功/失敗判定が正しい
- [ ] 宣言成功ボーナス（+1VP）が付与される
- [ ] 宣言0成功で恩寵ボーナス

### 4.4 アップグレード処理

| カード | 効果 | 確認項目 |
|--------|------|---------|
| UP_TRADE | 交易Lv+1 | yield: 2→4→6 |
| UP_HUNT | 討伐Lv+1 | yield: 1→2→3 |
| UP_PRAY | 祈りLv+1 | yield: 1→2→3 |
| RECRUIT_INSTANT | +2ワーカー | 即座に追加 |
| RECRUIT_WAGE_DISCOUNT | 給料軽減 | -1金/ラウンド |
| UP_DONATE | 寄付解放 | 2金→1恩寵 |
| UP_RITUAL | 儀式解放 | 1ワーカー→1恩寵 |

### 4.5 魔女カード処理（ラウンド3のみ）

| カード | 効果 | 確認項目 |
|--------|------|---------|
| WITCH_BLACKROAD | TRADE+2金 | 交易時に追加 |
| WITCH_BLOODHUNT | HUNT+1VP | 討伐時に追加 |
| WITCH_HERD | 給料-1 | 給料計算時 |
| WITCH_TREASURE | 1金→1恩寵 | ワーカー配置時 |
| WITCH_BLESSING | 毎ラウンド+1恩寵 | ラウンド開始時 |
| WITCH_PROPHET | 宣言成功+1金 | 宣言判定時 |
| WITCH_ZERO_MASTER | 宣言0成功+2恩寵 | 宣言0判定時 |

### 4.6 ワーカーアクション

- [ ] TRADE: 2+2×Lv 金貨獲得
- [ ] HUNT: 1+Lv VP獲得
- [ ] RECRUIT: 2金消費、ワーカー+1
- [ ] PRAY: 1+Lv 恩寵獲得
- [ ] DONATE: 2金+1ワーカー→1恩寵
- [ ] RITUAL: 1ワーカー→1恩寵

### 4.7 給料・負債処理

- [ ] WAGE_CURVE: [1,1,2,2,2,3] 適用
- [ ] 基本ワーカーのみ給料発生
- [ ] 雇用ワーカーは給料不要
- [ ] RECRUIT_WAGE_DISCOUNT で-1
- [ ] WITCH_HERD で-1
- [ ] 負債時: ×2ペナルティ（10VP上限）
- [ ] 4位救済: 2金 or 2恩寵

### 4.8 恩寵システム

- [ ] 手札交換: 1恩寵消費
- [ ] 閾値ボーナス: 13点→+8VP、10点→+5VP
- [ ] 0トリック勝利: +1恩寵
- [ ] 宣言0成功: +1恩寵
- [ ] 4位救済: +2恩寵選択可

### 4.9 ゲーム終了・得点計算

- [ ] 6ラウンド終了で終了
- [ ] 金貨→VP変換（2金=1VP）
- [ ] 恩寵閾値ボーナス適用
- [ ] 最終ランキング表示
- [ ] 同点時の処理

---

## フェーズ5: UI切り替え機能

### 5.1 起動オプション

```bash
# 既存Streamlit UI
uv run streamlit run streamlit_app.py

# 新リッチUI
uv run python run_rich_ui.py

# または
uv run python main.py --rich-ui
```

### 5.2 設定ファイル

```python
# config.py
UI_MODE = "streamlit"  # or "rich"
RICH_UI_PORT = 8080
```

---

## フェーズ6: テスト計画

### 6.1 自動テスト

```python
# test_rich_ui.py
async def test_100_games():
    """100ゲーム自動実行テスト"""
    for seed in range(100):
        game = await create_game(seed=seed, all_bots=True)
        while not game.game_over:
            await game.step()
        assert game.is_valid_end_state()
```

### 6.2 手動テスト項目

- [ ] 各フェーズの画面遷移
- [ ] カード選択のインタラクション
- [ ] アニメーションの動作
- [ ] エラー処理（不正入力時）
- [ ] ブラウザ互換性（Chrome, Firefox, Safari, Edge）
- [ ] レスポンシブデザイン（モバイル対応）

---

## 作業スケジュール

### Week 1: 基盤構築
- [ ] FastAPIサーバー基本実装
- [ ] WebSocket通信実装
- [ ] 基本HTML/CSSテンプレート

### Week 2: コア機能
- [ ] ゲーム状態表示
- [ ] カード表示システム
- [ ] 基本インタラクション

### Week 3: 全フェーズ対応
- [ ] 全7種類の入力タイプ実装
- [ ] アニメーション追加
- [ ] ログ表示

### Week 4: テスト・修正
- [ ] 100ゲームテスト
- [ ] バグ修正
- [ ] パフォーマンス最適化

---

## リスクと対策

| リスク | 対策 |
|-------|------|
| 既存ロジックとの不整合 | GameEngineを変更せず、APIレイヤーで吸収 |
| WebSocket切断 | 再接続ロジック実装、状態復元機能 |
| ブラウザ互換性 | モダンブラウザ対象、Polyfill最小限 |
| パフォーマンス | 仮想DOM不使用、直接DOM操作最適化 |

---

## 成功基準

1. **機能完全性**: 全ゲームルールが正しく動作
2. **安定性**: 100ゲーム連続実行でエラーなし
3. **UX**: インタラクションが直感的
4. **保守性**: カード画像差し替えが容易
5. **切り替え**: 既存UIと簡単に切り替え可能
