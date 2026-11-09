# knob-config

通販などで売られている、**上下2段に重なったノブ型のメディアコントローラー**（Bluetooth名 `MINI_KEYBOARD`、USB ID `514c:8850`）の割り当てを、Linux から変更するツール。

このデバイスの割り当ては、本来はメーカー配布の設定アプリ（Windows / Mac 用）で変える。このツールを使うと、そのアプリを使わずに、Linux（Raspberry Pi など）から次のことができる。

- 各操作に割り当てるキーを書き込む
- 本体に今入っている割り当てを読み出す
- ノブを操作したときに、PC に何が届いているかをリアルタイムで見る

## 対象のデバイス

上のノブ（押し込みあり）と、下のノブの2段構成。それぞれ次の操作に、好きなキーを割り当てられる。

| 設定ファイルでの名前 | 操作 | 工場出荷時の割り当て |
|---|---|---|
| `upper.left` | 上のノブを左に回す | 音量ダウン |
| `upper.right` | 上のノブを右に回す | 音量アップ |
| `upper.press` | 上のノブを押す | ミュート |
| `upper.press_left` | 上のノブを押しながら左に回す | 前の曲 |
| `upper.press_right` | 上のノブを押しながら右に回す | 次の曲 |
| `lower.left` | 下のノブを左に回す | マウス系の操作（Linux では反応しない） |
| `lower.right` | 下のノブを右に回す | マウス系の操作（Linux では反応しない） |

`lsusb` で `514c:8850` と表示されれば、このツールの対象である。ただし、同じ USB ID でも中身が異なる製品があるため、まず「今の割り当てを読み出す」で中身を確認すること。

## 準備

[uv](https://docs.astral.sh/uv/) を使う。

```bash
git clone https://github.com/mycks168/knob-config.git ~/knob-config
cd ~/knob-config
uv sync
```

デバイスは **USB ケーブルでつないで、底の電源スイッチを OFF** にしておく。無線（Bluetooth・2.4G）接続のままだと、読み書きできない。

読み書きは、USB の生データを扱うから `sudo` が必要になる。

## 使い方

### 1. 今の割り当てを読み出す

```bash
sudo .venv/bin/knob-read
```

```
キー 2  メディア    03 fa 02 01 02 01 02 00 00 ea
キー 3  メディア    03 fa 03 01 02 01 02 00 00 e2
...
```

キー番号と操作の対応や、右側の数字の意味は [docs/protocol.md](docs/protocol.md) で説明してる。

### 2. 割り当てを書き換える

`config/knob.yaml` を編集する。

```yaml
upper:
  left: volumedown
  press: mute
  right: volumeup
  press_left: wheelup
  press_right: wheeldown

lower:
  left: prev
  right: next
```

書かなかった操作は、本体の今の割り当てのまま変わらない。使える割り当て名は、次のコマンドで確認できる。

```bash
uv run knob-write --list
```

| 種類 | 例 |
|---|---|
| キーボード | `a`、`enter`、`space`、`f5`、`ctrl+c`、`ctrl+shift+t` |
| メディア | `volumeup`、`volumedown`、`mute`、`play`、`next`、`prev` |
| マウス | `click`、`rightclick`、`wheelup`、`wheeldown` |
| 割り当てなし | `none` |

書き込む前に、設定ファイルが正しいかだけ確認することもできる。

```bash
uv run knob-write --check
```

本体に書き込む。書き込み後は自動で読み戻し、正しく反映されたかを確認する。

```bash
sudo .venv/bin/knob-write                 # config/knob.yaml を書き込む
sudo .venv/bin/knob-write 別の設定.yaml
```

### 3. 動作を確かめる

```bash
uv run knob-view
```

ノブを操作すると、PC に届いた入力が1行ずつ表示される。終わるときは Ctrl+C。

```
14:51:34  音量アップ  [押した]
14:51:34  音量アップ  [離した]
14:51:40  スクロール 上 (1)
```

## 注意点

- **上のノブの押し込みは、押しっぱなしにできない。** 押した瞬間ではなく、離した瞬間に「押す→離す」がまとめて送られる。本体の仕様だから、何を割り当てても変わらない
- 書き込んだ割り当ては本体に保存される。無線接続に切り替えても、別の PC につないでも、そのまま使える

## 参考にしたもの

- [ch57x-keyboard-tool](https://github.com/kriomant/ch57x-keyboard-tool)：同じ系統の中華製マクロキーボード用の設定ツール。特に [PR #191](https://github.com/kriomant/ch57x-keyboard-tool/pull/191) の書き込み形式を参考にした
- メーカー配布の設定アプリ（Mac 版）：実行はせずに中身を解析して、読み出しの方法とキー番号の割り当てを調べた

通信の詳しい仕様は [docs/protocol.md](docs/protocol.md) を参照。

## ライセンス

[MIT License](LICENSE)
