"""Deterministic, offline isometric artwork. Pillow is the only dependency.

No generated art or live telemetry: six physical metaphors of the real projects.
The finite GIF catalogue is built once; scheduled updates only change SVG focus.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
TAU = math.tau
COLORS = ["#27b9bd", "#e6a34e", "#99b479", "#f1784c", "#a797c3", "#91b58c"]
NAMES = ["OBSERVATORY", "FALSIFICATION", "MEMORY", "FLIGHT", "ENCOUNTER", "ECOLOGY"]
POSITIONS = [(0, 0), (5.4, 0), (10.8, 0), (0, 5.4), (5.4, 5.4), (10.8, 5.4)]


def rgb(hex_value):
    return tuple(bytes.fromhex(hex_value.lstrip("#")))


def tint(color, amount):
    c = rgb(color) if isinstance(color, str) else color
    return tuple(max(0, min(255, round(v * amount))) for v in c)


def font(size, bold=False):
    filename = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    paths = [Path("/usr/share/fonts/truetype/dejavu") / filename,
             Path("/usr/share/fonts/truetype/dejavu") / filename]
    for p in paths:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size=size)


class Lab:
    def __init__(self, theme="light", width=1200, height=780, scale=1.5,
                 origin=(610, 280), unit=35):
        self.s, self.w, self.h = scale, width, height
        self.ox, self.oy, self.unit = origin[0], origin[1], unit
        self.dark = theme == "dark"
        self.bg = (19, 25, 30) if self.dark else (246, 245, 239)
        self.ink = (231, 235, 230) if self.dark else (33, 43, 44)
        self.muted = (134, 157, 160) if self.dark else (110, 126, 124)
        self.white = "#d8e0d9" if self.dark else "#fcfcf6"
        self.metal = "#596b6e" if self.dark else "#b9c9c5"
        self.graphite = "#36484d"
        self.im = Image.new("RGB", (round(width*scale), round(height*scale)), self.bg)
        self.d = ImageDraw.Draw(self.im)

    def p(self, x, y, z=0):
        return ((self.ox+(x-y)*self.unit)*self.s,
                (self.oy+(x+y)*self.unit*.5-z*self.unit*.95)*self.s)

    def line(self, points, color, width=1):
        self.d.line([self.p(*p) for p in points], fill=color,
                    width=max(1, round(width*self.s)), joint="curve")

    def poly(self, points, fill, outline=None):
        coords = [self.p(*p) for p in points]
        self.d.polygon(coords, fill=fill)
        if outline:
            self.d.line(coords+[coords[0]], fill=outline, width=max(1, round(self.s)))

    def box(self, x, y, z, a, b, h, color, edge=None):
        self.poly([(x,y+b,z),(x+a,y+b,z),(x+a,y+b,z+h),(x,y+b,z+h)], tint(color,.76), edge)
        self.poly([(x+a,y,z),(x+a,y+b,z),(x+a,y+b,z+h),(x+a,y,z+h)], tint(color,.57), edge)
        self.poly([(x,y,z+h),(x+a,y,z+h),(x+a,y+b,z+h),(x,y+b,z+h)], color, edge)

    def ring(self, x, y, z, r, color, width=1, tilt=0, phase=0):
        self.line([(x+math.cos(a)*r, y+math.sin(a)*r, z+math.sin(a)*tilt)
                   for a in [i*TAU/80+phase for i in range(81)]], color, width)

    def rod(self, x, y, z, r, h, color, cone=False):
        faces=[]
        for i in range(24):
            a,b=i*TAU/24,(i+1)*TAU/24
            x1,y1=x+r*math.cos(a),y+r*math.sin(a)
            x2,y2=x+r*math.cos(b),y+r*math.sin(b)
            end=[(x,y,z+h)] if cone else [(x2,y2,z+h),(x1,y1,z+h)]
            shade=.72+.26*math.cos(a-3.7)
            faces.append((math.sin(a)+math.cos(a),[(x1,y1,z),(x2,y2,z)]+end,tint(color,shade)))
        for _,points,c in sorted(faces): self.poly(points,c)
        if not cone:
            self.poly([(x+r*math.cos(i*TAU/40),y+r*math.sin(i*TAU/40),z+h)
                       for i in range(40)],color)

    def text(self, xy, text, size=14, color=None, bold=False, anchor=None):
        self.d.text((xy[0]*self.s,xy[1]*self.s),text,font=font(round(size*self.s),bold),
                    fill=color or self.ink,anchor=anchor)

    def pedestal(self, x, y, idx):
        self.box(x,y,0,4.25,4.25,.30,self.white)
        self.box(x+.10,y+.10,.30,4.05,4.05,.04,"#dce6de" if self.dark else "#e9eee4")
        for a in range(5):
            self.line([(x+.2+a*.78,y+.2,.35),(x+.2+a*.78,y+4,.35)],
                      "#b6c6bb" if self.dark else "#d3dfd3",.45)
        self.box(x+.36,y+3.82,.37,.52,.18,.05,COLORS[idx])
        px,py=self.p(x+1.2,y+4.65,0)
        self.text((px/self.s,py/self.s),f"0{idx+1}",17,COLORS[idx],True,anchor="mm")
        self.text((px/self.s+27,py/self.s),NAMES[idx],9,self.muted,anchor="lm")

    def observe(self,x,y,t):
        self.box(x+.8,y+.65,.35,2.55,2.0,.5,self.graphite)
        self.box(x+1.75,y+1.35,.85,.35,.35,1.05,self.metal)
        self.ring(x+1.95,y+1.5,2.15,1.25,self.metal,7,tilt=.35)
        self.ring(x+1.95,y+1.5,2.17,1.02,self.white,4,tilt=.29)
        self.ring(x+1.95,y+1.5,2.18,.65,COLORS[0],2,tilt=.19)
        a=TAU*t
        self.line([(x+1.95,y+1.5,2.2),(x+1.95+1.15*math.cos(a),y+1.5+1.15*math.sin(a),2.2+.32*math.sin(a))],COLORS[0],3)
        self.rod(x+1.95,y+1.5,2.15,.09,.22,self.white)
        self.box(x+.45,y+2.8,.35,1.35,.75,.38,self.metal)
        self.box(x+.58,y+2.93,.74,1.04,.51,.02,self.graphite)
        for i in range(8):
            self.box(x+.67+i*.11,y+3.03,.77,.06,.18,.06+.12*math.sin(TAU*(t+i/8))**2,COLORS[0])
        self.box(x+2.15,y+3.05,.35,1.1,.38,.30,self.white)
        for i in range(3): self.rod(x+2.3+i*.32,y+3.22,.67,.05,.05,COLORS[0])

    def verify(self,x,y,t):
        for j in range(3):
            gx=x+.7+j*.86
            c=self.white if j!=1 else self.metal
            self.box(gx,y+.8,.35,.15,2.3,2.6,c)
            self.box(gx+.15,y+.8,2.8,.47,2.3,.15,c)
            self.box(gx+.15,y+.8,.35,.47,.15,2.45,c)
            self.box(gx+.15,y+2.95,.35,.47,.15,2.45,c)
            self.box(gx+.2,y+1.1,2.96,.20,.28,.05,COLORS[1])
        self.line([(x+.3,y+2.1,.85),(x+3.7,y+2.1,.85)],COLORS[0],2)
        packet=(t*3)%3
        self.box(x+.3+packet,y+2,.82,.22,.22,.23,COLORS[0])
        self.box(x+2.7,y+3.25,.35,.65,.45,.18,self.graphite)
        self.box(x+2.85,y+3.32,.54,.17,.19,.12,COLORS[3])
        self.line([(x+2.6,y+2.1,.85),(x+3,y+3.45,.55)],COLORS[3],1.5)

    def memory(self,x,y,t):
        self.box(x+.6,y+.6,.35,2.9,1.15,2.7,self.graphite)
        for level in range(4):
            z=.53+level*.58
            self.box(x+.75,y+1.34,z,2.55,.73,.13,self.metal)
            for i in range(6):
                self.box(x+.85+i*.38,y+1.4,z+.13,.23,.49,.38,
                         self.white if i%3 else COLORS[2])
        self.box(x+.8,y+2.5,.35,2.7,.9,.15,self.metal)
        for i in range(4):
            self.box(x+1.1+i*.06,y+2.55+i*.04,.5+i*.095,1.7,.66,.05,self.white)
        self.box(x+1.3+1.0*math.sin(TAU*t)**2,y+2.72,.97,.33,.37,.04,COLORS[2])

    def flight(self,x,y,t):
        self.box(x+.35,y+.8,.35,.47,.5,4.7,self.graphite)
        for z in [1,1.8,2.6,3.4,4.2,5]:
            self.box(x+.29,y+.75,z,.62,.6,.06,self.metal)
        for z in [1.0,2,3,4]:
            self.line([(x+.82,y+1.3,z),(x+.35,y+1.3,z+.7)],self.metal,1)
        self.box(x+.5,y+.98,3.8,1.55,.13,.12,self.metal)
        # Periodic hover represents a flight study, not footage of the demo.
        rise=.15+.38*(.5-.5*math.cos(TAU*t))
        self.rod(x+2.15,y+2.2,.60+rise,.41,3.25,"#d5dedc")
        self.rod(x+2.15,y+2.2,3.85+rise,.41,1.15,self.white,cone=True)
        for z in [1.1,2,2.9]: self.ring(x+2.15,y+2.2,z+rise,.42,"#869a9b",1)
        self.poly([(x+1.72,y+2.2,.8+rise),(x+1.37,y+2.2,.42+rise),(x+1.75,y+2.2,1.6+rise)],self.graphite)
        self.poly([(x+2.54,y+2.2,.8+rise),(x+2.90,y+2.2,.42+rise),(x+2.53,y+2.2,1.6+rise)],self.graphite)
        self.rod(x+2.15,y+2.2,.40,.26,.26+rise,COLORS[3],cone=True)
        self.box(x+3.1,y+2.2,.35,.35,.35,.8,self.white)
        self.rod(x+3.28,y+2.36,1.15,.22,.25,self.metal)

    def encounter(self,x,y,t):
        self.ring(x+2.1,y+2.1,.39,1.58,self.metal,3)
        for i in range(4):
            a=i*TAU/4+TAU*t
            px,py=x+2.1+1.38*math.cos(a),y+2.1+1.38*math.sin(a)
            self.rod(px,py,.42,.20,.5,self.graphite)
            self.rod(px,py,.95,.13,.23,COLORS[4] if i%2 else COLORS[0])
        self.rod(x+2.1,y+2.1,.35,.43,.65,self.metal)
        self.rod(x+2.1,y+2.1,1.0,.82,.10,self.white)
        for i in range(2): self.box(x+1.6+i*.65,y+1.8,1.13,.39,.5,.06,COLORS[4] if t<.5 else COLORS[0])
        self.ring(x+2.1,y+2.1,1.12,.9,COLORS[4],1)

    def ecology(self,x,y,t):
        self.box(x+.65,y+.65,.35,2.95,2.95,.13,self.graphite)
        for i in range(4):
            xx=x+1+i*.6; yy=y+1.5+.7*math.sin(i*2.3)
            z=.65+.10*math.sin(TAU*t+i)
            self.poly([(xx,yy,z+.20),(xx+.13,yy,z),(xx,yy+.13,z-.12),(xx-.13,yy,z)],COLORS[5])
        self.rod(x+1.25+.4*math.sin(TAU*t),y+2.5,.48,.17,.45,COLORS[0])
        self.rod(x+2.6,y+1.65+.45*math.cos(TAU*t),.48,.22,.6,COLORS[3])
        self.ring(x+2.6,y+1.65+.45*math.cos(TAU*t),.5,.42,COLORS[1],1)
        self.box(x+.75,y+.75,.49,.14,.14,.25,self.white)
        self.box(x+3.3,y+3.3,.49,.14,.14,.25,self.white)

    def model(self,index,x,y,t=0):
        self.pedestal(x,y,index)
        [self.observe,self.verify,self.memory,self.flight,self.encounter,self.ecology][index](x,y,t)

    def finish(self):
        return self.im.resize((self.w,self.h),Image.Resampling.LANCZOS)


def hero(theme="light",t=0):
    lab=Lab(theme)
    lab.text((54,38),"JUHWAN",70,bold=True)
    lab.text((57,123),"S Y S T E M S   I N   M O T I O N",16,lab.muted)
    lab.text((1144,53),"VOL. 01",13,lab.muted,anchor="ra")
    lab.text((1144,78),"SIX EXPERIMENTS / ONE WORKSHOP",10,lab.muted,anchor="ra")
    lab.d.line([(54*lab.s,170*lab.s),(1145*lab.s,170*lab.s)],fill=lab.muted,width=1)
    # Soft cast shadows support physical depth without noisy textures.
    layer=Image.new("RGBA",lab.im.size)
    sd=ImageDraw.Draw(layer)
    for x,y in POSITIONS:
        px,py=lab.p(x+2.4,y+2.5,-.20)
        sd.ellipse((px-125*lab.s,py-48*lab.s,px+135*lab.s,py+53*lab.s),fill=(0,10,14,38 if lab.dark else 24))
    lab.im.paste(layer.filter(ImageFilter.GaussianBlur(18*lab.s)),(0,0),layer.filter(ImageFilter.GaussianBlur(18*lab.s)))
    lab.d=ImageDraw.Draw(lab.im)
    wire="#597271" if lab.dark else "#bdcfc5"
    for i in range(2):
        x,y=POSITIONS[i]
        nx,ny=POSITIONS[i+1]
        lab.line([(x+4,y+2,.1),(nx,y+2,.1)],wire,3)
        q=(t*2-i*.20)%1
        lab.box(x+4+q*(nx-x-4),y+1.9,.12,.18,.18,.15,COLORS[i])
    for x in [2.1,7.5,12.9]: lab.line([(x,4.2,.1),(x,5.5,.1)],wire,2)
    for index in [0,1,3,2,4,5]:
        x,y=POSITIONS[index]
        lab.model(index,x,y,t)
    lab.text((57,731),"OBSERVE  /  QUESTION  /  BUILD  /  REMEMBER",11,lab.muted)
    lab.text((1144,731),"A CODE-CRAFTED MINIATURE",10,lab.muted,anchor="ra")
    return lab.finish()


def ribbon(index,theme="light"):
    lab=Lab(theme,width=1200,height=270,scale=2,origin=(167,120),unit=24)
    lab.model(index,0,0,.125)
    lab.text((371,39),f"0{index+1}  /  {NAMES[index]}",13,COLORS[index],True)
    titles=["Stock AutoResearch","KMB / Behavior Lab","Market Memo","STARSHIP","Rotation Talk","VOID HARVEST"]
    lab.text((366,82),titles[index],43,bold=True)
    notes=["SIGNAL → EVENT → FOLLOW-UP","FACT / ESTIMATE / COUNTEREXAMPLE","EVIDENCE HAS A MEMORY","A BROWSER-SIZED FLIGHT STUDY","SAME QUESTION. NEW CONNECTION.","YOU ARE NOT THE ONLY ONE COLLECTING."]
    lab.text((370,155),notes[index],14,lab.muted)
    lab.d.line([(370*lab.s,208*lab.s),(1138*lab.s,208*lab.s)],fill=lab.muted,width=1)
    lab.text((1140,227),"JUHWAN / WORKSHOP",10,lab.muted,anchor="ra")
    return lab.finish()


def build_assets(force=False):
    ASSETS.mkdir(exist_ok=True)
    for theme in ["light","dark"]:
        path=ASSETS/f"workshop-{theme}.gif"
        if force or not path.exists():
            # One stable palette avoids flickering. Durations are exactly 8 seconds.
            palette=hero(theme,.125).quantize(colors=128,method=Image.Quantize.MEDIANCUT)
            frames=[hero(theme,i/80).quantize(palette=palette,dither=Image.Dither.NONE) for i in range(80)]
            frames[0].save(path,save_all=True,append_images=frames[1:],duration=100,
                           loop=0,optimize=True,disposal=1)
            hero(theme,.125).save(ASSETS/f"workshop-{theme}.png",optimize=True)
        for i in range(6):
            path=ASSETS/f"specimen-{i+1:02d}-{theme}.png"
            if force or not path.exists(): ribbon(i,theme).save(path,optimize=True)


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--force",action="store_true")
    args=parser.parse_args()
    build_assets(args.force)
