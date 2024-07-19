import enum
import sys
import os
from typing import Optional, Union, Tuple


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


import numpy as np



class TWindow:
    def __init__(self, r, c, h, w):
        self._h = h
        self._w = w
        self._r = r 
        self._c = c
        self._data = np.full((h - 2, w - 2), '', dtype='U1')
        self._hsplit: Optional[Tuple[TWindow, TWindow]] = None
        self._wsplit: Optional[Tuple[TWindow, TWindow]] = None
    
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
        TC.write_line(f"┌{'─' * (self._w - 2)}┐", end='')
        TC.flush()
        for _ in range( self._r + 1, self._r + self._h - 1):
            TC.go_cursor_to_pos(_, self._c)
            TC.write_line(f"│{' ' * (self._w - 2)}│", end='')
        TC.go_cursor_to_pos(self._r + self._h - 1, self._c)
        TC.write_line(f"└{'─' * (self._w - 2)}┘", end='')
        TC.flush()
        
    def draw_text(self):
        for i,row in enumerate(self._data):
            TC.go_cursor_to_pos(self._r + 1 + i, self._c + 1)
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
                       left_col)
        
        right = self.__class__(self._r, 
                        self._c + left_col,
                        self._h,
                        self._w - left_col)
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
                      self._w)
        
        bot = self.__class__(self._r + top_row, 
                      self._c,
                      self._h - top_row,
                      self._w)
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
    def __init__(self, row, col, h, w):
        """
            ( start_row, start_col, end_row, end_col )
        """
        super().__init__(row, col, h, w)
        self.msg_coo = []

    def add_msg(self, msg: str):
        length = len(msg)
        sng_ln_len = self._w - 2
        if self.msg_coo: 
            start_row = self.msg_coo[-1][2] + 1 
        else: 
            start_row = 0

        if length <= sng_ln_len:
            self.msg_coo.append( (start_row, 0, 
                                  start_row, length ) )
        elif length > sng_ln_len:
            rows = int(length / sng_ln_len)
            self.msg_coo.append( (start_row, 0,
                                  start_row + rows,  length - rows * sng_ln_len) )
        coo = self.msg_coo[-1]
        ind = 0
        for row in range(coo[0], coo[2] + 1): 
            if row == coo[2]: 
                ran = range(coo[1], coo[3])
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
    TC.switch_buffer()
    # p = TWindow(5,5,30,70)
    p = TLog(3,3, 20, 30)
    j = 0
    for i in range(0, 40, 5):
        f = ' '.join([str(k) for k in range(0, i)])
        p.add_msg(f'{j}){f}')
        j += 1
    # p.add_msg(f'{"!" * 30}')
    # p.add_msg(f'{"-" * 30}')
    p.draw_frame()
    p.draw_text()


    
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
    TC.switch_buffer()
    

if __name__ == '__main__':
   main() 
