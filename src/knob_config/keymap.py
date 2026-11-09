"""設定ファイルの割り当て（文字列）を、本体へ送る書き込みデータに変換する。"""
from .hid import CMD_WRITE

# 操作名 → 本体のキー番号
SLOTS = {
    ('upper', 'left'): 2,
    ('upper', 'press'): 3,
    ('upper', 'right'): 4,
    ('upper', 'press_left'): 5,
    ('upper', 'press_right'): 6,
    ('lower', 'left'): 7,
    ('lower', 'right'): 8,
}

KIND_NONE, KIND_KEYBOARD, KIND_MEDIA, KIND_MOUSE = 0, 1, 2, 3

# 修飾キー → 本体用の修飾コード
MODIFIERS = {'ctrl': 0xF1, 'shift': 0xF2, 'alt': 0xF3, 'win': 0xF4}

# メディアキー → コンシューマ用途コード（HID Usage Page 0x0C）
MEDIA = {
    'volumeup': 0xE9, 'volumedown': 0xEA, 'mute': 0xE2,
    'play': 0xCD, 'next': 0xB5, 'prev': 0xB6, 'stop': 0xB7,
}

# マウス操作 → (ボタン, 縦移動ではなくホイール量)
MOUSE_CLICK = {'click': 1, 'rightclick': 2, 'middleclick': 4}
MOUSE_WHEEL = {'wheelup': 1, 'wheeldown': -1}


def _keyboard_codes():
    """キー名 → HID キーボード用途コードの表を作る。"""
    codes = {chr(ord('a') + i): 0x04 + i for i in range(26)}
    codes.update({str((i + 1) % 10): 0x1E + i for i in range(10)})
    codes.update({f'f{i}': 0x39 + i for i in range(1, 13)})
    codes.update({
        'enter': 0x28, 'esc': 0x29, 'backspace': 0x2A, 'tab': 0x2B, 'space': 0x2C,
        'insert': 0x49, 'home': 0x4A, 'pageup': 0x4B, 'delete': 0x4C, 'end': 0x4D,
        'pagedown': 0x4E, 'right': 0x4F, 'left': 0x50, 'down': 0x51, 'up': 0x52,
    })
    return codes


KEYBOARD = _keyboard_codes()


def action_names():
    """設定ファイルで使える割り当て名の一覧を返す。"""
    return {
        'キーボード': sorted(KEYBOARD) + [f'{m}+<キー>' for m in MODIFIERS],
        'メディア': sorted(MEDIA),
        'マウス': sorted(MOUSE_CLICK) + sorted(MOUSE_WHEEL),
        '割り当てなし': ['none'],
    }


def encode_action(action):
    """割り当て文字列を (種類, 種類以降のバイト列) に変換する。

    例: 'mute' → メディア、'ctrl+c' → キーボード、'wheelup' → マウス、'none' → 空。
    不明な名前なら ValueError を送出する。
    """
    name = str(action).strip().lower()
    if name == 'none':
        return KIND_NONE, b''
    if name in MEDIA:
        code = MEDIA[name]
        # 16ビットの用途コードを、2つのグループの値に下位・上位の順で入れる
        return KIND_MEDIA, bytes([0, 2, 0, 0, code & 0xFF, 0, 0, code >> 8])
    if name in MOUSE_CLICK or name in MOUSE_WHEEL:
        groups = [0] * 5  # 修飾・ボタン・横移動・縦移動・ホイール
        if name in MOUSE_CLICK:
            groups[1] = MOUSE_CLICK[name]
        else:
            groups[4] = MOUSE_WHEEL[name] & 0xFF
        body = bytes([1, 4])  # 修飾グループ1つ＋データグループ4つ
        return KIND_MOUSE, body + b''.join(bytes([0, 0, g]) for g in groups)
    *mods, key = name.split('+')
    if key not in KEYBOARD or any(m not in MODIFIERS for m in mods):
        raise ValueError(f'不明な割り当て名です: {action}')
    groups = [MODIFIERS[m] for m in mods] + [KEYBOARD[key]]
    return KIND_KEYBOARD, bytes([0, len(groups)]) + b''.join(bytes([0, 0, g]) for g in groups)


def write_payload(key, layer, action):
    """1キー分の書き込みペイロード（レポートIDを除く）を返す。"""
    kind, body = encode_action(action)
    return bytes([CMD_WRITE, key, layer, kind]) + body


def parse_config(conf):
    """設定（辞書）を検証し、[(キー番号, 割り当て)] のリストにする。

    ノブ名・操作名・割り当て名が間違っていれば ValueError を送出する。
    """
    if not isinstance(conf, dict):
        raise ValueError('設定ファイルの形式が正しくありません')
    result = []
    for knob, ops in conf.items():
        if knob not in ('upper', 'lower') or not isinstance(ops, dict):
            raise ValueError(f'ノブ名は upper か lower で指定してください: {knob}')
        for op, action in ops.items():
            if (knob, op) not in SLOTS:
                raise ValueError(f'{knob} に {op} という操作はありません')
            encode_action(action)  # 名前の確認
            result.append((SLOTS[(knob, op)], action))
    return sorted(result)
