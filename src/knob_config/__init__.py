"""二層ノブ（514c:8850）用の設定ツール群。"""

VENDOR_ID = 0x514C
PRODUCT_ID = 0x8850
REPORT_ID = 0x03
REPORT_SIZE = 64  # レポートIDを除いたペイロード長


def main():
    """使えるコマンドの一覧を表示する。"""
    print('使えるコマンド:')
    print('  knob-view   入力イベントをリアルタイム表示')
    print('  knob-write  設定ファイルを本体に書き込む（要sudo）')
    print('  knob-read   本体の現在の設定を読み出す（要sudo）')
