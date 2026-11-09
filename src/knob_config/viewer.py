"""ダイアルの入力イベントをリアルタイム表示するビューア（Ctrl+C で終了）。"""
import glob
import select
import struct
import time

EVENT_FMT = 'llHHi'
EVENT_SIZE = struct.calcsize(EVENT_FMT)
DEVICE_NAME = 'USB Composite Device'

EV_SYN, EV_KEY, EV_REL, EV_MSC = 0, 1, 2, 4
REL_HWHEEL_HI_RES, REL_WHEEL_HI_RES = 12, 11
REL_WHEEL = 8

KEY_NAMES = {113: 'ミュート', 114: '音量ダウン', 115: '音量アップ',
             163: '次の曲', 164: '再生/停止', 165: '前の曲',
             272: '左クリック', 273: '右クリック', 274: '中クリック'}
REL_NAMES = {0: 'マウス横移動', 1: 'マウス縦移動', 6: '横スクロール', 8: 'スクロール'}


def device_name(path, sysfs_root='/sys/class/input'):
    """イベントデバイスの名前を sysfs から取得する。"""
    node = path.rsplit('/', 1)[-1]
    try:
        with open(f'{sysfs_root}/{node}/device/name') as f:
            return f.read().strip()
    except OSError:
        return '?'


def describe(etype, code, value):
    """イベント1件を人が読める文字列に変換する。表示不要なら None を返す。"""
    if etype in (EV_SYN, EV_MSC):
        return None
    if etype == EV_KEY:
        if value == 2:  # キーリピートは省略
            return None
        state = '押した' if value == 1 else '離した'
        return f'{KEY_NAMES.get(code, f"キー code={code}")}  [{state}]'
    if etype == EV_REL:
        if code in (REL_WHEEL_HI_RES, REL_HWHEEL_HI_RES):  # 高精度スクロールは重複なので省略
            return None
        name = REL_NAMES.get(code, f'相対移動 code={code}')
        if code == REL_WHEEL:
            return f'{name} {"上" if value > 0 else "下"} ({value})'
        return f'{name} {value:+d}'
    return f'その他 type={etype} code={code} value={value}'


def find_devices(pattern='/dev/input/event*', name_of=device_name):
    """ダイアルのイベントデバイスのパス一覧を返す。"""
    return [p for p in sorted(glob.glob(pattern)) if DEVICE_NAME in name_of(p)]


def main():
    """対象デバイスを開いてイベントを表示し続ける。"""
    paths = find_devices()
    if not paths:
        print(f'ノブが見つかりません（{DEVICE_NAME}）')
        return 1
    fds = {open(p, 'rb', buffering=0): p for p in paths}
    for p in paths:
        print(f'監視中: {p}  ({device_name(p)})')
    print('ノブを操作してください（Ctrl+C で終了）\n', flush=True)
    try:
        while True:
            ready, _, _ = select.select(list(fds), [], [])
            for f in ready:
                _, _, etype, code, value = struct.unpack(EVENT_FMT, f.read(EVENT_SIZE))
                text = describe(etype, code, value)
                if text:
                    print(f'{time.strftime("%H:%M:%S")}  {text}', flush=True)
    except KeyboardInterrupt:
        print('\n終了')
    return 0
