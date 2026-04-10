"""
ScreenAnnotator v5 DEBUG — finds exact cause of immediate exit
"""
import tkinter as tk
import platform, os, signal, traceback, math, statistics

SYS = platform.system()
signal.signal(signal.SIGINT, lambda s,f: os._exit(0))

import tkinter as tk

def _dist(a,b):  return math.hypot(a[0]-b[0],a[1]-b[1])
def _plen(pts):  return sum(_dist(pts[i],pts[i+1]) for i in range(len(pts)-1))
def _bbox(pts):
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    return min(xs),min(ys),max(xs),max(ys)

print("Step 1: Creating root...")
root = tk.Tk()
print("Step 2: Withdrawing root...")
root.withdraw()
print("Step 3: root.update()...")
root.update()
print("Step 4: Getting screen size...")
sw = root.winfo_screenwidth()
sh = root.winfo_screenheight()
print(f"  Screen: {sw}x{sh}")

print("Step 5: Creating canvas Toplevel...")
cw = tk.Toplevel(root)
cw.overrideredirect(True)
cw.geometry(f"{sw}x{sh}+0+0")
cw.attributes("-topmost", True)
print("Step 6: update_idletasks on canvas window...")
cw.update_idletasks()
print("Step 7: Setting transparentcolor and bg...")
TCOLOR = "#000000"
cw.config(bg=TCOLOR)
cw.attributes("-transparentcolor", TCOLOR)
cw.attributes("-alpha", 1.0)
print("Step 8: cw.update()...")
cw.update()

print("Step 9: Setting WS_EX_LAYERED via ctypes...")
try:
    import ctypes
    hwnd = cw.winfo_id()
    print(f"  hwnd={hwnd}")
    GWL_EXSTYLE=-20; WS_EX_LAYERED=0x80000
    cur=ctypes.windll.user32.GetWindowLongW(hwnd,GWL_EXSTYLE)
    ctypes.windll.user32.SetWindowLongW(hwnd,GWL_EXSTYLE,cur|WS_EX_LAYERED)
    print("  WS_EX_LAYERED set OK")
except Exception as ex:
    print(f"  ERROR: {ex}")

print("Step 10: Creating canvas widget...")
cv = tk.Canvas(cw, bg=TCOLOR, highlightthickness=0)
cv.pack(fill="both", expand=True)
cw.update()
print("  Canvas created OK")

print("Step 11: Creating toolbar Toplevel...")
tb = tk.Toplevel(root)
tb.overrideredirect(True)
tb.attributes("-topmost", True)
tb.config(bg="#12122A")
W = min(sw-10, 900); H = 56
tb.geometry(f"{W}x{H}+{(sw-W)//2}+3")
tb.update()
print("  Toolbar created OK")

print("Step 12: Adding EXIT button...")
def on_quit():
    print("EXIT CALLED — stack trace:")
    traceback.print_stack()
    print("Exiting.")
    os._exit(0)

f = tk.Frame(tb, bg="#12122A")
f.pack(fill="both", expand=True, padx=3, pady=3)
tk.Button(f, text="✕ EXIT", command=on_quit, bg="#FF3B30", fg="white",
          relief="flat", font=("Helvetica",10,"bold"), width=7).pack(side="left", padx=2)
tk.Button(f, text="TEST DRAW", bg="#007AFF", fg="white",
          relief="flat", font=("Helvetica",10,"bold"),
          command=lambda: cv.create_oval(300,300,500,500,outline="#FF3B30",width=4)).pack(side="left",padx=4)
tk.Button(f, text="TEST TEXT", bg="#34C759", fg="white",
          relief="flat", font=("Helvetica",10,"bold"),
          command=lambda: cv.create_text(sw//2,sh//2,text="Hello! Transparency working!",
                                         fill="#FFCC00",font=("Helvetica",24,"bold"))).pack(side="left",padx=4)
print("  Buttons added OK")

print("Step 13: Binding keys...")
# Bind ONLY to toolbar to avoid spurious events on canvas/root
tb.bind("<F12>", lambda e: on_quit())
tb.bind("<Control-q>", lambda e: on_quit())
# DO NOT bind to cw or root — that was the likely bug
print("  Keys bound OK")

print("Step 14: Starting mainloop...")
print()
print("="*50)
print("If you see this, startup succeeded!")
print("You should see:")
print("  - Dark toolbar at top of screen")  
print("  - Rest of screen TRANSPARENT (see through)")
print("  - Click TEST DRAW → red circle appears")
print("  - Click TEST TEXT → yellow text appears")
print("="*50)

root.mainloop()
