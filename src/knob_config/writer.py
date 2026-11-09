"""設定ファイルの割り当てを本体に書き込む。"""
import argparse
import sys

import yaml

from .hid import COMMIT, Device, build_report, find_hidraw
from .keymap import action_names, encode_action, parse_config, write_payload
from .readcfg import read_layer

LAYER = 1  # この製品はレイヤー1だけを使う


def load(path):
    """YAML 設定ファイルを読み込んで [(キー番号, 割り当て)] を返す。"""
    with open(path, encoding='utf-8') as f:
        return parse_config(yaml.safe_load(f))


def write(dev, items):
    """割り当てを書き込み、最後に確定コマンドを送る。"""
    for key, action in items:
        dev.send(build_report(write_payload(key, LAYER, action)))
    dev.send(build_report(COMMIT))


def verify(dev, items):
    """読み戻して、各キーの種類が書き込んだ通りか確かめる。食い違ったキー番号を返す。"""
    kinds = {e['key']: e['kind'] for e in read_layer(dev, LAYER)}
    return [key for key, action in items if kinds.get(key) != encode_action(action)[0]]


def main(argv=None):
    """コマンドライン引数を解釈して書き込む。"""
    p = argparse.ArgumentParser(description='設定ファイルの割り当てを本体に書き込む')
    p.add_argument('config', nargs='?', default='config/knob.yaml', help='設定ファイル')
    p.add_argument('--device', help='hidraw デバイス（省略時は自動検出）')
    p.add_argument('--check', action='store_true', help='設定ファイルの確認だけして書き込まない')
    p.add_argument('--list', action='store_true', help='使える割り当て名を表示する')
    a = p.parse_args(argv)
    if a.list:
        for group, names in action_names().items():
            print(f'{group}: {" ".join(names)}')
        return 0
    try:
        items = load(a.config)
    except (OSError, ValueError, yaml.YAMLError) as e:
        print(f'設定ファイルのエラー: {e}', file=sys.stderr)
        return 1
    if a.check:
        print('設定ファイルに問題はありません')
        return 0
    path = a.device or find_hidraw()
    if not path:
        print('ノブが見つかりません', file=sys.stderr)
        return 1
    dev = Device(path)
    try:
        write(dev, items)
        bad = verify(dev, items)
    finally:
        dev.close()
    if bad:
        print(f'書き込み後の読み戻しが一致しないキーがあります: {bad}', file=sys.stderr)
        return 1
    print(f'書き込み完了（{len(items)}か所、読み戻して確認済み）')
    return 0
