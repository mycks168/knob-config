"""hid モジュールのテスト。"""
import os

import pytest

from knob_config import hid


def test_build_report_pads_to_65_bytes():
    """レポートIDが先頭に付き、64バイトにゼロ埋めされること。"""
    r = hid.build_report([0xFD, 1, 2])
    assert len(r) == 65
    assert r[:4] == bytes([0x03, 0xFD, 1, 2])
    assert r[4:] == bytes(61)


def test_build_report_rejects_long_payload():
    """64バイトを超えるペイロードはエラーになること。"""
    with pytest.raises(ValueError):
        hid.build_report(bytes(65))


def test_read_request_format():
    """読み出し要求が 03 fa 19 00 <レイヤー> になること。"""
    assert hid.read_request(1)[:5] == bytes([0x03, 0xFA, 0x19, 0x00, 0x01])


def test_parse_entry_media():
    """メディアキーの応答を正しく解析できること。"""
    raw = bytes([3, 0xFA, 3, 1, 2, 1, 2, 0, 0, 0xE2]) + bytes(55)
    e = hid.parse_entry(raw)
    assert e['key'] == 3 and e['layer'] == 1 and e['kind'] == 2
    assert e['kind_name'] == 'メディア'
    assert e['raw'] == '03 fa 03 01 02 01 02 00 00 e2'


@pytest.mark.parametrize('raw', [b'', bytes([3, 0xFD, 1, 1, 1, 1, 1]), bytes([2, 0xFA, 1, 1, 1, 1, 1])])
def test_parse_entry_rejects_other(raw):
    """読み出し応答以外は None になること。"""
    assert hid.parse_entry(raw) is None


def test_parse_entry_unknown_kind():
    """未知の種類は『不明』と表示されること。"""
    assert hid.parse_entry(bytes([3, 0xFA, 1, 1, 9, 0, 0]))['kind_name'] == '不明(9)'


def _make_hidraw(root, name, devname, desc):
    """テスト用に sysfs の hidraw 構造を作る。"""
    dev = root / 'devices' / devname
    dev.mkdir(parents=True)
    (dev / 'report_descriptor').write_bytes(desc)
    node = root / 'class' / name
    node.mkdir(parents=True)
    os.symlink(dev, node / 'device')


def test_find_hidraw_picks_vendor_interface(tmp_path):
    """ベンダー定義インターフェースの hidraw だけが選ばれること。"""
    _make_hidraw(tmp_path, 'hidraw0', '0003:222A:0001.0001', b'\x06\x00\xff')
    _make_hidraw(tmp_path, 'hidraw3', '0003:514C:8850.0009', b'\x05\x01\x09\x06')
    _make_hidraw(tmp_path, 'hidraw2', '0003:514C:8850.000A', b'\x06\x00\xff\x09\x01')
    (tmp_path / 'class' / 'hidraw9').mkdir()  # device が無いノードは無視
    assert hid.find_hidraw(str(tmp_path / 'class')) == '/dev/hidraw2'


def test_find_hidraw_none(tmp_path):
    """見つからなければ None を返すこと。"""
    assert hid.find_hidraw(str(tmp_path)) is None


def test_device_send_receive(monkeypatch):
    """パイプを使って Device の送受信と破棄が動くこと。"""
    r, w = os.pipe()
    dev = hid.Device.__new__(hid.Device)
    dev.fd = w
    dev.send(b'abc', wait=0)
    reader = hid.Device.__new__(hid.Device)
    reader.fd = r
    assert reader.receive_all(timeout=0.05) == [b'abc']
    os.write(w, b'old')
    reader.drain()
    assert reader.receive_all(timeout=0.05) == []
    dev.close()
    reader.close()


def test_device_open(tmp_path):
    """Device がファイルを開いて閉じられること。"""
    p = tmp_path / 'f'
    p.write_bytes(b'')
    d = hid.Device(str(p))
    d.close()
