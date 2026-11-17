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
    fields = {'version', 'type', 'sequence', 'rows', 'dim', 'door', 'status', 'session', 'epoch'}
    if item.get('type') != 'frame' or set(item) not in (fields, fields | {'equipment'}):
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
    equipment = item.get('equipment', [-1]*4)
    if (not isinstance(equipment, list) or len(equipment) != 4
            or any(type(value) is not int or value not in (-1, 0, 1) for value in equipment)):
        raise ValueError('invalid equipment states')
    rows = item['rows']
    if not isinstance(rows, list) or len(rows) != 4:
        raise ValueError('invalid LCD rows')
    for row in rows:
        if not isinstance(row, str) or len(row) != 20:
            raise ValueError('invalid LCD width')
        if any(not (' ' <= cell <= '~' or cell == '°') for cell in row):
            raise ValueError('unsupported LCD cell')
    return item


# Original geometry in a 32-unit square; no imported icon paths or assets.
def icon_strokes(name):
    import math
    def arc(cx, cy, radius, start, end, steps=32):
        return [(cx + radius * math.cos(math.radians(start + (end-start)*i/steps)),
                 cy + radius * math.sin(math.radians(start + (end-start)*i/steps)))
                for i in range(steps+1)]
    if name in ('cw', 'ccw'):
        path = arc(16, 16, 10, -135, 135)
        tip, previous = path[-1], path[-2]
        dx, dy = tip[0]-previous[0], tip[1]-previous[1]
        length = math.hypot(dx, dy); dx, dy = dx/length, dy/length
        head = [(tip[0]-5*dx+4*dy, tip[1]-5*dy-4*dx), tip,
                (tip[0]-5*dx-4*dy, tip[1]-5*dy+4*dx)]
        paths = [path, head]
        return [[(32-x, y) for x, y in p] for p in paths] if name == 'ccw' else paths
    if name == 'press':
        return [[(16, 3), (16, 18)], [(10, 12), (16, 18), (22, 12)],
                [(6, 23), (26, 23), (26, 29), (6, 29), (6, 23)]]
    if name == 'heater':
        return [[(16, 2), (18, 9), (24, 15), (26, 21), (24, 26), (19, 29),
                 (12, 29), (7, 26), (5, 21), (7, 15), (10, 12), (10, 19),
                 (14, 16), (17, 10), (16, 2)]]
    if name == 'cooler':
        paths = []
        for degrees in (0, 60, 120):
            angle = math.radians(degrees); dx, dy = math.cos(angle), math.sin(angle)
            paths.append([(16-12*dx, 16-12*dy), (16+12*dx, 16+12*dy)])
            for side in (-1, 1):
                x, y = 16+side*7*dx, 16+side*7*dy
                paths.append([(x-side*3*dx-3*dy, y-side*3*dy+3*dx), (x, y),
                              (x-side*3*dx+3*dy, y-side*3*dy-3*dx)])
        return paths
    if name == 'fan':
        paths = [arc(16, 16, 2, 0, 360)]
        blade = [(0, -3), (-3, -9), (-2, -13), (3, -14), (7, -11),
                 (7, -7), (3, -3), (0, -3)]
        for degrees in (0, 90, 180, 270):
            a = math.radians(degrees)
            paths.append([(16+x*math.cos(a)-y*math.sin(a),
                           16+x*math.sin(a)+y*math.cos(a)) for x, y in blade])
        return paths
    if name == 'no':
        return [arc(16, 16, 15, 0, 360), [(5, 5), (27, 27)]]
    if name == 'light':
        return [arc(16, 12, 9, 150, 390), [(8.2, 16.5), (11, 22), (21, 22), (23.8, 16.5)],
                [(11, 26), (21, 26)], [(13, 30), (19, 30)]]
    if name == 'door open':
        return [[(8, 29), (8, 3), (25, 3), (25, 29)],
                [(8, 3), (19, 7), (19, 29), (8, 25)], [(15, 17), (16, 17)],
                [(3, 29), (29, 29)]]
    if name == 'door close':
        return [[(8, 29), (8, 3), (25, 3), (25, 29)], [(20, 16), (21, 16)],
                [(3, 29), (29, 29)]]
    raise ValueError('unknown original icon')


def canvas_icon(canvas, name, x, y, size, color, tag):
    for points in icon_strokes(name):
        coords = [value for px, py in points for value in (x+(px-16)*size/32, y+(py-16)*size/32)]
        canvas.create_line(*coords, fill=color, width=2, capstyle='round', joinstyle='round', tags=(tag, name))


def button_image(tk, name, color='#273125', size=28, face=False):
    # Rasterize only these original strokes for native button images. Keep the
    # surrounding pixels transparent; no platform-dependent symbol font.
    import math
    image = tk.PhotoImage(width=size, height=size)
    if face:
        for y in range(size):
            for x in range(size):
                radius = math.hypot(x-(size-1)/2, y-(size-1)/2)
                if radius <= size/2-1:
                    image.put('#31412a' if radius > size/2-3 else '#e1e9d2', (x, y))
    pixels = set()
    inset = size*.23 if face else 2
    scale = (size-2*inset)/32
    for path in icon_strokes(name):
        points = [(inset+x*scale, inset+y*scale) for x, y in path]
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            dx, dy = x1-x0, y1-y0; length = dx*dx+dy*dy
            for y in range(max(0, int(min(y0,y1))-2), min(size, math.ceil(max(y0,y1))+2)):
                for x in range(max(0, int(min(x0,x1))-2), min(size, math.ceil(max(x0,x1))+2)):
                    t = max(0, min(1, ((x-x0)*dx+(y-y0)*dy)/length)) if length else 0
                    if (x-x0-t*dx)**2+(y-y0-t*dy)**2 <= 1.25**2:
                        pixels.add((x, y))
    for point in pixels:
        image.put(color, point)
    return image


class Tooltip:
    def __init__(self, widget, text):
        self.widget, self.text = widget, text
        self.callback = self.window = None
        for event in ('<Enter>', '<FocusIn>'):
            widget.bind(event, self.schedule, add='+')
        for event in ('<Leave>', '<FocusOut>', '<ButtonPress>', '<Destroy>'):
            widget.bind(event, self.hide, add='+')

    def schedule(self, event=None):
        self.hide()
        self.callback = self.widget.after(500, self.show)

    def show(self):
        import tkinter as tk
        self.callback = None
        if not self.widget.winfo_exists() or not self.widget.winfo_ismapped():
            return
        self.window = tk.Toplevel(self.widget)
        self.window.overrideredirect(True)
        self.window.geometry('+%d+%d' % (self.widget.winfo_rootx(),
                                        self.widget.winfo_rooty()+self.widget.winfo_height()+4))
        tk.Label(self.window, text=self.text, background='#f4f6ec', foreground='#273125',
                 borderwidth=1, relief='solid', padx=7, pady=4).pack()

    def hide(self, event=None):
        if self.callback is not None:
            self.widget.after_cancel(self.callback)
            self.callback = None
        if self.window is not None:
            self.window.destroy()
            self.window = None


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
        self.equipment = [-1]*4
        self.equipment_canvas = tk.Canvas(self.root, height=62, background='#242d29', highlightthickness=0)
        self.equipment_tip = Tooltip(self.equipment_canvas, 'Modeled physical equipment; N/A means unavailable or no modeled load')
        controls = ttk.Frame(self.root, padding=(16, 10))
        group = ttk.Frame(controls)
        group.pack()
        style = ttk.Style(self.root)
        icon_color = style.lookup('TButton', 'foreground') or '#273125'
        try:
            rgb = self.root.winfo_rgb(icon_color)
            icon_color = '#%02x%02x%02x' % tuple(value//257 for value in rgb)
        except tk.TclError:
            icon_color = '#273125'
        self.images = {name: button_image(tk, name, color=icon_color)
                       for name in ('ccw', 'cw', 'door open', 'door close')}
        self.images['press'] = button_image(tk, 'press', size=58, face=True)
        ccw = ttk.Button(group, text='Counterclockwise', image=self.images['ccw'], width=4,
                         command=lambda: self.action('ccw'))
        ccw.pack(side='left', padx=(0, 18))
        self.encoder = tk.Canvas(group, width=110, height=110, highlightthickness=0,
                                 takefocus=False, background=style.lookup('TFrame', 'background')
                                 or self.root.cget('background'))
        self.encoder.pack(side='left')
        self.encoder.create_oval(5, 5, 105, 105, fill='#617f3e', outline='#31412a', width=2)
        self.encoder.create_line(55, 9, 55, 24, fill='#e1e9d2', width=4)
        self.press_button = tk.Button(self.encoder, text='Press', image=self.images['press'],
                                      command=lambda: self.action('press'), borderwidth=0,
                                      highlightthickness=1, highlightbackground='#617f3e',
                                      highlightcolor='#162711', background='#617f3e',
                                      activebackground='#617f3e', padx=0, pady=0)
        self.press_button.place(x=55, y=55, anchor='center', width=60, height=60)
        self.encoder.bind('<Button-1>', self.knob)
        cw = ttk.Button(group, text='Clockwise', image=self.images['cw'], width=4,
                        command=lambda: self.action('cw'))
        cw.pack(side='left', padx=(18, 0))
        self.buttons = [ccw, self.press_button, cw]
        self.tooltips = [Tooltip(widget, name) for widget, name in
                         zip(self.buttons, ('Counterclockwise', 'Press', 'Clockwise'))]
        for widget, command in zip(self.buttons, ('ccw', 'press', 'cw')):
            self.bind_keys(widget, command, encoder=True)
        self.bind_keys(self.encoder, 'press', encoder=True)
        footer = ttk.Frame(self.root, padding=(16, 0, 16, 12))
        self.door_button = ttk.Button(footer, text='Open door', image=self.images['door close'],
                                      width=4, command=self.door_action)
        footer.columnconfigure(0, weight=1)
        self.door_button.grid(row=0, column=1, sticky='e')
        self.door_tip = Tooltip(self.door_button, 'Door closed — click to open')
        self.bind_keys(self.door_button, 'door', encoder=False)
        self.status = ttk.Label(footer, text='Connecting controls…', wraplength=360)
        self.status.grid(row=0, column=0, sticky='ew')
        # Reserve controls first; the scalable LCD receives the remaining space.
        footer.pack(side='bottom', fill='x')
        controls.pack(side='bottom', fill='x')
        self.equipment_canvas.pack(side='bottom', fill='x')
        self.canvas.pack(side='top', fill='both', expand=True)
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
            button.configure(state='normal' if enabled else 'disabled')

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
        self.draw_equipment()
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

    def draw_equipment(self):
        canvas = self.equipment_canvas
        width = canvas.winfo_width()
        key = (width, tuple(self.equipment))
        if getattr(self, '_equipment_drawn', None) == key:
            return
        self._equipment_drawn = key
        canvas.delete('all')
        colors = ('#ff6658', '#bce8ff', '#d6e8ca', '#f3db8d')
        muted = ('#b56258', '#819da9', '#b7c1bb', '#a99c6a')
        for i, name in enumerate(('heater', 'cooler', 'fan', 'light')):
            x = width*(i+.5)/4
            value = self.equipment[i]
            color = colors[i] if value == 1 else muted[i] if value == 0 else '#a5afa8'
            canvas_icon(canvas, name, x-34, 25, 24, color, 'equipment')
            if name == 'fan' and value == 0:
                canvas_icon(canvas, 'no', x-34, 25, 28, color, 'equipment')
            canvas.create_text(x-14, 17, text=name.capitalize(), anchor='w',
                               fill='#e7eee8', font=('TkDefaultFont', 10))
            canvas.create_text(x-14, 37, text='N/A' if value < 0 else 'On' if value else 'Off',
                               anchor='w', fill='#d5dfd7', font=('TkDefaultFont', 9))

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
                self.equipment = newest.get('equipment', [-1]*4)
                self.door_button.configure(text='Close door' if self.door_open else 'Open door',
                                           image=self.images['door open' if self.door_open else 'door close'])
                self.door_tip.text = ('Door open — click to close' if self.door_open
                                      else 'Door closed — click to open')
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
