from dataclasses import dataclass
import enum
import sys
import os
from typing import Optional, Union, Tuple, List
from datetime import datetime

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class COORD(ctypes.Structure):
        _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]

    class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
        _fields_ = [("dwSize", COORD),
                    ("dwCursorPosition", COORD),
                    ("wAttributes", wintypes.WORD),
                    ("srWindow", ctypes.c_short * 4),
                    ("dwMaximumWindowSize", COORD)]

    def get_console_cursor_pos():
        h = ctypes.windll.kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        csbi = CONSOLE_SCREEN_BUFFER_INFO()
        res = ctypes.windll.kernel32.GetConsoleScreenBufferInfo(h, ctypes.byref(csbi))
        if res:
            return csbi.dwCursorPosition.X, csbi.dwCursorPosition.Y
        else:
            return -1, -1
else:
    import termios
    import re

def _get_cursor_pos() -> Tuple[int, int]:
    if sys.platform == "win32":
        h = ctypes.windll.kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        csbi = CONSOLE_SCREEN_BUFFER_INFO()
        res = ctypes.windll.kernel32.GetConsoleScreenBufferInfo(h, ctypes.byref(csbi))
        if res:
            return csbi.dwCursorPosition.X, csbi.dwCursorPosition.Y
        else:
            return -1, -1
    else:
        OldStdinMode = termios.tcgetattr(sys.stdin)
        _ = termios.tcgetattr(sys.stdin)
        _[3] = _[3] & ~(termios.ECHO | termios.ICANON)
        termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, _)
        try:
            _ = ""
            sys.stdout.write("\x1b[6n")
            sys.stdout.flush()
            while not (_ := _ + sys.stdin.read(1)).endswith('R'):
                pass
            res = re.match(r".*\[(?P<y>\d*);(?P<x>\d*)R", _)
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, OldStdinMode)
        if(res):
            return (int(res.group("x")), int(res.group("y")))
        return (-1, -1)

def _get_terminal_res():
    w,h = os.get_terminal_size()
    return h,w



class TC:
    alt_buffer: bool = False 
    cursor_pos: Tuple[int, int] = (-1,-1)
    terminal_res: Tuple[int, int] = (-1,-1)
    
    @staticmethod
    def init():
        TC._update()

    @staticmethod
    def _update():
        TC.cursor_pos = _get_cursor_pos()
        TC.terminal_res = _get_terminal_res()

    @staticmethod
    def go_screen_up(n: int):
        sys.stdout.write(f'\x1b[{n}S')
        sys.stdout.flush()
        TC._update()

    @staticmethod
    def go_screen_down(n: int):
        sys.stdout.write(f'\x1b[{n}T')
        sys.stdout.flush()
        TC._update()

    @staticmethod
    def go_cursor_up(n: int):
        sys.stdout.write(f'\x1b[{n}A')
        TC._update()

    @staticmethod
    def go_cursor_down(n: int):
        sys.stdout.write(f'\x1b[{n}B')
        TC._update()

    @staticmethod
    def erase_line():
        sys.stdout.write(f'\x1b[K')
        TC._update()

    @staticmethod
    def switch_buffer():
        if TC.alt_buffer: 
            sys.stdout.write("\033[?1049l")
            TC.alt_buffer = False
        else:
            sys.stdout.write('\033[?1049h')
            TC.alt_buffer = True
        sys.stdout.flush()
        TC._update()
    
    @staticmethod
    def clear_buffer():
        sys.stdout.write("\033[H")
        TC._update()

    @staticmethod
    def go_cursor_to_left_top():
        sys.stdout.write("\033[2J")
        TC._update()
    
    @staticmethod
    def go_cursor_to_pos(n: int, m: int):
        sys.stdout.write(f"\033[{n};{m}H")
        # TC._update()

    @staticmethod
    def go_cursor_to_left():
        sys.stdout.write('\033[0G')
        TC._update()

    @staticmethod
    def clear_current_line():
        sys.stdout.write('\033[2K')

    @staticmethod
    def write_line(text: str, end='\n'): 
        sys.stdout.write(''.join([text, end]))
        # TC._update()

    @staticmethod
    def flush():
        sys.stdout.flush()

# Default table chars
dtc = { 
    'cross'     : '┼',

    'left_bot'  : '└',
    'left_top'  : '┌',
    'right_bot' : '┘',
    'right_top' : '┐',

    'top'       : '┬',
    'left'      : '├',
    'bot'       : '┴',
    'right'     : '┤',

    'h' : '│',
    'w' : '─',
}


import numpy as np



class TWindow:
    def __init__(self, r, c, h, w, title='', *args, **kwargs):
        self._h = h
        self._w = w
        self._r = r 
        self._c = c
        self._title = title

        self._args = args
        self._kwargs = kwargs

        self._data = np.full((h - 2, w - 2), '', dtype='U1')
        self._hsplit: Optional[Tuple[TWindow, TWindow]] = None
        self._wsplit: Optional[Tuple[TWindow, TWindow]] = None
    
    def full(self):
        return self.__class__(1,1, *_get_terminal_res(), self._title, *self._args, **self._kwargs)
   
    def set_title(self, title): 
        self._title = title

    def clear(self) :
        if self._hsplit: 
            self._hsplit[0].clear()
            self._hsplit[1].clear()
            return
        elif self._wsplit:
            self._wsplit[0].clear()
            self._wsplit[1].clear()
            return
        self._data = np.full((self._h - 2, self._w - 2), '', dtype='U1')
    
    @staticmethod
    def __split_str(s: str, n: int): 
        return [s[i:i+n] for i in range(0, len(s), n)]

    def draw_frame(self, isroot=False):
        if isroot:
            if self._hsplit:
                self._hsplit[0].draw_frame(isroot)
                self._hsplit[1].draw_frame(isroot)
                return
            if self._wsplit:
                self._wsplit[0].draw_frame(isroot)
                self._wsplit[1].draw_frame(isroot)
                return

        TC.go_cursor_to_pos(self._r, self._c)
        str_num = self._r
        if self._title: 
            splitted_title = self.__split_str(self._title, self._w - 2)
            
            TC.write_line(f"{dtc['left_top']}"\
                          f"{dtc['w'] * (self._w - 2)}"\
                          f"{dtc['right_top']}", end='')
            for substr in splitted_title:
                str_num += 1
                TC.go_cursor_to_pos(str_num, self._c)
                if len(substr) >= self._w - 2:
                    TC.write_line(f"{dtc['h']}{substr:{self._w - len(substr)}}{dtc['h']}")
                else: 
                    TC.write_line(f"{dtc['h']}{substr:{self._w-2}}{dtc['h']}")
            str_num += 1

            TC.go_cursor_to_pos(str_num, self._c)
            TC.write_line(f"{dtc['left']}{dtc['w'] * (self._w - 2)}{dtc['right']}")
            str_num += 1
            ran = range(str_num, self._r + self._h - 1)
        else:
            TC.write_line(f"{dtc['left_top']}{dtc['w'] * (self._w - 2)}{dtc['right_top']}", end='')
            ran = range(str_num + 1, self._r + self._h - 1)

        TC.flush()
        for _ in ran:
            TC.go_cursor_to_pos(_, self._c)
            TC.write_line(f"{dtc['h']}{' ' * (self._w - 2)}{dtc['h']}", end='')
        TC.go_cursor_to_pos(self._r + self._h - 1, self._c)
        TC.write_line(f"{dtc['left_bot']}{dtc['w'] * (self._w - 2)}{dtc['right_bot']}", end='')
        TC.flush()
        
    def draw_text(self, isroot=False):
        if isroot:
            if self._hsplit:
                self._hsplit[0].draw_text(isroot)
                self._hsplit[1].draw_text(isroot)
                return
            if self._wsplit:
                self._wsplit[0].draw_text(isroot)
                self._wsplit[1].draw_text(isroot)
                return
        if self._title: 
            num_rows = len(self.__split_str(self._title, self._w - 2)) + 1
        else:
            num_rows = 0

        for i,row in enumerate(self._data):
            TC.go_cursor_to_pos(self._r + 1 + i + num_rows, self._c + 1)
            TC.write_line(''.join(row), end='')
        TC.flush()

    def issplitted(self):
        return self._hsplit or self._wsplit

    def hsplit(self, per=0.5):
        """
            Splits TWindow into 2 TWindow's
            
            per=0.5 ~ percentage of left part of split
            
            per = 0.3:
            +------+-------+
            | left | right |
            +------+-------+
            | 0.3  | 0.7   | 
            +------+-------+
        """
        if self._hsplit:
            print(self)
            return (self._hsplit[0].hsplit(per),
                    self._hsplit[1].hsplit(per))
        elif self._wsplit:
            print(self)
            return (self._wsplit[0].hsplit(per),
                    self._wsplit[1].hsplit(per))

        left_col = int(self._w * per)
        left = self.__class__(self._r,
                              self._c,
                              self._h,
                              left_col,
                              self._title,
                              *self._args,
                              **self._kwargs
        )
        
        right = self.__class__(self._r, 
                               self._c + left_col,
                               self._h,
                               self._w - left_col,
                               self._title,
                               *self._args,
                               **self._kwargs
        )
        self._hsplit = left, right
        return left, right
    
    def wsplit(self, per=0.5):
        if self._hsplit:
            return (self._hsplit[0].wsplit(per),
                    self._hsplit[1].wsplit(per))
        elif self._wsplit:
            return (self._wsplit[0].wsplit(per),
                    self._wsplit[1].wsplit(per))

        top_row = int(self._h * per)
        top = self.__class__(self._r,
                      self._c,
                      top_row,
                      self._w,
                      *self._args, 
                      **self._kwargs
        )
        
        bot = self.__class__(self._r + top_row, 
                      self._c,
                      self._h - top_row,
                      self._w,
                      *self._args,
                      **self._kwargs
        )
        self._wsplit = top, bot
        return top, bot
    
    def __getitem__(self, ind):
        return self._data[ind]
    
    def __repr__(self):
        return\
        f'{self.__class__.__name__}('\
        f'(r,c)=({self._r}, {self._c}), '\
        f'(h,w)=({self._h}, {self._w}), '\
        f'ishsplt={True if self._hsplit else False}'\
        f'iswsplt={True if self._wsplit else False})'\

class TLog(TWindow):
    @dataclass
    class LogPos: 
        begin_row: int = -1
        begin_col: int = -1
        end_row: int = -1
        end_col: int = -1
        

    def __init__(self, row, col, h, w, title='', msg_format=r'[%H:%M:%S] {msg}', *args, **kwargs):
        """
            ( start_row, start_col, end_row, end_col )
        """
        kwargs['msg_format'] = msg_format
        super().__init__(row, col, h, w, title, *args, **kwargs)
        self.msg_coo: List[TLog.LogPos] = []
        self.msg_format = msg_format
        self._is_time_format = self._ckeck_is_time_format(msg_format)
    
    @staticmethod
    def _ckeck_is_time_format(format: str): 
        if any([part in format for part in ['%Y', '%m', '%d', '%H', '%M', '%S']]):
            return True 
        return False
    
    def clear(self): 
        super().clear()
        self.msg_coo = []

    def add_msg(self, msg: str): 
        if self._is_time_format: 
            self._add_msg(datetime.now().strftime(self.msg_format.format(msg=msg)))
        else:
            self._add_msg(self.msg_format.format(msg=msg))
    
    def _redirect_strs(self, new: LogPos):
        # print(self.msg_coo[-1].end_row, self._h - 2)
        if self.msg_coo[-1].end_row  - self.msg_coo[0].begin_row ==\
            self._h - 2:

            rows_num = new.end_row - new.begin_row
            rows_to_erase = []
            for i in range(len(self.msg_coo)):
                l_coo = self.msg_coo[i]
                delta = l_coo.end_row - l_coo.begin_row
                if delta <= rows_num:
                    rows_to_erase += [
                        i for i in range( l_coo.begin_row, l_coo.end_row + 1 )
                    ]
                    rows_num -= delta
                if rows_num <= 0: 
                    break
            for coo in self.msg_coo:
                print(coo)

    def _add_msg(self, msg: str):
        length = len(msg)
        sng_ln_len = self._w - 2
        if self.msg_coo: 
            start_row = self.msg_coo[-1].end_row + 1 
        else: 
            start_row = 0
    
        if length <= sng_ln_len:
            new_log_pos = TLog.LogPos(begin_row=start_row,
                                      begin_col=0,
                                      end_row=start_row,
                                      end_col=length)
        
        else: # length > sng_ln_len:
            rows = int(length / sng_ln_len)
            new_log_pos = TLog.LogPos(begin_row=start_row,
                                      begin_col=0,
                                      end_row=start_row + rows,
                                      end_col= length - rows * sng_ln_len)
        
        self.msg_coo.append(new_log_pos)
        self._redirect_strs(new_log_pos)


        coo = self.msg_coo[-1]
        ind = 0
        for row in range(coo.begin_row, coo.end_row + 1): 
            if row == coo.end_row: 
                ran = range(coo.begin_col, coo.end_col)
            else: 
                ran = range(sng_ln_len)
            for col in ran:
                self._data[row][col] = msg[ind]
                ind += 1


class TFullWindow(TWindow):
    def __init__(self):
        super().__init__(1,1,*_get_terminal_res())



import time

def main():

    # sys.stdout.write('\033[?1049h')
    # TC.switch_buffer()
    # p = TWindow(5,5,30,70, title=f'{"1" * 100}')
    p = TLog(3,3,30,50,msg_format=r'...{msg}', title='hi')
    p = p.full()

    l, r = p.hsplit()

    j = 0
    
    while True:
        for i in range(0, 30):
            f = ' '.join([str(k) for k in range(0, i)])
            l.add_msg(f'{f}')
            j += 1

        # p.draw_frame(isroot=True)
        # p.draw_text(isroot=True)
        time.sleep(.05)
        # p.clear()


    
    # p.hsplit()
    # p.draw_frame(isroot=True)
    # time.sleep(2)
    # TC.clear_buffer()
    #
    # p.wsplit()
    # p.draw_frame(isroot=True)
    # time.sleep(2)
    # TC.clear_buffer()
    # #
    # p.wsplit()
    # p.draw_frame(isroot=True)
    # time.sleep(2)
    # TC.clear_buffer()
    #
    time.sleep(5)
    # TC.switch_buffer()
    

if __name__ == '__main__':
   main() 
