"""Rounded controls for the Soares Soluções Tkinter interface."""
import tkinter as tk
from tkinter import font as tkfont


class RoundedButton(tk.Canvas):
    def __init__(self, master, text='', command=None, bg='#0F2747', fg='white',
                 activebackground=None, activeforeground=None, padx=14, pady=8,
                 font=('Segoe UI', 10), anchor='center', cursor='hand2',
                 bd=0, relief=None, **kwargs):
        self._surface = master.cget('bg')
        self._normal = bg
        self._hover = activebackground or bg
        self._fg = fg
        self._hover_fg = activeforeground or fg
        self._text = text
        self._command = command
        self._font = font
        self._padx = int(padx)
        self._pady = int(pady)
        self._anchor = anchor
        self._hovered = False
        self._enabled = True
        measure = tkfont.Font(font=font)
        width = measure.measure(text) + self._padx * 2
        height = measure.metrics('linespace') + self._pady * 2
        super().__init__(master, width=width, height=height, bg=self._surface,
                         highlightthickness=0, bd=0, cursor=cursor)
        self.bind('<Configure>', self._draw)
        self.bind('<Enter>', self._enter)
        self.bind('<Leave>', self._leave)
        self.bind('<ButtonRelease-1>', self._click)

    def _draw(self, event=None):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        if w < 3 or h < 3:
            return
        r = min(14, h // 2, w // 2)
        fill = self._hover if self._hovered else self._normal
        self.create_polygon(r, 0, w-r, 0, w, r, w, h-r, w-r, h,
                            r, h, 0, h-r, 0, r, smooth=True, splinesteps=16,
                            fill=fill, outline=fill)
        x = self._padx if self._anchor == 'w' else w // 2
        self.create_text(x, h // 2, anchor='w' if self._anchor == 'w' else 'center',
                         text=self._text, font=self._font,
                         fill=self._hover_fg if self._hovered else self._fg)

    def _enter(self, event):
        self._hovered = True
        self._draw()

    def _leave(self, event):
        self._hovered = False
        self._draw()

    def _click(self, event):
        if self._enabled and self._command and 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height():
            self._command()

    def configure(self, cnf=None, **kwargs):
        if 'state' in kwargs:
            self._enabled = kwargs.pop('state') != 'disabled'
            self._hovered = False
            self._draw()
        return super().configure(cnf, **kwargs)

    config = configure


class RoundedEntry(tk.Canvas):
    """A rounded search field with a native keyboard accessible text entry."""
    def __init__(self, master, textvariable=None, width=220, **kwargs):
        surface = master.cget('bg')
        super().__init__(master, width=max(120, width), height=38, bg=surface,
                         highlightthickness=0, bd=0)
        self._entry = tk.Entry(self, textvariable=textvariable, relief='flat',
                               bd=0, bg='white', fg='#172B4D',
                               font=('Segoe UI', 10), **kwargs)
        self._window = self.create_window(16, 19, window=self._entry, anchor='w')
        self.bind('<Configure>', self._draw)
        self.bind('<Button-1>', lambda _event: self._entry.focus_set())

    def _draw(self, event=None):
        self.delete('shape')
        w, h = self.winfo_width(), self.winfo_height()
        if w < 38:
            return
        self.create_polygon(18, 1, w-18, 1, w-1, 18, w-1, h-18,
                            w-18, h-1, 18, h-1, 1, h-18, 1, 18,
                            smooth=True, splinesteps=16, fill='white',
                            outline='#D0D5DD', width=1, tags='shape')
        self.tag_lower('shape')
        self.itemconfigure(self._window, width=max(1, w-32), height=max(1, h-12))

    def bind(self, sequence=None, func=None, add=None):
        if sequence in ('<Configure>', '<Button-1>'):
            return super().bind(sequence, func, add)
        return self._entry.bind(sequence, func, add)

    def focus_set(self):
        return self._entry.focus_set()

    def selection_range(self, *args):
        return self._entry.selection_range(*args)

    def get(self):
        return self._entry.get()

    def insert(self, *args):
        return self._entry.insert(*args)

    def delete(self, *args):
        return self._entry.delete(*args)
