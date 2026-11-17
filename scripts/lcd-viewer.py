#!/usr/bin/env python3
# Copyright 2026 Lee Bussy
# SPDX-License-Identifier: MIT
"""Independently drawn 20x4 LCD with local physical controls. Private local IPC, never serial."""
import os
import sys
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
    if not isinstance(item, dict) or type(item.get('version')) is not int or item['version'] != 2:
        raise ValueError('invalid message version')
    if item.get('type') == 'heartbeat' and set(item) == {'version', 'type'}:
        return item
    if item.get('type') == 'ack':
        if set(item) != {'version', 'type', 'session', 'id', 'epoch', 'status'}:
            raise ValueError('invalid acknowledgment')
        if not isinstance(item['session'], str) or not 0 < len(item['session']) <= 80:
            raise ValueError('invalid session')
        if type(item['id']) is not int or not 0 < item['id'] < 2**53:
            raise ValueError('invalid action ID')
        if type(item['epoch']) is not int or not 0 <= item['epoch'] < 2**53:
            raise ValueError('invalid epoch')
        if not isinstance(item['status'], str) or len(item['status']) > 100:
            raise ValueError('invalid status')
        return item
    if item.get('type') != 'frame' or set(item) != {'version', 'type', 'sequence', 'rows',
                                                   'dim', 'door', 'status', 'session', 'epoch'}:
        raise ValueError('invalid frame schema')
    if type(item['sequence']) is not int or not 0 < item['sequence'] <= 2**53 - 1:
        raise ValueError('invalid frame sequence')
    if type(item['dim']) is not bool or type(item['door']) is not bool:
        raise ValueError('invalid display metadata')
    if not isinstance(item['status'], str) or len(item['status']) > 100:
        raise ValueError('invalid status')
    if not isinstance(item['session'], str) or not 0 < len(item['session']) <= 80:
        raise ValueError('invalid session')
    if type(item['epoch']) is not int or not 0 <= item['epoch'] < 2**53:
        raise ValueError('invalid epoch')
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
        from tkinter import font, ttk
        if tk.TkVersion < 8.6:
            raise RuntimeError('LCD requires Tk 8.6 or later')
        self.channel = channel
        self.root = tk.Tk()
        self.root.title('BrewPi Emulator — LCD')
        self.root.minsize(560, 360)
        self.root.geometry('720x420')
        self.canvas = tk.Canvas(self.root, background='#9cba69', highlightthickness=0, height=160, width=480)
        self.canvas.pack(fill='both', expand=True)
        self.font = font.nametofont('TkFixedFont').copy()
        self.font.configure(size=22)
        self.cells = [self.canvas.create_text(0, 0, text=' ', fill='#162711',
                                            font=self.font, anchor='center')
                      for _ in range(80)]
        self.rows = [' ' * 20 for _ in range(4)]
        self.sequence = 0
        self.session = None
        self.epoch = 0
        self.frame_epoch = 0
        self.action_id = 0
        self.pending = None
        self.door_open = False
        self.keys = {}
        controls = ttk.Frame(self.root, padding=(16, 10))
        controls.pack(fill='x')
        self.encoder = tk.Canvas(controls, width=110, height=110, highlightthickness=2,
                                 highlightbackground='#617f3e', highlightcolor='#162711',
                                 takefocus=True, background='#e1e9d2')
        self.encoder.pack(side='left', padx=(0, 18))
        self.encoder.create_oval(5, 5, 105, 105, fill='#617f3e', outline='#162711', width=2)
        self.encoder.create_line(55, 9, 55, 24, fill='#e1e9d2', width=4)
        self.encoder.create_oval(29, 29, 81, 81, fill='#e1e9d2', outline='#162711', width=2)
        self.encoder.create_text(55, 55, text='Press', fill='#162711')
        self.encoder.bind('<Button-1>', self.knob)
        self.stacked = None
        self.buttons = []
        for label, command in [('Counterclockwise', 'ccw'), ('Press', 'press'), ('Clockwise', 'cw')]:
            button = ttk.Button(controls, text=label, command=lambda c=command: self.action(c))
            button.pack(side='left', padx=3)
            self.bind_keys(button, command, encoder=True)
            self.buttons.append(button)
        self.bind_keys(self.encoder, 'press', encoder=True)
        footer = ttk.Frame(self.root, padding=(16, 0, 16, 12))
        footer.pack(fill='x')
        self.door_button = ttk.Button(footer, text='Open door', command=self.door_action)
        self.door_button.pack(side='right')
        self.bind_keys(self.door_button, 'door', encoder=False)
        self.status = ttk.Label(footer, text='Connecting controls…', wraplength=360)
        self.status.pack(side='left', fill='x', expand=True)
        self.enable_controls(False)
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
        packet = json.dumps({'version': 2, 'type': kind}, separators=(',', ':')).encode()
        try:
            self.channel.send(packet)
            return True
        except OSError:
            return False

    def enable_controls(self, enabled):
        for button in self.buttons + [self.door_button]:
            button.state(['!disabled'] if enabled else ['disabled'])

    def bind_keys(self, widget, command, encoder):
        def down(event):
            key = event.keysym
            if key in self.keys:
                if self.keys[key] is not None:
                    self.root.after_cancel(self.keys[key])
                    self.keys[key] = None
                return 'break'
            self.keys[key] = None
            if key in ('Left', 'Right'):
                self.action('ccw' if key == 'Left' else 'cw')
            elif command == 'door':
                self.door_action()
            else:
                self.action(command)
            return 'break'
        def up(event):
            key = event.keysym
            if key in self.keys:
                self.keys[key] = self.root.after(30, lambda: self.keys.pop(key, None))
            return 'break'
        for key in (['Left', 'Right', 'Return', 'space'] if encoder else ['Return', 'space']):
            widget.bind('<KeyPress-' + key + '>', down)
            widget.bind('<KeyRelease-' + key + '>', up)

    def clear_keys(self, event=None):
        for callback in self.keys.values():
            if callback is not None:
                self.root.after_cancel(callback)
        self.keys.clear()

    def knob(self, event):
        self.encoder.focus_set()
        if (event.x - 55)**2 + (event.y - 55)**2 <= 26**2:
            self.action('press')
        else:
            self.action('cw' if event.x >= 55 else 'ccw')

    def door_action(self):
        self.action('door close' if self.door_open else 'door open')

    def action(self, command):
        if self.closing:
            return
        if not self.ready or not self.session:
            self.status.configure(text='Controls not ready')
            return
        if self.pending or self.frame_epoch < self.epoch:
            self.status.configure(text='Busy; waiting for current display')
            return
        self.action_id += 1
        packet = dict(version=2, type='action', session=self.session, id=self.action_id,
                      epoch=self.epoch, command=command)
        try:
            self.channel.send(json.dumps(packet, separators=(',', ':')).encode())
        except OSError:
            self.status.configure(text='Action not sent; controls disconnected')
            self.emit('error')
            self.root.destroy()
            return
        self.pending = time.monotonic()
        self.enable_controls(False)
        self.status.configure(text='Applying action…')

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
        stacked = self.root.winfo_width() < 680
        if self.stacked != stacked:
            self.stacked = stacked
            for button in self.buttons:
                button.pack_forget()
                button.pack(side='top' if stacked else 'left',
                            fill='x' if stacked else 'none', padx=3, pady=2)
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
                    newest = item
                elif item['type'] == 'ack':
                    if item['session'] != self.session or not self.pending or item['id'] != self.action_id:
                        raise ValueError('unexpected action acknowledgment')
                    self.epoch = max(self.epoch, item['epoch'])
                    self.pending = None
                    self.status.configure(text=item['status'])
            if newest is not None and newest['epoch'] >= self.epoch:
                if self.session is not None and newest['session'] != self.session:
                    raise ValueError('session changed')
                self.session = newest['session']
                self.epoch = max(self.epoch, newest['epoch'])
                self.frame_epoch = newest['epoch']
                self.rows = newest['rows']
                self.door_open = newest['door']
                self.door_button.configure(text='Close door' if self.door_open else 'Open door')
                self.canvas.itemconfigure('all', fill='#384624' if newest['dim'] else '#162711')
                if not self.pending:
                    self.status.configure(text=newest['status'])
                self.layout()
            self.enable_controls(self.ready and self.session is not None and not self.pending
                                 and self.frame_epoch >= self.epoch)
            now = time.monotonic()
            if self.pending and now - self.pending >= 5:
                raise ValueError('action acknowledgment timed out')
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
    transport = parser.add_mutually_exclusive_group(required=True)
    transport.add_argument('--fd', type=int)
    transport.add_argument('--pipe')
    parser.add_argument('--parent-pid', type=int)
    args = parser.parse_args()
    if args.pipe is not None:
        if os.name != 'nt' or args.parent_pid is None:
            parser.error('--pipe requires native Windows and --parent-pid')
        # Isolated Python excludes the script directory from sys.path. Load
        # only the adjacent installed original helper, without bytecode writes.
        import importlib.util
        from pathlib import Path
        sys.dont_write_bytecode = True
        spec = importlib.util.spec_from_file_location(
            'rmx_windows_channel', Path(__file__).with_name('windows_channel.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        channel = module.PacketPipe(args.pipe, args.parent_pid)
    else:
        if os.name == 'nt' or args.parent_pid is not None:
            parser.error('--fd requires POSIX and excludes --parent-pid')
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
            channel.send(b'{"version":2,"type":"error"}')
        except OSError:
            pass
    finally:
        channel.close()


if __name__ == '__main__':
    raise SystemExit(main())
