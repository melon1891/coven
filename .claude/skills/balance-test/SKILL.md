# balance-test

Description: バランステスト一括実行。全シミュレーションを走らせて結果を要約レポートとして出力する。
User-invocable: true

## Instructions

テストプレイ後のバランス確認を一括で実施する。以下の手順を順番に実行すること。

### 1. 動作確認（自動実行モード）
```bash
PYTHONIOENCODING=utf-8 uv run python main.py --auto
```
エラーが出た場合はここで中断し、原因を報告する。

### 2. 恩寵バランスシミュレーション
```bash
PYTHONIOENCODING=utf-8 uv run python main.py --simulate-grace
```

### 3. カードランクシミュレーション
```bash
PYTHONIOENCODING=utf-8 uv run python main.py --simulate
```

### 4. 負債ペナルティシミュレーション
```bash
PYTHONIOENCODING=utf-8 uv run python main.py --simulate-debt-penalty
```

**注意**: ステップ2〜4は互いに独立しているため、可能なら並列実行する。

### 5. 要約レポート
全シミュレーション完了後、以下の項目を含む要約レポートをユーザーに提示する:

- **動作確認**: OK / NG
- **恩寵バランス**: 平均恩寵ポイント、ボーナス獲得率、平均ボーナスVP、評価結果
- **カードランク**: 推奨ランク範囲、平均VP差
- **負債ペナルティ**: 推奨設定、負債発生率、勝者平均VP
- **総合評価**: バランスの問題点があれば指摘
