"""本体の設定用HIDインターフェースとのやり取り（パケット生成・送受信）。"""
import glob
import os
import select
import time

from . import PRODUCT_ID, REPORT_ID, REPORT_SIZE, VENDOR_ID

CMD_READ = 0xFA   # 設定読み出し
CMD_WRITE = 0xFD  # 設定書き込み
COMMIT = bytes([CMD_WRITE, 0xFE, 0xFF])  # 書き込み確定

KIND_NAMES = {0: '空', 1: 'キーボード', 2: 'メディア', 3: 'マウス'}


def build_report(payload):
    """ペイロードの先頭にレポートIDを付け、64バイトにゼロ埋めしたレポートを返す。"""
    if len(payload) > REPORT_SIZE:
        raise ValueError('ペイロードが長すぎます')
    return bytes([REPORT_ID]) + bytes(payload) + bytes(REPORT_SIZE - len(payload))


def read_request(layer):
    """指定レイヤー（1始まり）の設定を要求するレポートを返す。

    公式アプリは 03 fa 19 00 <レイヤー> を送り、本体はそのレイヤーの全キーを返す。
    """
    return build_report([CMD_READ, 0x19, 0x00, layer])


def parse_entry(report):
    """読み出し応答1件を辞書に変換する。応答でなければ None を返す。"""
    if len(report) < 7 or report[0] != REPORT_ID or report[1] != CMD_READ:
        return None
    return {
        'key': report[2],
        'layer': report[3],
        'kind': report[4],
        'kind_name': KIND_NAMES.get(report[4], f'不明({report[4]})'),
        'raw': bytes(report).rstrip(b'\0').hex(' '),
    }


def find_hidraw(sysfs_root='/sys/class/hidraw'):
    """設定用インターフェース（ベンダー定義）の /dev/hidrawN を探して返す。"""
    target = f'{VENDOR_ID:04X}:{PRODUCT_ID:04X}'
    for node in sorted(glob.glob(f'{sysfs_root}/hidraw*')):
        try:
            with open(f'{node}/device/report_descriptor', 'rb') as f:
                desc = f.read()
        except OSError:
            continue
        # ベンダー定義ページ(06 00 ff)を持つ方が設定用
        if target in os.path.realpath(f'{node}/device') and desc.startswith(b'\x06\x00\xff'):
            return '/dev/' + os.path.basename(node)
    return None


class Device:
    """hidraw デバイスを開いてレポートを送受信する。"""

    def __init__(self, path):
        """デバイスを読み書きモードで開く。"""
        self.fd = os.open(path, os.O_RDWR)

    def close(self):
        """デバイスを閉じる。"""
        os.close(self.fd)

    def drain(self):
        """受信済みの古いデータを捨てる。"""
        while select.select([self.fd], [], [], 0.1)[0]:
            os.read(self.fd, REPORT_SIZE + 1)

    def send(self, report, wait=0.05):
        """レポートを1件送信する。"""
        os.write(self.fd, report)
        time.sleep(wait)

    def receive_all(self, timeout=0.3):
        """タイムアウトまで届いたレポートをすべて返す。"""
        out = []
        while select.select([self.fd], [], [], timeout)[0]:
            out.append(os.read(self.fd, REPORT_SIZE + 1))
        return out
