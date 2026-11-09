"""keymap / writer のテスト。"""
import pytest

from knob_config import keymap, writer


@pytest.mark.parametrize('action,kind,body', [
    ('none', 0, b''),
    ('mute', 2, bytes([0, 2, 0, 0, 0xE2, 0, 0, 0])),
    ('volumeup', 2, bytes([0, 2, 0, 0, 0xE9, 0, 0, 0])),
    ('a', 1, bytes([0, 1, 0, 0, 0x04])),
    ('0', 1, bytes([0, 1, 0, 0, 0x27])),
    ('f1', 1, bytes([0, 1, 0, 0, 0x3A])),
    ('ctrl+c', 1, bytes([0, 2, 0, 0, 0xF1, 0, 0, 0x06])),
    ('Ctrl+Shift+Space', 1, bytes([0, 3, 0, 0, 0xF1, 0, 0, 0xF2, 0, 0, 0x2C])),
    ('click', 3, bytes([1, 4]) + bytes([0, 0, 0, 0, 0, 1]) + bytes(9)),
    ('wheelup', 3, bytes([1, 4]) + bytes(12) + bytes([0, 0, 1])),
    ('wheeldown', 3, bytes([1, 4]) + bytes(12) + bytes([0, 0, 0xFF])),
])
def test_encode_action(action, kind, body):
    """各割り当て名が本体の形式に変換されること。"""
    assert keymap.encode_action(action) == (kind, body)


@pytest.mark.parametrize('action', ['foo', 'hyper+a', 'ctrl+', ''])
def test_encode_action_unknown(action):
    """知らない名前はエラーになること。"""
    with pytest.raises(ValueError):
        keymap.encode_action(action)


def test_write_payload():
    """ヘッダ（コマンド・キー番号・レイヤー・種類）が付くこと。"""
    assert keymap.write_payload(3, 1, 'mute')[:4] == bytes([0xFD, 3, 1, 2])


def test_parse_config():
    """ノブ名と操作名がキー番号に変換され、番号順に並ぶこと。"""
    conf = {'lower': {'right': 'next'}, 'upper': {'press': 'mute', 'left': 'volumedown'}}
    assert keymap.parse_config(conf) == [(2, 'volumedown'), (3, 'mute'), (8, 'next')]


@pytest.mark.parametrize('conf', [
    None, [], {'middle': {'left': 'a'}}, {'upper': 'a'},
    {'lower': {'press': 'a'}}, {'upper': {'left': 'foo'}},
])
def test_parse_config_errors(conf):
    """間違った設定はエラーになること。"""
    with pytest.raises(ValueError):
        keymap.parse_config(conf)


def test_action_names():
    """一覧にそれぞれの種類が含まれること。"""
    names = keymap.action_names()
    assert 'mute' in names['メディア'] and 'wheelup' in names['マウス']
    assert 'ctrl+<キー>' in names['キーボード'] and names['割り当てなし'] == ['none']


class FakeDevice:
    """送信を記録し、読み戻し要求には決まった応答を返す偽デバイス。"""

    def __init__(self, kinds):
        """キー番号 → 種類 の辞書で応答を用意する。"""
        self.kinds, self.sent, self.closed = kinds, [], False

    def drain(self):
        """何もしない。"""

    def send(self, report, wait=0.05):
        """送信を記録する。"""
        self.sent.append(report)

    def receive_all(self, timeout=0.3):
        """読み戻し応答を返す。"""
        return [bytes([3, 0xFA, k, 1, v, 0, 0]) for k, v in self.kinds.items()]

    def close(self):
        """閉じたことを記録する。"""
        self.closed = True


def _config(tmp_path, text):
    """一時設定ファイルを作ってパスを返す。"""
    p = tmp_path / 'knob.yaml'
    p.write_text(text, encoding='utf-8')
    return str(p)


def test_write_and_verify():
    """書き込み後に確定コマンドが送られ、種類が一致すれば問題なしになること。"""
    dev = FakeDevice({3: 2, 7: 3})
    items = [(3, 'mute'), (7, 'wheelup')]
    writer.write(dev, items)
    assert [r[1:3] for r in dev.sent] == [bytes([0xFD, 3]), bytes([0xFD, 7]), bytes([0xFD, 0xFE])]
    assert writer.verify(dev, items) == []
    assert writer.verify(dev, [(3, 'a')]) == [3]


def test_main_list(capsys):
    """--list で割り当て名が表示されること。"""
    assert writer.main(['--list']) == 0
    assert 'volumeup' in capsys.readouterr().out


def test_main_check(tmp_path, capsys):
    """--check で書き込まずに確認だけすること。"""
    assert writer.main([_config(tmp_path, 'upper:\n  press: mute\n'), '--check']) == 0
    assert '問題はありません' in capsys.readouterr().out


@pytest.mark.parametrize('text', ['upper:\n  press: foo\n', 'upper: [\n'])
def test_main_bad_config(tmp_path, text, capsys):
    """設定ファイルが間違っていればエラー終了すること。"""
    assert writer.main([_config(tmp_path, text)]) == 1
    assert 'エラー' in capsys.readouterr().err


def test_main_missing_file(tmp_path):
    """設定ファイルが無ければエラー終了すること。"""
    assert writer.main([str(tmp_path / 'none.yaml')]) == 1


def test_main_not_found(tmp_path, monkeypatch):
    """ノブが無ければエラー終了すること。"""
    monkeypatch.setattr(writer, 'find_hidraw', lambda: None)
    assert writer.main([_config(tmp_path, 'upper:\n  press: mute\n')]) == 1


@pytest.mark.parametrize('kinds,code,msg', [({3: 2}, 0, '完了'), ({3: 1}, 1, '一致しない')])
def test_main_write(tmp_path, monkeypatch, capsys, kinds, code, msg):
    """書き込み・読み戻しの結果に応じた終了コードになること。"""
    dev = FakeDevice(kinds)
    monkeypatch.setattr(writer, 'Device', lambda p: dev)
    assert writer.main([_config(tmp_path, 'upper:\n  press: mute\n'), '--device', '/dev/x']) == code
    out = capsys.readouterr()
    assert msg in out.out + out.err
    assert dev.closed
