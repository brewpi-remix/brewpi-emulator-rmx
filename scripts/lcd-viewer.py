#!/usr/bin/env python3
# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Read-only, independently drawn 20x4 LCD. Private local IPC, never serial."""
import argparse
import json
import socket
import time

LIMIT = 4096


def decode(data):
    if not data or len(data) > LIMIT:
        raise ValueError('invalid datagram size')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate message key')
            result[key] = value
        return result
    item = json.loads(data.decode('utf-8'), object_pairs_hook=unique)
    if not isinstance(item, dict) or type(item.get('version')) is not int or item['version'] != 1:
        raise ValueError('invalid message version')
    if item.get('type') == 'heartbeat' and set(item) == {'version', 'type'}:
        return item
    if item.get('type') != 'frame' or set(item) != {'version', 'type', 'sequence', 'rows'}:
        raise ValueError('invalid frame schema')
    if type(item['sequence']) is not int or not 0 < item['sequence'] <= 2**53 - 1:
        raise ValueError('invalid frame sequence')
    rows = item['rows']
    if not isinstance(rows, list) or len(rows) != 4:
        raise ValueError('invalid LCD rows')
    for row in rows:
        if not isinstance(row, str) or len(row) != 20:
            raise ValueError('invalid LCD width')
        if any(not (' ' <= cell <= '~' or cell == '°') for cell in row):
            raise ValueError('unsupported LCD cell')
    return item


class Viewer:
    def __init__(self, channel):
        # Import after channel setup so missing Tk is a structured error.
        import tkinter as tk
        from tkinter import font
        if tk.TkVersion < 8.6:
            raise RuntimeError('LCD requires Tk 8.6 or later')
        self.channel = channel
        self.root = tk.Tk()
        self.root.title('BrewPi Emulator — LCD')
        self.root.minsize(480, 152)
        self.root.geometry('720x232')
        self.canvas = tk.Canvas(self.root, background='#9cba69', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self.font = font.nametofont('TkFixedFont').copy()
        self.font.configure(size=22)
        self.cells = [self.canvas.create_text(0, 0, text=' ', fill='#162711',
                                            font=self.font, anchor='center')
                      for _ in range(80)]
        self.rows = [' ' * 20 for _ in range(4)]
        self.sequence = 0
        self.parent_seen = time.monotonic()
        self.next_progress = 0
        self.ready = False
        self.closing = False
        self.root.bind('<Configure>', self.layout)
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        if self.root.tk.call('tk', 'windowingsystem') == 'aqua':
            self.root.createcommand('tk::mac::Quit', self.close)
        self.root.after(30, self.poll)
        self.root.after_idle(self.painted)

    def emit(self, kind):
        packet = json.dumps({'version': 1, 'type': kind}, separators=(',', ':')).encode()
        try:
            self.channel.send(packet)
            return True
        except OSError:
            return False

    def close(self):
        self.closing = True
        self.emit('close')
        self.root.destroy()

    def painted(self):
        if not self.root.winfo_ismapped():
            self.root.after(30, self.painted)
            return
        self.layout()
        self.root.update_idletasks()
        if self.emit('ready'):
            self.ready = True
            self.next_progress = time.monotonic() + 1
        else:
            self.root.after(30, self.painted)

    def layout(self, event=None):
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        cw, ch = (width - 40) / 20, (height - 32) / 4
        # Tk negative font sizes are pixels; scale to both dimensions.
        self.font.configure(size=-max(8, int(min(cw * 1.35, ch * .63))))
        for r in range(4):
            for c in range(20):
                index = r * 20 + c
                self.canvas.coords(self.cells[index], 20 + (c + .5) * cw, 16 + (r + .5) * ch)
                self.canvas.itemconfigure(self.cells[index], text=self.rows[r][c])

    def poll(self):
        try:
            newest = None
            for _ in range(7):
                try:
                    data = self.channel.recv(LIMIT + 1)
                except (BlockingIOError, InterruptedError):
                    break
                item = decode(data)
                self.parent_seen = time.monotonic()
                if item['type'] == 'frame':
                    if item['sequence'] <= self.sequence:
                        raise ValueError('nonincreasing frame sequence')
                    self.sequence = item['sequence']
                    newest = item['rows']
            if newest is not None:
                self.rows = newest
                self.layout()
            now = time.monotonic()
            if now - self.parent_seen >= 10:
                self.root.destroy()
                return
            if self.ready and now >= self.next_progress and self.emit('progress'):
                self.next_progress = now + 1
            self.root.after(30, self.poll)
        except Exception:
            self.emit('error')
            self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fd', type=int, required=True)
    args = parser.parse_args()
    channel = socket.socket(fileno=args.fd)
    channel.setblocking(False)
    try:
        viewer = Viewer(channel)
        viewer.run()
        # Reliable close intent even when the socket was backpressured or the
        # parent reaps this process before consuming the close datagram.
        return 10 if viewer.closing else 0
    except Exception:
        try:
            channel.send(b'{"version":1,"type":"error"}')
        except OSError:
            pass
    finally:
        channel.close()


if __name__ == '__main__':
    raise SystemExit(main())
