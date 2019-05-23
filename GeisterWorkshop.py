# coding:utf-8
"""
Geister program for Board game AI Workshop #1

© Morikatron Inc. 2019
written by matsubara@morikatron.co.jp

動作環境はPython 3.5以降。特別なライブラリは不要。
"""

from enum import Enum
from typing import List, Tuple, Union
import random
import re
import pickle

# ゲームの基本的な枠組みや表現に関する各種の定数を宣言
BOARD_WIDTH = 6  # ボードの幅
BOARD_HEIGHT = 6  # 高さ
MAX_PIECES = 8  # プレイヤーの持ち駒の数
ME = 0  # pieces[]リストの先頭はAIプレイヤー（自分=Me）の持ち駒とする
OP = 1  # pieces[]リストの2番目は敵プレイヤー（相手=Opponent）の持ち駒とする
NO_PLAYER = -1  # MEでもOPでもない場合に使う値
LOC_CAPTURED = 99  # xにLOC_CAPTUREDが入っていれば、そのコマは相手に取られたコマとする
LOC_ESCAPED_W = -1  # xにLOC_ESCAPED_Wが入っていれば、そのコマ（青のみだが）は敵陣地から抜け出た（勝った）コマとする
LOC_ESCAPED_E = BOARD_WIDTH  # xにLOC_ESCAPED_Eが入っていれば、そのコマ（青のみだが）は敵陣地から抜け出た（勝った）コマとする
COL_R = -1.0  # 赤
COL_B = 1.0  # 青
COL_U = 0.0  # 不明

CAPTURE_ABOVE_E_COLOR_ALL = COL_R + 0.1  # 「赤確実のコマは捕獲しない」ときに使う capture_above_e_color 値
CAPTURE_ABOVE_E_COLOR_ONLY_BLUE = COL_B  # 「青確実のコマなら捕獲する」ときに使う capture_above_e_color 値

# 表示制御に関する定数
"""
コンソールに盤面を表示すると、フォントによってはガタガタになります。
ですので、実行環境のフォントはできるだけ等幅フォントに設定してください。
Google Colaboratoryで実行する場合は、ブラウザの表示フォントを等幅に。
（Chromeには固定幅フォントの設定があります）
mac + PyCharmで実行する場合は、全角表示にするとわかりやすいです。(ZENKAKU = Trueに)
"""
ZENKAKU = False  # Trueにすると全角で表示。mac + PyCharmでは全角表示が快適です。
if ZENKAKU:
    CHAR_RED = 'ｒ'  # 'ⓡ'
    CHAR_BLUE = 'ｂ'  # 'ⓑ'
    CHAR_UNDEFINED = '？'  # '🅤'
    CHAR_SPACE = '・'
else:
    CHAR_RED = 'r'
    CHAR_BLUE = 'b'
    CHAR_UNDEFINED = '?'
    CHAR_SPACE = '-'


# ゲームの進行を保持・制御する列挙型を宣言
class GameState(Enum):
    enter_f_or_s = 0  # ゲームの開始待ち（どちらが先手か入力してもらう）
    enter_opponent_move = 1  # 相手の打ち手（x,y,direction）の入力待ち
    enter_color_of_captured_piece = 2  # AIがとったコマの色の入力待ち
    next_is_AI_move = 3  # 次はAIの番です
    won = 4  # AIの勝ち
    lost = 5  # AIの負け


# クラスを定義
class Piece:
    """1つのコマに関する情報を記録するクラス"""

    def __init__(self, x: int, y: int, col: float):
        """初期化"""
        self.x = x  # x座標
        self.y = y  # y座標
        self.color = col  # 色
        self.e_color = 0.0  # COL_Uの推測値 Estimated value を保持。　COL_R <= e_color <= COL_B の値をとるとする。
        # ただし現在のこのプログラムでは e_color を更新していない（つまり「赤の疑い」度を算出していない）。
        # 敵コマの推定方法を考えてe_colorを更新するコードを追加すれば、より強くなるはずです。

    def get_color_string(self) -> str:
        """colorの値を文字列に変換して返す。推定値も。"""
        if self.color == COL_R:
            return "R"
        elif self.color == COL_B:
            return "B"
        elif self.e_color == COL_R:
            return "?R"
        elif self.e_color == COL_B:
            return "?B"
        return "?" + str(self.e_color)

    def __repr__(self):
        """Pieceのインスタンスがprint()で表示できるようにするための関数"""
        return "(%d,%d,%s)" % (self.x, self.y, self.get_color_string())


class Player:
    """一人のプレイヤーの状態をすべて記録するクラス"""

    def __init__(self, which_player: int = ME, pieces: List[Piece] = None):
        self.which_player = which_player  # 自分か相手かを保持
        self.pieces = pieces  # 初期化時に８個のコマが入ったリストを受け取る
        self.n_alive_pieces = len(self.pieces)  # 生きているコマの数
        self.n_escaped = 0  # 敵陣から抜けたコマの数
        self.n_alive_red = 0  # 生きている赤コマの数
        self.n_alive_blue = 0  # 生きている青コマの数
        self.n_captured_pieces = 0  # 捕獲されたコマの数
        self.n_captured_red = 0  # 捕獲された赤コマの数
        self.n_captured_blue = 0  # 捕獲された青コマの数

    def analyse(self):
        """コマの生死状態をカウントする"""
        self.n_alive_pieces = 0  # 生きているコマの数
        self.n_escaped = 0  # 敵陣から抜けたコマの数
        self.n_alive_red = 0  # 生きている赤コマの数
        self.n_alive_blue = 0  # 生きている青コマの数
        self.n_captured_pieces = 0  # 捕獲されたコマの数
        self.n_captured_red = 0  # 捕獲された赤コマの数
        self.n_captured_blue = 0  # 捕獲された青コマの数
        for piece in self.pieces:
            self.n_alive_pieces = self.n_alive_pieces + 1
            if piece.x in {LOC_ESCAPED_W, LOC_ESCAPED_E}:  # 脱出
                self.n_escaped = self.n_escaped + 1
            if piece.x == LOC_CAPTURED:  # 捕獲されたコマの数
                self.n_captured_pieces = self.n_captured_pieces + 1
                if piece.color == COL_B:
                    self.n_captured_blue = self.n_captured_blue + 1
                elif piece.color == COL_R:
                    self.n_captured_red = self.n_captured_red + 1
            else:  # 生きているコマの数
                self.n_alive_pieces = self.n_alive_pieces + 1
                if piece.color == COL_B:
                    self.n_alive_blue = self.n_alive_blue + 1
                elif piece.color == COL_R:
                    self.n_alive_red = self.n_alive_red + 1


class Move:
    """一つの手を表現するクラス"""
    news = ['n', 'e', 'w', 's']

    def __init__(self, which_player=ME, piece_ix=-1, piece_x=0, piece_y=0, direction='n'):
        self.which_player = which_player  # プレイヤー番号
        self.piece_ix = piece_ix  # コマの番号　（コマの番号を指定するか、X,Yを指定するか。どっちでもかまわない）
        self.piece_x = piece_x  # コマのX座標
        self.piece_y = piece_y  # コマのY座標
        self.direction = direction  # コマの移動方向
        self.x_after_move = 0  # コマを動かした後のX座標
        self.y_after_move = 0  # コマを動かした後のY座標
        if self.piece_ix < 0:
            # piece_xとpiece_yから対象pieceを探し出す
            which_player, found_piece = find_piece_from_xy(piece_x, piece_y)
            if found_piece is None:
                print("error! piece (" + str(piece_x) + ", " + str(piece_y) + ") was not found.")
            else:
                self.piece_ix = g.players[which_player].pieces.index(found_piece)
        else:
            # piece_ixからxとyを出しておく
            self.piece_x = g.players[self.which_player].pieces[self.piece_ix].x
            self.piece_y = g.players[self.which_player].pieces[self.piece_ix].y
        self.calc_moved_loc()  # コマを動かした後の座標を計算する

    @classmethod
    def rand(cls, which_player=ME):
        """完全にランダムな打ち手（妥当性は考慮せず）のインスタンスを生成して返す"""
        piece_ix = random.randrange(MAX_PIECES)
        direction = Move.news[random.randrange(4)]
        return cls(which_player=which_player, piece_ix=piece_ix, direction=direction)

    def calc_moved_loc(self):
        """Moveを実行した結果、コマがどこへ移動するかを計算しておく"""
        x = self.piece_x
        y = self.piece_y
        if self.direction == 'n':
            y = y - 1
        if self.direction == 'e':
            x = x + 1
        if self.direction == 'w':
            x = x - 1
        if self.direction == 's':
            y = y + 1
        self.x_after_move = x  # コマを動かした後のX座標
        self.y_after_move = y  # コマを動かした後のY座標

    def __repr__(self):
        """Moveのインスタンスをprint()で表示するための関数"""
        return "(%d,%d,%s)" % (g.players[self.which_player].pieces[self.piece_ix].x,
                               g.players[self.which_player].pieces[self.piece_ix].y,
                               self.direction)

    def reverse_repr(self):
        """敵の側から見た打ち手を返す（相手に伝える時に逆から見た時の x,y,direction を伝えると楽に進行できそうだから）"""
        x = (BOARD_WIDTH - 1) - g.players[self.which_player].pieces[self.piece_ix].x
        y = (BOARD_HEIGHT - 1) - g.players[self.which_player].pieces[self.piece_ix].y
        if self.direction == 'n':
            d = 's'
        elif self.direction == 'e':
            d = 'w'
        elif self.direction == 'w':
            d = 'e'
        else:  # 's'
            d = 'n'
        return "(%d,%d,%s)" % (x, y, d)


class Game:
    """ゲーム全体（進行、プレイヤーデータなどすべて）を保持するクラス"""

    def __init__(self):
        self.game_state = GameState.enter_f_or_s  # ゲームの状態遷移を記録
        self.players = []  # プレイヤー二人 ME, OP を保持
        self.first_player = ME  # 先手を記憶
        self.last_captured_piece = None  # 最後に捕獲されたコマを記憶
        self.last_move = None  # 最後の手を記憶
        self.n_moved = 0  # 何手まで打ったか
        self.capture_above_e_color = CAPTURE_ABOVE_E_COLOR_ALL  # AIの捕獲行動を制御する閾値。
        # 相手コマの推定色 e_color >= capture_above_e_color なら捕獲できる、と判断する。
        # 相手コマの推定色 e_color < capture_above_e_color なら捕獲できない、と判断する。
        # なんでも取っていい場合は capture_above_e_color = COL_R + 0.1 とかにしておく。（「確実に赤コマ」は捕獲しない）
        # 赤３つ取っちゃった後は capture_above_e_color = COL_B にしておく。（「確実に青コマ」を捕獲）


# グローバル変数
g = Game()  # 現在のゲーム状態すべて
g_stack = []  # ゲーム状態を保存しておくスタック


def push_game() -> None:
    """現在のゲーム状態をスタックに積む"""
    binary = pickle.dumps(g)  # ゲーム状態をバイナリに変換して
    g_stack.append(binary)  # スタックに退避


def pop_game(show_message: bool = True) -> None:
    """スタックからGameを取り出してセットする(Undoに相当）"""
    if len(g_stack) > 0:
        binary = g_stack.pop()  # スタックから取り出して
        global g
        g = pickle.loads(binary)  # ゲーム状態に復元
        if show_message:
            print('----------')
            print('reverted.')
            print('----------')
        # 最初の一個がなくなるとNewGame状態に戻れなくなるので、これを保存しておく。
        if len(g_stack) <= 0:
            push_game()


# 捕獲されたコマのRB表示部分
def get_captured_piece_strings(player):
    ix = 0
    result = ""
    for piece in player.pieces:
        if piece.x == LOC_CAPTURED:
            if piece.color == COL_R:
                result = result + CHAR_RED
            elif piece.color == COL_B:
                result = result + CHAR_BLUE
            else:
                result = result + CHAR_UNDEFINED
            ix = ix + 1
    for i in range(8 - ix):
        if ZENKAKU:
            result = result + '　'
        else:
            result = result + ' '
    return result[0:4], result[4:8]


def show_board() -> None:
    """現在のボード状態を表示する"""
    """ 出力フォーマットは以下
    　　　　　　　　　 ｎ　　　　　（こちらが相手の陣地）
    　　　　　　　０１２３４５　
    ⓡⓡⓡⓡ　０　・🅤🅤🅤🅤・　５
    ⓑⓑⓑⓑ　１　・🅤🅤🅤🅤・　４
    　　　ｗ　２　・・・・・・　３　ｅ
    　　　　　３　・・・・・・　２
    　　　　　４　・ⓡⓡⓡⓡ・　１　ⓡⓡⓡⓡ   （←捕獲したコマを横に表示）
    　　　　　５　・ⓑⓑⓑⓑ・　０　ⓑⓑⓑⓑ
    　　　　　　　５４３２１０
    　　　　　　　　　 ｓ　　　　　（こちらが自分の陣地）
    ・座標は、ボードの左上を原点とした二次元座標(x, y)=(0~5, 0~5)で表現します。
    　（右側と下側に、右下原点の座標値を表示しているのは、
    　　対戦相手から見たときの座標値が表示してあったほうが親切かな？との考えです）
    ・コマを動かす方向は東西南北の ｅ ｗ ｎ ｓ で表現します。
    """
    # print(g.players[OP].pieces)  # show pieces for debug
    # print(g.players[ME].pieces)  # show pieces for debug
    # 盤面の中を作成
    if ZENKAKU:
        board = ["　・・・・・・　"] * BOARD_HEIGHT
    else:
        board = [" ------ "] * BOARD_HEIGHT
    for p in g.players:
        for piece in p.pieces:
            if piece.x != LOC_CAPTURED:
                if piece.color == COL_R:
                    board[piece.y] = board[piece.y][:piece.x + 2 - 1] + CHAR_RED + board[piece.y][piece.x + 2:]
                elif piece.color == COL_B:
                    board[piece.y] = board[piece.y][:piece.x + 2 - 1] + CHAR_BLUE + board[piece.y][piece.x + 2:]
                else:
                    board[piece.y] = board[piece.y][:piece.x + 2 - 1] + CHAR_UNDEFINED + board[piece.y][piece.x + 2:]
    my_captured_string_1, my_captured_string_2 = get_captured_piece_strings(g.players[ME])
    op_captured_string_1, op_captured_string_2 = get_captured_piece_strings(g.players[OP])
    # 表示
    if ZENKAKU:
        print("　　　　　　　　　 ｎ")
        print("　　　　　　　０１２３４５")
        print(my_captured_string_1 + "　０" + board[0] + "５")
        print(my_captured_string_2 + "　１" + board[1] + "４")
        print("　　　ｗ　２" + board[2] + "３　ｅ")
        print("　　　　　３" + board[3] + "２")
        print("　　　　　４" + board[4] + "１　" + op_captured_string_1)
        print("　　　　　５" + board[5] + "０　" + op_captured_string_2)
        print("　　　　　　　５４３２１０")
        print("　　　　　　　　　 ｓ")
    else:
        print("          n")
        print("       012345")
        print(my_captured_string_1 + " 0" + board[0] + "5")
        print(my_captured_string_2 + " 1" + board[1] + "4")
        print("   w 2" + board[2] + "3 e")
        print("     3" + board[3] + "2")
        print("     4" + board[4] + "1 " + op_captured_string_1)
        print("     5" + board[5] + "0 " + op_captured_string_2)
        print("       543210")
        print("          s")


def show_status_message() -> None:
    """現在の状況（何を待っているかなど）を表示する　"""
    if g.game_state == GameState.enter_f_or_s:  # ゲーム開始待ちなので、先手か後手かを入れてくれ
        print('enter f(My AI is first) or s(My AI is second)')
    elif g.game_state == GameState.enter_opponent_move:  # 相手の手番なので、相手の手を入れてくれ
        print('enter opponent move x,y,n/e/w/s (e.g. 1,1,s or 11s)')
    elif g.game_state == GameState.next_is_AI_move:  # 次はAIの番ですよ
        print('AI Thinking ...')
    elif g.game_state == GameState.enter_color_of_captured_piece:  # AIがとったコマの色の入力待ち
        print('enter r or b (color of captured piece)')
    elif g.game_state == GameState.won:  # 勝った表示
        print('My AI won!')
    elif g.game_state == GameState.lost:  # 負けた表示
        print('My AI lost.')


def show_help() -> None:
    """入力できるコマンドなどの説明を表示する　"""
    print('----------')
    print('h, help, ?     : show help')
    print('q, quit        : quit program')
    print('e, end, finish : finish game, and start new game')
    print('u, undo, z     : undo')
    print('----------')


def reset_game() -> None:
    """ゲームの状態をすべてリセットして、ゲームを開始できる状態にする"""
    global g_stack
    g_stack = []  # ゲーム状態を保存しておくスタックをクリアする
    g.game_state = GameState.enter_f_or_s  # 現在のゲームの状態を保持する変数
    g.last_move = None  # 最後に動かした手
    """ ゲーム開始時のコマの配置場所を決めます
     012345
    0 0123 5  　　←　こちらが敵側とします
    1 4567 4
    2      3
    3      2
    4 0123 1　　　←　こちらが自分側とします
    5 4567 0
     543210
    """
    # 初期配置
    # 自分（AI）のコマ情報を保持するplayerを作ります
    # 前４個を赤に、後ろ４個を青にしています。これは各自のAIで好きな配置を選んでください（何らかのアルゴリズムで配置する仕組みを作っても良いですね）
    me = Player(which_player=ME, pieces=[
        Piece(1, 4, COL_R), Piece(2, 4, COL_R), Piece(3, 4, COL_R), Piece(4, 4, COL_R),
        Piece(1, 5, COL_B), Piece(2, 5, COL_B), Piece(3, 5, COL_B), Piece(4, 5, COL_B)
    ])
    # 相手（敵）のコマ情報を保持するplayerを作ります
    # 敵のコマは色が不明なのでCOL_Uで全部並べます
    op = Player(which_player=OP, pieces=[
        Piece(1, 0, COL_U), Piece(2, 0, COL_U), Piece(3, 0, COL_U), Piece(4, 0, COL_U),
        Piece(1, 1, COL_U), Piece(2, 1, COL_U), Piece(3, 1, COL_U), Piece(4, 1, COL_U)
    ])
    # playerリストに保存します
    g.players = [me, op]
    # 最初のまっさらなゲーム状態をスタックに退避しておく
    push_game()


def is_game_over() -> bool:
    """盤面解析して勝利条件が確定しているか確かめ、確定していればTrueを返す"""
    # すでに勝ち負けが決まっていればTrueを返すだけでよい
    if g.game_state in {GameState.won, GameState.lost}:
        return True
    # いろいろカウント
    g.players[ME].analyse()
    g.players[OP].analyse()
    # 各勝利条件を調べていく
    # 敵陣を抜けたコマがいる　＝　勝ち
    if g.players[ME].n_escaped > 0:
        g.game_state = GameState.won
        return True
    # 自陣から抜けられたコマがいる　＝　負け
    if g.players[OP].n_escaped > 0:
        g.game_state = GameState.lost
        return True
    # 敵の赤を４個取ってしまった判定　＝　負け
    if g.players[OP].n_captured_red >= 4:
        g.game_state = GameState.lost
        return True
    # 敵の青を４個取ってしまった判定　＝　勝ち
    if g.players[OP].n_captured_blue >= 4:
        g.game_state = GameState.won
        return True
    # 自分の赤を４個取られてしまった判定　＝　勝ち
    if g.players[ME].n_captured_red >= 4:
        g.game_state = GameState.won
        return True
    # 自分の青を４個取られてしまった判定　＝　負け
    if g.players[ME].n_captured_blue >= 4:
        g.game_state = GameState.lost
        return True
    # 上記状態以外であれば、ゲーム終了条件は成立していないのでFalseを返す
    return False


def find_piece_from_xy(x: int, y: int) -> Union[Tuple[int, None], Tuple[int, Piece]]:
    """XYで指定された座標に存在するコマを探して、誰のどのコマかを返す（または何もない=NO_PLAYERを返す）"""
    for p in g.players:
        for piece in p.pieces:
            if piece.x == x and piece.y == y:
                return p.which_player, piece
    return NO_PLAYER, None


def is_correct_move(move: Move) -> bool:
    """手が適正かどうかを判定します"""
    if move.piece_ix < 0 or move.piece_ix >= MAX_PIECES:
        return False
    target_piece = g.players[move.which_player].pieces[move.piece_ix]
    # 指定したコマがすでに脱出していたらFalseを返す
    if target_piece.x in {LOC_ESCAPED_W, LOC_ESCAPED_E}:
        return False
    # 指定したコマがすでに捕獲されていたらFalseを返す
    if target_piece.x == LOC_CAPTURED:
        return False
    # 移動が「青コマの脱出」であればTrueを返す
    if target_piece.color != COL_R:  # 敵のUnknownのコマでも脱出行動は適正と判断したいので !COL_R で比較
        if (move.which_player == ME and target_piece.y == 0) or \
                (move.which_player == OP and target_piece.y == (BOARD_HEIGHT - 1)):  # 自分なら上、敵なら下の行で
            if target_piece.x == 0:  # 左から
                if move.direction == 'w':  # 西（＝左）へ抜けようとしていたら
                    return True  # 適正
            elif target_piece.x == (BOARD_WIDTH - 1):  # 右から
                if move.direction == 'e':  # 東（＝右）へ抜けようとしていたら
                    return True  # 適正
    # 移動先が盤面からはみ出していればFalseを返す
    if move.x_after_move < 0 or move.x_after_move >= BOARD_WIDTH:
        return False
    if move.y_after_move < 0 or move.y_after_move >= BOARD_HEIGHT:
        return False
    # 移動先に自分のコマがいたらFalseを返す
    which_player, target_piece = find_piece_from_xy(move.x_after_move, move.y_after_move)
    if move.which_player == which_player:  # 移動先に自分のコマがいるなら、の条件判定
        return False
    # 自コマの移動チェックの場合、e_color < g.capture_above_e_color の場合は捕獲できない、とする。
    if which_player == OP:
        if target_piece.e_color < g.capture_above_e_color:
            return False
    # 上記以外の条件ならTrue（適正な打ち手）と判断してTrueを返す
    return True


def execute_move(move: Move) -> Union[Piece, None]:
    """打ち手を実行して盤面をアップデートする。与えられた手Moveは適正なものとする（事前にis_correct_moveでチェック済みであるとする）。とったコマを返す"""
    g.last_move = move
    g.n_moved = g.n_moved + 1
    target_piece = g.players[move.which_player].pieces[move.piece_ix]
    # 移動先にコマがあれば、それを発見しておく
    which_player, captured_piece = find_piece_from_xy(move.x_after_move, move.y_after_move)
    # 次にコマを移動する
    target_piece.x = move.x_after_move
    target_piece.y = move.y_after_move
    # 移動先でコマが見つかっていた場合は、それを獲得状態に変更する
    if which_player != NO_PLAYER:
        # 移動先にコマがあるので、それを獲得する
        captured_piece.x = LOC_CAPTURED
        captured_piece.y = LOC_CAPTURED
        return captured_piece
    return None  # 相手のコマはとっていません


def ai_move() -> GameState:
    """次の手を考え、打ち、状況を判定して、次のゲームステータスを返す"""
    # まず最初にゲームが終了していないことを確認します（念のため）
    if is_game_over():
        return g.game_state
    # 次の手を考えます。このサンプルではランダムな手を選択します。
    move = think()

    # この段階で、打つ手が move に決定した、とします。

    # コンソールに「このコマをこう動かします」と表示します。
    print("--------------------------")
    print("AI move is " + str(move) + " ⇄ " + move.reverse_repr())
    print("--------------------------")
    # AIの考えた手を打ちます
    captured_piece = execute_move(move)
    if captured_piece is not None:
        # 敵のコマをとった場合、そのコマの色を入力してもらいます
        g.last_captured_piece = captured_piece
        return GameState.enter_color_of_captured_piece  # 色の入力待ちに遷移
    # ゲームの終了条件を判定します
    if is_game_over():
        return g.game_state
    # GameStatusをアップデートします（次の打ち手待ちになるように）
    return GameState.enter_opponent_move  # AIが考えた後は敵の打ち手を待つ状態に遷移


def opponent_move(move: Move) -> GameState:
    """敵の手を実行、状況を判定して、次のゲームステータスを返す"""
    # まず最初にゲームが終了していないことを確認します（念のため）
    if is_game_over():
        return g.game_state
    # 敵の考えた手を打ちます
    push_game()  # 現在のゲーム状態を退避
    captured_piece = execute_move(move)
    if captured_piece is not None:
        # AIのコマをとった場合
        g.last_captured_piece = captured_piece
    # ゲームの終了条件を判定します
    if is_game_over():
        return g.game_state
    # GameStatusをアップデートします（次の打ち手待ちになるように）
    return GameState.next_is_AI_move  # 敵が考えた後はAIの打ち手を待つ状態に遷移


def process_command(cmd: str) -> bool:
    """入力を処理する。処理できたらTrueを、意味不明の場合はFalseを返す"""
    if g.game_state == GameState.enter_f_or_s:  # ゲーム開始待ちなので、先手か後手かを入れてくれ
        # print('enter f(My AI is first) or s(My AI is second)')
        if cmd == 'f':
            # 先手を選択された　＝　最初のAIの手を考えて実行
            g.first_player = ME
            g.game_state = ai_move()
            return True
        if cmd == 's':
            # 後手を選択された = 敵のコマの入力待ちになる
            g.first_player = OP
            g.game_state = GameState.enter_opponent_move
            return True
        print('f または s を入力してください。 fはAIが先手, sはAIが後手の意味です。')
        return False
    elif g.game_state == GameState.enter_opponent_move:  # 相手の手番なので、相手の手を入れてくれ
        # print('enter opponent move x,y,n/e/w/s (e.g. 1,1,s or 11s)')
        # commands = cmd.split(",")
        commands = re.split(r'\s|"|,|\.', cmd)  # カンマ、スペース、ピリオドなどの区切り文字も使えるように
        if len(commands) == 1 and len(cmd) == 3:
            # 01s みたいに区切り文字なく連続してxydが入力された場合でも処理する
            x = int(cmd[0:1])
            y = int(cmd[1:2])
            d = cmd[2:3]
            if 0 <= x < BOARD_WIDTH and 0 <= y < BOARD_HEIGHT and d in Move.news:
                commands = [str(x), str(y), d]
        if len(commands) != 3 or \
                not commands[0].isdecimal or \
                len(commands[0]) < 1 or \
                not commands[1].isdecimal or \
                len(commands[1]) < 1 or \
                commands[2] not in {'n', 'e', 's', 'w'}:
            print("相手の指し手を 0,1,s のように x,y,方角 の形で入力してください（01sでもOK）")
            return False

        which_player, captured_piece = find_piece_from_xy(int(commands[0]), int(commands[1]))
        if which_player == ME:
            print("指定された位置(" + cmd + ")は相手のコマではありません。相手のコマを指定してください。")
        elif which_player == NO_PLAYER:
            print("指定された位置(" + cmd + ")には相手のコマがありません。")
        else:
            move = Move(which_player=OP,
                        piece_ix=-1,
                        piece_x=int(commands[0]),
                        piece_y=int(commands[1]),
                        direction=commands[2])
            if is_correct_move(move):
                g.game_state = opponent_move(move)
            else:
                print("指定された手(" + cmd + ")は打てません。不正な移動です。")
        return True
    elif g.game_state == GameState.enter_color_of_captured_piece:  # AIがとったコマの色の入力待ち
        # print('enter r or b (color of captured piece)')
        push_game()  # 現在のゲーム状態を退避
        if cmd in {'r', 'red'}:
            g.last_captured_piece.color = COL_R
        elif cmd in {'b', 'blue'}:
            g.last_captured_piece.color = COL_B
        else:
            pop_game(show_message=False)  # 入力が無効だったのでスタックを元に戻す
            return False
        if not is_game_over():
            g.game_state = GameState.enter_opponent_move
        return True
    elif g.game_state == GameState.won:  # 勝った表示
        return True
    elif g.game_state == GameState.lost:  # 負けた表示
        return True
    return False


def main():
    random.seed()  # 乱数の初期化
    reset_game()
    while True:
        # 現在のボード状態を表示する
        show_board()
        # 現在の状況に応じた入力を催促する
        show_status_message()
        if g.game_state == GameState.next_is_AI_move:  # 次はAIの番ですよ
            # AIに考えて打ってもらう
            g.game_state = ai_move()
        else:
            # 何らかのコマンドを入れてもらう
            cmd = input('(' + str(g.n_moved) + ') >> ')
            cmd = cmd.lower()
            # 終了コマンドの検出と処理
            if cmd in {'quit', 'q'}:
                break
            # ヘルプコマンドの検出と処理
            if cmd in {'help', 'h', '?'}:
                show_help()
                continue
            # endコマンドの検出と処理
            if cmd in {'e', 'end', 'finish', 'restart', 'new'}:
                reset_game()
                continue
            # Undoコマンドの検出と処理
            if cmd in {'u', 'undo', 'z'}:
                pop_game()  # スタックから前の状態を取り出して戻す
                continue
            if process_command(cmd):
                continue


"""思考ルーチンのサンプル"""


def think_random() -> Move:
    """ランダムな手を返す"""
    return Move.rand()


def think_attack(color: float) -> Move:
    """指定色のコマで攻めていくだけの思考ルーチン"""
    # 生きている指定色（のインデックス番号）をリスト化
    target_piece_indexes = []
    for pix, piece in enumerate(g.players[ME].pieces):
        if 0 <= piece.x < BOARD_WIDTH and piece.color == color:
            target_piece_indexes.append(pix)
    # シャッフルする（動かそうとするコマをランダムに選択するため）
    random.shuffle(target_piece_indexes)
    # できるだけ北へ動かそうとトライ
    for pix in target_piece_indexes:
        # newsの順に動く方角を試してOKなら打ち手を返す
        for direction in Move.news:
            move = Move(which_player=ME,
                        piece_ix=pix,
                        direction=direction)
            if is_correct_move(move):
                return move
        # どの方角にも動けなかった場合はここまで落ちてきて、次のコマを試す
    # すべての指定色コマが動けない状態はここまで落ちてくるので、ランダムな手を返す
    return think_random()


def move_blocking_piece(x: int, y: int) -> Union[Move, None]:
    """指定位置に赤ゴマがあった場合、現在の場所から動かすことが可能ならばその手を返す"""
    which_player, piece = find_piece_from_xy(x, y)
    if which_player != ME:
        return None
    if piece.color != COL_R:
        return None
    for direction in Move.news:
        move = Move(which_player=ME,
                    piece_x=x,
                    piece_y=y,
                    direction=direction)
        if is_correct_move(move):
            return move
    return None


def move_to_win() -> Union[Move, None]:
    """必勝状態なら必勝手を返す"""
    # 左上に青コマがあるときは西へ抜ける
    which_player, piece = find_piece_from_xy(0, 0)
    if which_player == ME:
        if piece.color == COL_B:
            return Move(which_player=ME,
                        piece_x=0,
                        piece_y=0,
                        direction='w')
    # 右上に青コマがある時は東へ抜ける
    which_player, piece = find_piece_from_xy(BOARD_WIDTH - 1, 0)
    if which_player == ME:
        if piece.color == COL_B:
            return Move(which_player=ME,
                        piece_x=BOARD_WIDTH - 1,    # これが0になっていた（バグ）ので修正しました。事故った方ごめんなさいです！
                        piece_y=0,
                        direction='w')
    return None


def move_to_capture(tgx: int, tgy: int) -> Union[Move, None]:
    """指定された位置にある敵コマを自ゴマで捕獲できるなら、そのMoveを返す"""
    # 捕獲対象コマの上下左右の自ゴマを探索、捕獲方角を指示するための配列
    search_xyd = [[-1, 0, 'e'], [1, 0, 'w'], [0, -1, 's'], [0, 1, 'n']]
    for xyd in search_xyd:
        x = tgx + xyd[0]
        y = tgy + xyd[1]
        which_player, piece = find_piece_from_xy(x, y)
        if which_player == ME:
            move = Move(which_player=ME,
                        piece_x=x,
                        piece_y=y,
                        direction=xyd[2])
            if is_correct_move(move):  # is_correct_moveで弾かれる可能性がある（無限ループになる）ので、その可能性を除外しておく
                return move
    return None


def move_to_no_lose() -> Union[Move, None]:
    """必敗状態ならそれを阻止する手を返す"""
    # 左下に敵コマがあるとき、可能なら捕獲する
    which_player, piece = find_piece_from_xy(0, BOARD_HEIGHT - 1)
    if which_player == OP:
        move = move_to_capture(piece.x, piece.y)
        if move is not None:
            return move
    # 右下に敵コマがあるとき、可能なら捕獲する
    which_player, piece = find_piece_from_xy(BOARD_WIDTH - 1, BOARD_HEIGHT - 1)
    if which_player == OP:
        move = move_to_capture(piece.x, piece.y)
        if move is not None:
            return move
    return None


def think_various_rules_1() -> Move:
    """ちょっと複雑なことを考えながら打ってみる"""
    # 必勝状態ならそれを逃さない（青コマが敵陣抜けられるなら絶対抜ける）
    move = move_to_win()
    if move is not None:
        return move
    # 必敗状態ならそれを阻止する
    move = move_to_no_lose()
    if move is not None:
        return move
    # 敵の赤を3個取ってしまったら、赤の疑いがあるコマを取らないようにする
    if g.players[OP].n_captured_red >= 3:
        g.capture_above_e_color = CAPTURE_ABOVE_E_COLOR_ONLY_BLUE
    # 20手までは赤コマだけで攻める
    if g.n_moved < 20:
        return think_attack(COL_R)
    # 20手目以降は赤コマ青コマの残りが多い方（同数ならランダムで決定）で攻める
    if g.players[ME].n_alive_red > g.players[ME].n_alive_blue:
        return think_attack(COL_R)
    if g.players[ME].n_alive_red == g.players[ME].n_alive_blue:
        return think_attack(random.choice((COL_R, COL_B)))
    # 青コマで攻める前に、赤コマが脱出口を塞いでいるときは、それを動かす
    move = move_blocking_piece(0, 0)
    if move is not None:
        return move
    move = move_blocking_piece(BOARD_WIDTH - 1, 0)
    if move is not None:
        return move
    # 青駒で攻める
    return think_attack(COL_B)


def think() -> Move:
    """現在のゲーム状況から、AIの最善の打ち手を考え、Moveを作成して返す"""
    while True:
        # move = think_random()  # ランダムな手を選ぶパターン
        # move = think_attack(COL_R)  # 赤だけで攻めていくパターン
        move = think_various_rules_1()  # もうちょっと複雑な攻め方をするパターン
        # 打ち手が正しければループを抜ける
        if is_correct_move(move):
            break
    return move


if __name__ == '__main__':
    main()
