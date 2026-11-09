"""本体の現在のキー設定を読み出して表示する（読み出し専用）。"""
import argparse
import sys

from .hid import Device, find_hidraw, parse_entry, read_request


def format_entry(entry):
    """解析済みエントリを1行の文字列にする。"""
    return f"キー{entry['key']:2d}  {entry['kind_name']:<6}  {entry['raw']}"


def read_layer(dev, layer):
    """指定レイヤーの設定を読み出し、解析済みエントリのリストを返す。"""
    dev.drain()
    dev.send(read_request(layer))
    entries = [parse_entry(r) for r in dev.receive_all()]
    return [e for e in entries if e and e['layer'] == layer]


def main(argv=None):
    """コマンドライン引数を解釈して設定を表示する。"""
    p = argparse.ArgumentParser(description='本体の現在の設定を読み出す')
    p.add_argument('--device', help='hidraw デバイス（省略時は自動検出）')
    p.add_argument('--layer', type=int, default=1, help='レイヤー（1始まり、既定 1）')
    p.add_argument('--keys', type=int, default=8, help='表示するキー数（既定 8）')
    a = p.parse_args(argv)
    path = a.device or find_hidraw()
    if not path:
        print('ノブが見つかりません', file=sys.stderr)
        return 1
    dev = Device(path)
    try:
        entries = read_layer(dev, a.layer)
    finally:
        dev.close()
    for e in entries[:a.keys]:
        print(format_entry(e))
    return 0
