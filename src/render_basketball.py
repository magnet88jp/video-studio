"""Render 150 illustrated frames. Requires Pillow. Run from project root.
Then: swift src/encode.swift
"""
from PIL import Image, ImageDraw
from pathlib import Path
import math, json

ROOT = Path(__file__).resolve().parent.parent
FRAMES = ROOT/'work/frames'
FRAMES.mkdir(parents=True, exist_ok=True)
S=2
INK='#24364b'; ORANGE='#f79436'; BLUE='#267eaa'
def mix(a,b,u): return tuple(x+(y-x)*u for x,y in zip(a,b))
def ease(u): return (1-math.cos(math.pi*max(0,min(1,u))))/2
def ball_position(t):
    if t<=1: return mix((345,410),(345,446),ease(t))
    if t<=2: return mix((345,446),(410,242),ease(t-1))
    if t<=3.5:
        u=(t-2)/1.5
        return (410+590*u,242-560*u+603*u*u)
    v=t-3.5
    return (1000+24*v,285+110*v+160*v*v) if v<1 else (1024+24*(v-1),555-120*(v-1)+240*(v-1)**2)

def render(t):
    im=Image.new('RGB',(1280*S,720*S),'#f5f3ec'); d=ImageDraw.Draw(im)
    def line(points,fill=INK,w=5): d.line([(int(x*S),int(y*S)) for x,y in points], fill=fill,width=int(w*S),joint='curve')
    def poly(points,fill,outline=None,w=3):
        pts=[(int(x*S),int(y*S)) for x,y in points]; d.polygon(pts,fill=fill)
        if outline: line(points+[points[0]],outline,w)
    def oval(box,fill,outline=None,w=3): d.ellipse(tuple(int(v*S) for v in box),fill=fill,outline=outline,width=int(w*S))
    def rect(box,fill): d.rectangle(tuple(int(v*S) for v in box),fill=fill)
    rect((0,575,1280,720),'#e7bf83')
    line([(0,575),(1280,575)],'#d9a86d',3)
    line([(0,655),(1280,655)],'#fff4dd',3)
    line([(820,575),(750,720)],'#fff4dd',3)
    # Fixed goal, visible base, transparent board.
    oval((1085,598,1225,623),'#c29c68')
    line([(1155,602),(1155,172),(1100,172)],INK,15)
    rect((1090,143,1105,321),'#cadce2')
    line([(1090,143),(1105,143),(1105,321),(1090,321),(1090,143)],INK,4)
    line([(1090,220),(1090,281),(1069,281)],'#e26c3e',5)
    # Shadow stays on the court as the player jumps.
    oval((233,596,389,615),'#c49f6e')
    if t<=1:
        q=ease(t); lift=0; crouch=36*q
    elif t<=2:
        q=ease(t-1); lift=100*q; crouch=36*(1-q)
    else:
        lift=100*(1-ease((t-2)/2.15)); crouch=10*math.sin(math.pi*max(0,min(1,(t-4.15)/.6)))
    hip=(302,500-lift+crouch*.45); shoulder=(309,411-lift+crouch)
    feet=[(268,591-lift),(353,591-lift)]
    knees=[(256-crouch*.7,544-lift+crouch*.4),(347+crouch*.45,544-lift+crouch*.4)]
    for k,f in zip(knees,feet):
        line([hip,k,f],INK,22); line([hip,k,f],'#c9875b',15)
        line([(f[0]-9,f[1]+5),(f[0]+24,f[1]+5)],INK,15)
        line([(f[0]-8,f[1]+8),(f[0]+24,f[1]+8)],'#f8faf9',4)
    poly([(280,479-lift+crouch*.5),(328,479-lift+crouch*.5),(343,517-lift+crouch*.45),(304,519-lift+crouch*.45),(275,515-lift+crouch*.45)],'#184968',INK)
    poly([(289,shoulder[1]-8),(330,shoulder[1]-8),(335,488-lift+crouch*.45),(279,488-lift+crouch*.45)],BLUE,INK)
    line([(298,shoulder[1]+32),(315,shoulder[1]+32),(303,shoulder[1]+57)],'#fff6dc',5)
    head=(307,shoulder[1]-37)
    line([(307,shoulder[1]-12),(307,shoulder[1]-24)],'#c9875b',18)
    oval((head[0]-22,head[1]-28,head[0]+24,head[1]+22),'#d99a6c',INK,3)
    poly([(285,head[1]-6),(284,head[1]-23),(296,head[1]-32),(322,head[1]-28),(330,head[1]-13),(300,head[1]-17),(294,head[1]-3)],INK)
    oval((320,head[1]-5,324,head[1]-1),INK)
    b=ball_position(t)
    if t<=2: wrist=(b[0],b[1]+18)
    else: wrist=mix((410,shoulder[1]-51),(382,shoulder[1]-39),ease((t-4.3)/.7))
    elbow=(shoulder[0]+46,shoulder[1]+18) if t<1 else mix((355,465),(357,shoulder[1]-35),ease(t-1))
    line([(shoulder[0]-15,shoulder[1]+8),(340,shoulder[1]+30),(wrist[0]-20,wrist[1]-3)],INK,17)
    line([(shoulder[0]-15,shoulder[1]+8),(340,shoulder[1]+30),(wrist[0]-20,wrist[1]-3)],'#c9875b',11)
    line([(shoulder[0]+17,shoulder[1]+7),elbow,wrist],INK,19)
    line([(shoulder[0]+17,shoulder[1]+7),elbow,wrist],'#d99a6c',13)
    line([wrist,(wrist[0]+10,wrist[1]-7)],'#d99a6c',9)
    # Back half of the rim, then the ball, then the net/front rim.
    oval((958,277,1042,293),None,'#be5534',5)
    x,y=b; r=18
    oval((x-r,y-r,x+r,y+r),ORANGE,INK,2)
    line([(x-r+2,y),(x+r-2,y)],INK,1.5)
    line([(x,y-r+1),(x,y+r-1)],INK,1.5)
    line([(x-11,y-14),(x-5,y-7),(x-3,y),(x-5,y+7),(x-11,y+14)],INK,1.5)
    line([(x+11,y-14),(x+5,y-7),(x+3,y),(x+5,y+7),(x+11,y+14)],INK,1.5)
    # Rim attachment stays fixed; the net stretches and swings after entry.
    elapsed=max(0,t-3.5)
    pulse=math.sin(math.pi*min(1,elapsed/.65)) if elapsed<.65 else 0
    swing=25*math.exp(-2*elapsed)*math.sin(12*elapsed) if t>=3.5 else 0
    bottom=341+30*pulse
    def net_point(f,u):
        width=80*(1-u)+44*u+14*pulse*math.sin(math.pi*u)
        return (1000+(f-.5)*width+swing*u*u,287+(bottom-287)*u)
    for i in range(7):
        line([net_point(i/6,j/12) for j in range(13)],'#758d92',2)
    for u in [.3,.6,1]:
        line([net_point(j/12,u) for j in range(13)],'#758d92',2)
    line([(959,286),(967,291),(1033,291),(1041,286)],'#e16d3e',5)
    return im.resize((1280,720),Image.Resampling.LANCZOS)

if __name__=='__main__':
    for i in range(150): render(i/30).save(FRAMES/f'{i:04}.png')
    times=[0,1,1.9666667,2,2.5,3.4666667,3.5,3.8,4.5]
    sheet=Image.new('RGB',(1280*3,720*3))
    for i,t in enumerate(times): sheet.paste(render(t),((i%3)*1280,(i//3)*720))
    sheet.resize((1920,1080)).save(ROOT/'work/contact_sheet.jpg')
    (ROOT/'work/motion_checks.json').write_text(json.dumps({'frames':150,'fps':30,'release':{'time':2,'ball':ball_position(2),'hand':[410,260],'ball_radius':18},'rim_crossing':{'time':3.5,'ball':ball_position(3.5),'rim_center':[1000,285]},'samples':[{'time':i/30,'ball':ball_position(i/30)} for i in range(150)]},indent=2))
