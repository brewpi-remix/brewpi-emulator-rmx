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


# Original vector geometry in a 32-unit square; no imported paths or assets.
def icon_strokes(name):
    import math

    def arc(cx, cy, radius, start, end):
        steps = max(12, int(abs(end-start)/3))
        return [(cx+radius*math.cos(math.radians(start+(end-start)*i/steps)),
                 cy+radius*math.sin(math.radians(start+(end-start)*i/steps)))
                for i in range(steps+1)]

    def curve(start, *segments):
        points = [start]
        for first, second, end in segments:
            x, y = points[-1]
            for i in range(1, 25):
                t = i/24; u = 1-t
                points.append((u**3*x+3*u*u*t*first[0]+3*u*t*t*second[0]+t**3*end[0],
                               u**3*y+3*u*u*t*first[1]+3*u*t*t*second[1]+t**3*end[1]))
        return points

    if name in ('cw', 'ccw'):
        path = arc(16, 17, 10, 35, 270)
        head = [(15, 1), (25, 7), (15, 13), (15, 1)]
        paths = [path, head]
        return [[(32-x, y) for x, y in p] for p in paths] if name == 'ccw' else paths
    if name == 'press':
        return [[(16, 3), (16, 14)], [(10, 12), (16, 21), (22, 12), (10, 12)],
                [(6, 25), (26, 25), (26, 30), (6, 30), (6, 25)]]
    if name == 'heater':
        return [curve((16, 2), ((20, 8), (18, 10), (23, 14)),
                      ((30, 23), (23, 30), (16, 30)),
                      ((6, 30), (3, 23), (7, 17)),
                      ((8, 15), (9, 13), (10, 12)),
                      ((9, 18), (11, 21), (14, 18)),
                      ((19, 13), (17, 9), (16, 2)))]
    if name == 'cooler':
        paths = []
        for degrees in range(0, 360, 60):
            a = math.radians(degrees); dx, dy = math.cos(a), math.sin(a)
            paths.append([(16, 16), (16+12*dx, 16+12*dy)])
            paths.append([(16+10*dx-3*dy, 16+10*dy+3*dx),
                          (16+7*dx, 16+7*dy),
                          (16+10*dx+3*dy, 16+10*dy-3*dx)])
        return paths
    if name == 'fan':
        paths = [arc(16, 16, 2.5, 0, 360)]
        blade = curve((14, 13), ((10, 11), (9, 6), (13, 3)),
                      ((17, 0), (25, 3), (25, 7)),
                      ((25, 11), (20, 10), (18, 14)),
                      ((17, 12), (15, 12), (14, 13)))
        for degrees in (0, 120, 240):
            a = math.radians(degrees)
            paths.append([(16+(x-16)*math.cos(a)-(y-16)*math.sin(a),
                           16+(x-16)*math.sin(a)+(y-16)*math.cos(a)) for x, y in blade])
        return paths
    if name == 'no':
        return [arc(16, 16, 14, 0, 360), [(6, 6), (26, 26)]]
    if name == 'light':
        return [curve((11, 22), ((11, 18), (7, 17), (7, 11)),
                      ((7, -1), (25, -1), (25, 11)),
                      ((25, 17), (21, 18), (21, 22))),
                [(11, 22), (21, 22)], [(11, 26), (21, 26)], [(13, 30), (19, 30)]]
    if name in ('door open', 'door close'):
        body = [(10, 2), (23, 2)]
        body += curve((23, 2), ((24.5, 2), (25, 2.5), (25, 4)))[1:]
        body += [(25, 27)]
        body += curve((25, 27), ((25, 28.5), (24.5, 29), (23, 29)))[1:]
        body += [(10, 29)]
        body += curve((10, 29), ((8.5, 29), (8, 28.5), (8, 27)))[1:]
        body += [(8, 4)]
        body += curve((8, 4), ((8, 2.5), (8.5, 2), (10, 2)))[1:]
        paths = [body, [(8, 11), (25, 11)], [(22, 5), (22, 8)],
                 [(10, 29), (10, 30)], [(23, 29), (23, 30)]]
        if name == 'door open':
            return paths + [[(8, 12), (2, 15), (2, 29), (8, 27), (8, 12)],
                            [(4, 20), (4, 24)], [(11, 18), (23, 18)],
                            [(11, 23), (23, 23)]]
        return paths + [[(22, 15), (22, 21)]]
    raise ValueError('unknown original icon')


def icon_png(name, color, size, face=False, focused=False):
    """Supersample original vectors and encode an RGBA PNG using only the stdlib."""
    import math
    import struct
    import zlib

    samples = 6
    width = size*samples
    coverage = bytearray(width*width)
    prohibition = bytearray(width*width)
    radius = (1.5 if name in ('cw', 'ccw', 'press') else 1.1)*samples

    def draw(paths, inset, filled=False, target=None):
        target = coverage if target is None else target
        scale = (size-2*inset)/32*samples
        for path in paths:
            points = [(inset*samples+x*scale, inset*samples+y*scale) for x, y in path]
            if filled:
                # Even-odd scan conversion of the original closed vector shape.
                for y in range(max(0, math.floor(min(p[1] for p in points))),
                               min(width, math.ceil(max(p[1] for p in points)))):
                    py = y+.5; crossings = []
                    for (x0, y0), (x1, y1) in zip(points, points[1:]):
                        if y0 <= py < y1 or y1 <= py < y0:
                            crossings.append(x0+(py-y0)*(x1-x0)/(y1-y0))
                    crossings.sort()
                    for left, right in zip(crossings[::2], crossings[1::2]):
                        first, last = max(0, math.ceil(left-.5)), min(width, math.ceil(right-.5))
                        target[y*width+first:y*width+last] = b'\x01'*(last-first)
                continue
            for (x0, y0), (x1, y1) in zip(points, points[1:]):
                dx, dy = x1-x0, y1-y0; length = dx*dx+dy*dy
                for y in range(max(0, math.floor(min(y0,y1)-radius)),
                               min(width, math.ceil(max(y0,y1)+radius))):
                    for x in range(max(0, math.floor(min(x0,x1)-radius)),
                                   min(width, math.ceil(max(x0,x1)+radius))):
                        px, py = x+.5-x0, y+.5-y0
                        t = max(0, min(1, (px*dx+py*dy)/length)) if length else 0
                        if (px-t*dx)**2+(py-t*dy)**2 <= radius**2:
                            target[y*width+x] = 1
    if name in ('cw', 'ccw', 'press'):
        paths = icon_strokes(name)
        inset = size*.23 if face else 2
        draw(paths[:1]+paths[2:], inset)
        draw(paths[1:2], inset, filled=True)
    elif name == 'fan off':
        draw(icon_strokes('fan'), 4, filled=True)
        # Clear beneath the slash so it cannot tangle with the fan silhouette.
        for y in range(width):
            for x in range(max(0, y-math.ceil(1.9*samples*math.sqrt(2))),
                           min(width, y+math.ceil(1.9*samples*math.sqrt(2))+1)):
                if abs(x-y) <= 1.9*samples*math.sqrt(2):
                    coverage[y*width+x] = 0
        draw(icon_strokes('no'), 2, target=prohibition)
    else:
        draw(icon_strokes(name), size*.23 if face else 2, filled=name == 'fan')
    rgb = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
    raw = bytearray(); count = samples*samples
    outer = ((size/2-1)*samples)**2
    inner = ((size/2-(5 if focused else 3))*samples)**2
    edge = (22, 39, 17) if focused else (49, 65, 42)
    for y in range(size):
        raw.append(0)  # PNG row filter: none.
        for x in range(size):
            hits = 0; total = [0, 0, 0]
            for sy in range(y*samples, (y+1)*samples):
                for sx in range(x*samples, (x+1)*samples):
                    mark = prohibition[sy*width+sx]
                    hit = coverage[sy*width+sx] or mark; hits += hit
                    ink = (185, 107, 102) if mark else rgb
                    if face:
                        distance = (sx+.5-width/2)**2+(sy+.5-width/2)**2
                        base = (97, 127, 62) if distance > outer else edge if distance > inner else (225, 233, 210)
                        for channel, value in enumerate(ink if hit else base):
                            total[channel] += value
                    elif hit:
                        for channel, value in enumerate(ink):
                            total[channel] += value
            if face:
                raw.extend((*[round(value/count) for value in total], 255))
            else:
                pixel_rgb = tuple(round(value/hits) for value in total) if hits else rgb
                raw.extend((*pixel_rgb, round(255*hits/count)))

    def chunk(kind, data):
        return struct.pack('!I', len(data))+kind+data+struct.pack('!I', zlib.crc32(kind+data))

    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', struct.pack('!2I5B', size, size, 8, 6, 0, 0, 0))+
            chunk(b'IDAT', zlib.compress(raw))+chunk(b'IEND', b''))


def canvas_icon(canvas, name, x, y, size, color, tag):
    import tkinter as tk
    # The set of icon/color/size combinations is fixed by equipment states.
    if not hasattr(canvas, '_icon_images'):
        canvas._icon_images = {}
    key = (name, size, color)
    if key not in canvas._icon_images:
        canvas._icon_images[key] = button_image(tk, name, color=color, size=size)
    tags = (tag, 'fan', 'no') if name == 'fan off' else (tag, name)
    canvas.create_image(x, y, image=canvas._icon_images[key], tags=tags)


def button_image(tk, name, color='#273125', size=28, face=False, focused=False):
    import base64
    return tk.PhotoImage(data=base64.b64encode(icon_png(name, color, size, face, focused)), format='png')


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
        controls = ttk.Frame(self.root, padding=(16, 6))
        controls.columnconfigure(0, weight=1, uniform='control-sides')
        controls.columnconfigure(2, weight=1, uniform='control-sides')
        group = ttk.Frame(controls)
        group.grid(row=0, column=1)
        style = ttk.Style(self.root)
        icon_color = style.lookup('TButton', 'foreground') or '#273125'
        try:
            rgb = self.root.winfo_rgb(icon_color)
            icon_color = '#%02x%02x%02x' % tuple(value//257 for value in rgb)
        except tk.TclError:
            icon_color = '#273125'
        self.images = {name: button_image(tk, name, color=icon_color)
                       for name in ('ccw', 'cw')}
        self.images.update({name: button_image(tk, name, color=icon_color, size=84)
                            for name in ('door open', 'door close')})
        self.images.update({name+' focus': button_image(tk, name, color='#617f3e', size=84)
                            for name in ('door open', 'door close')})
        self.images['press'] = button_image(tk, 'press', size=60, face=True)
        self.images['press focus'] = button_image(tk, 'press', size=60, face=True, focused=True)
        style.layout('Encoder.TButton', [('Button.label', {'sticky': 'nswe'})])
        style.configure('Encoder.TButton', background='#617f3e', padding=0)
        style.layout('Door.TButton', [('Button.label', {'sticky': 'nswe'})])
        ccw = ttk.Button(group, text='Counterclockwise', image=self.images['ccw'], width=4,
                         command=lambda: self.action('ccw'))
        ccw.pack(side='left', padx=(0, 18))
        self.encoder = tk.Canvas(group, width=110, height=110, highlightthickness=0,
                                 takefocus=False, background=style.lookup('TFrame', 'background')
                                 or self.root.cget('background'))
        self.encoder.pack(side='left')
        self.encoder.create_oval(5, 5, 105, 105, fill='#617f3e', outline='#31412a', width=2)
        self.encoder.create_line(55, 9, 55, 24, fill='#e1e9d2', width=4)
        self.press_button = ttk.Button(self.encoder, text='Press',
                                       image=(self.images['press'], 'focus', self.images['press focus']),
                                       command=lambda: self.action('press'), style='Encoder.TButton')
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
        footer = ttk.Frame(self.root, padding=(16, 0, 16, 6))
        door_area = ttk.Frame(controls, width=110, height=110)
        door_area.grid(row=0, column=2, sticky='e', padx=(18, 0))
        self.door_button = ttk.Button(door_area, text='Open door',
                                      image=(self.images['door close'], 'focus', self.images['door close focus']),
                                      width=4, command=self.door_action, style='Door.TButton')
        footer.columnconfigure(0, weight=1)
        self.door_button.place(x=0, y=0, width=110, height=110)
        self.door_tip = Tooltip(self.door_button, 'Door closed — click to open')
        self.bind_keys(self.door_button, 'door', encoder=False)
        self.status = ttk.Label(footer, text='Connecting controls…', wraplength=360)
        self.status.grid(row=0, column=0, sticky='ew')
        # Reserve controls first; the scalable LCD receives the remaining space.
        footer.pack(side='bottom', fill='x')
        controls.pack(side='bottom', fill='x')
        self.equipment_canvas.pack(side='bottom', fill='x')
        self.canvas.pack(side='top', fill='both', expand=True)
        self.root.update_idletasks()
        self.root.minsize(max(560, controls.winfo_reqwidth()), 360)
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
            fan_off = name == 'fan' and value == 0
            canvas_icon(canvas, 'fan off' if fan_off else name, x-34, 25,
                        28 if fan_off else 24, color, 'equipment')
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
                door_icon = 'door open' if self.door_open else 'door close'
                self.door_button.configure(text='Close door' if self.door_open else 'Open door',
                                           image=(self.images[door_icon], 'focus', self.images[door_icon+' focus']))
                self.door_tip.text = ('Door open — click to close' if self.door_open
                                      else 'Door closed — click to open')
                self.canvas.itemconfigure('all', fill='#384624' if newest['dim'] else '#162711')
                if not self.pending:
                    # Terminal command hints do not describe graphical controls.
                    self.status.configure(text='' if newest['status'] == 'cw ccw press help'
                                          else newest['status'])
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
