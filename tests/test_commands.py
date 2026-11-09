"""readcfg / viewer / パッケージ本体のテスト。"""
import io

import pytest

import knob_config
from knob_config import readcfg, viewer


class FakeDevice:
    """送信内容を記録し、決まった応答を返す偽デバイス。"""

    def __init__(self, replies=()):
        """応答を受け取って初期化する。"""
        self.sent, self.replies, self.closed = [], list(replies), False

    def drain(self):
        """何もしない。"""

    def send(self, report, wait=0.05):
        """送信内容を記録する。"""
        self.sent.append(report)

    def receive_all(self, timeout=0.3):
        """用意した応答を返す。"""
        return self.replies

    def close(self):
        """閉じたことを記録する。"""
        self.closed = True


def _entry(key, layer, kind, code):
    """読み出し応答のバイト列を作る。"""
    return bytes([3, 0xFA, key, layer, kind, 1, 1, 0, 0, code]) + bytes(55)


def test_read_layer_filters_layer():
    """指定レイヤーの応答だけが返ること。"""
    dev = FakeDevice([_entry(2, 1, 2, 0xEA), _entry(2, 2, 2, 0xEA), b'junk'])
    es = readcfg.read_layer(dev, 1)
    assert [(e['key'], e['layer']) for e in es] == [(2, 1)]
    assert dev.sent[0][:5] == bytes([3, 0xFA, 0x19, 0, 1])


def test_format_entry():
    """表示用の1行が作れること。"""
    e = {'key': 2, 'kind_name': 'メディア', 'raw': '03 fa'}
    assert readcfg.format_entry(e).startswith('キー 2  メディア')


def test_readcfg_main(monkeypatch, capsys):
    """main がデバイスから読んで表示し、閉じること。"""
    dev = FakeDevice([_entry(k, 1, 1, 0x28) for k in range(1, 11)])
    monkeypatch.setattr(readcfg, 'Device', lambda p: dev)
    assert readcfg.main(['--device', '/dev/x', '--keys', '3']) == 0
    assert len(capsys.readouterr().out.splitlines()) == 3
    assert dev.closed


def test_readcfg_main_not_found(monkeypatch, capsys):
    """デバイスが無いときはエラー終了すること。"""
    monkeypatch.setattr(readcfg, 'find_hidraw', lambda: None)
    assert readcfg.main([]) == 1
    assert '見つかりません' in capsys.readouterr().err



@pytest.mark.parametrize('args,expected', [
    ((0, 0, 0), None),
    ((4, 4, 786658), None),
    ((1, 113, 1), 'ミュート  [押した]'),
    ((1, 113, 0), 'ミュート  [離した]'),
    ((1, 113, 2), None),
    ((1, 30, 1), 'キー code=30  [押した]'),
    ((2, 8, 1), 'スクロール 上 (1)'),
    ((2, 8, -1), 'スクロール 下 (-1)'),
    ((2, 11, 120), None),
    ((2, 0, 5), 'マウス横移動 +5'),
    ((2, 99, -2), '相対移動 code=99 -2'),
    ((3, 0, 1), 'その他 type=3 code=0 value=1'),
])
def test_describe(args, expected):
    """各種イベントが正しい文字列になること。"""
    assert viewer.describe(*args) == expected


def test_device_name(tmp_path):
    """sysfs から名前を読めること、無ければ ? になること。"""
    d = tmp_path / 'event8' / 'device'
    d.mkdir(parents=True)
    (d / 'name').write_text('USB Composite Device Keyboard\n')
    assert viewer.device_name('/dev/input/event8', str(tmp_path)) == 'USB Composite Device Keyboard'
    assert viewer.device_name('/dev/input/event1', str(tmp_path)) == '?'


def test_find_devices(tmp_path):
    """名前に USB Composite Device を含むものだけ選ばれること。"""
    for n in ('event1', 'event8'):
        (tmp_path / n).write_bytes(b'')
    names = {'event1': 'HDMI', 'event8': 'USB Composite Device Keyboard'}
    found = viewer.find_devices(str(tmp_path / 'event*'), lambda p: names[p.rsplit('/', 1)[-1]])
    assert found == [str(tmp_path / 'event8')]


def test_viewer_main_not_found(monkeypatch, capsys):
    """デバイスが無いときはエラー終了すること。"""
    monkeypatch.setattr(viewer, 'find_devices', lambda: [])
    assert viewer.main() == 1
    assert '見つかりません' in capsys.readouterr().out


def test_viewer_main_loop(monkeypatch, tmp_path, capsys):
    """イベントを表示し、Ctrl+C で終了すること。"""
    import struct
    ev = tmp_path / 'event8'
    ev.write_bytes(struct.pack(viewer.EVENT_FMT, 0, 0, 1, 115, 1))
    monkeypatch.setattr(viewer, 'find_devices', lambda: [str(ev)])
    calls = {'n': 0}

    def fake_select(r, w, x):
        """1回目は読み込み可、2回目で Ctrl+C を発生させる。"""
        calls['n'] += 1
        if calls['n'] > 1:
            raise KeyboardInterrupt
        return r, [], []

    monkeypatch.setattr(viewer.select, 'select', fake_select)
    assert viewer.main() == 0
    out = capsys.readouterr().out
    assert '音量アップ  [押した]' in out and '終了' in out


def test_package_main(capsys):
    """コマンド一覧が表示されること。"""
    knob_config.main()
    assert 'knob-view' in capsys.readouterr().out
