#!/usr/bin/env python3
"""
Recrea la figura como DOS plots separados (sin letras A / B):
  - figura_gc_A.pdf : dos gaussianas con rayado, lineas discontinuas y flecha 2d
  - figura_gc_B.pdf : esquemas de picos y circulos para distintos valores de mu

Requisitos:  pip install numpy matplotlib
Uso:         python figura_gc.py
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon

# ---------------------------------------------------------------- estilo
plt.rcParams.update({
    "mathtext.fontset": "cm",       # estilo LaTeX sin necesitar LaTeX instalado
    "font.family": "DejaVu Sans",
    "hatch.linewidth": 0.7,
})

RED = "#e00000"
BLUE = "#1010ff"
GREEN = "#3d7d1c"
GRAY = "#6b6b6b"

# ================================================================ PLOT 1
figA, axA = plt.subplots(figsize=(6.2, 3.6))

d = 0.55          # posicion de los centros (+-d)
sigma = 0.09
amp = 0.57
x = np.linspace(-1.1, 1.1, 1500)


def gauss(x, mu, s, a):
    return a * np.exp(-0.5 * ((x - mu) / s) ** 2)


yL = gauss(x, -d, sigma, amp)
yR = gauss(x, +d, sigma, amp)

# rayado + contorno
axA.fill_between(x, yL, facecolor="none", edgecolor=RED, hatch="\\\\\\\\", linewidth=0)
axA.fill_between(x, yR, facecolor="none", edgecolor=BLUE, hatch="\\\\\\\\", linewidth=0)
axA.plot(x, yL, color=RED, lw=2)
axA.plot(x, yR, color=BLUE, lw=2)

# lineas verticales discontinuas
for xc in (-d, d):
    axA.axvline(xc, color="k", ls=(0, (4, 3)), lw=1.3)

# flecha doble (linea discontinua + puntas solidas)
ya = 0.65
axA.plot([-d + 0.06, d - 0.06], [ya, ya], color=GREEN, ls=(0, (3, 2)), lw=1.8)
for xt, xh in ((-d, -d + 0.12), (d, d - 0.12)):
    axA.annotate("", xy=(xt, ya), xytext=(xh, ya),
                 arrowprops=dict(arrowstyle="-|>", color=GREEN, lw=1,
                                 mutation_scale=30, shrinkA=0, shrinkB=0))
axA.text(0, ya + 0.025, r"$2d$", color=GREEN, ha="center", va="bottom", fontsize=14)

# etiquetas gc-, gc+
axA.text(-d - 0.02, 0.80, r"$gc^{-}$", color=RED, ha="right", va="center", fontsize=14)
axA.text(d - 0.02, 0.80, r"$gc^{+}$", color=BLUE, ha="right", va="center", fontsize=14)

# etiquetas A-, A+ con fondo blanco
bb = dict(boxstyle="square,pad=0.15", fc="white", ec="none")
axA.text(-d + 0.03, 0.07, r"$A^{-}$", color=RED, ha="center", va="center",
         fontsize=13, bbox=bb)
axA.text(d + 0.03, 0.07, r"$A^{+}$", color=BLUE, ha="center", va="center",
         fontsize=13, bbox=bb)

# ejes
axA.set_xlim(-1.1, 1.1)
axA.set_ylim(0, 1)
axA.set_xticks([-1, 0, 1])
axA.set_xticklabels(["-1", "0", "1"], fontsize=13)
axA.set_yticks(np.linspace(0, 1, 8)[1:-1])
axA.set_yticklabels([])
axA.tick_params(top=True, right=True, direction="in", length=5)
axA.set_xlabel(r"$X$", fontsize=14, labelpad=2)
axA.set_ylabel(r"$p(X)$", fontsize=14, labelpad=8)

figA.tight_layout()

# ================================================================ PLOT 2
# Eje en coordenadas de "pixel" (origen arriba-izquierda); region x:[80,450], y:[245,405]
X0, X1, Y0, Y1 = 80, 450, 245, 405
figB = plt.figure(figsize=((X1 - X0) / 66, (Y1 - Y0) / 66))
ov = figB.add_axes([0, 0, 1, 1])
ov.set_xlim(X0, X1)
ov.set_ylim(Y1, Y0)
ov.axis("off")


def peaks(x0, x1, base, specs, n=400):
    """Linea base + una o varias gaussianas rellenas de gris.
    specs = [(centro, sigma, altura), ...]  (altura en pixeles)"""
    xs = np.linspace(x0, x1, n)
    ys = np.zeros_like(xs)
    for c, s, h in specs:
        ys += h * np.exp(-0.5 * ((xs - c) / s) ** 2)
    pts = np.column_stack([xs, base - ys])
    ov.add_patch(Polygon(pts, closed=True, fc=GRAY, ec="none", zorder=2))
    ov.plot(xs, base - ys, color="k", lw=1.0, zorder=3)
    ov.plot([x0, x1], [base, base], color="k", lw=1.0, zorder=3)


def disc(cx, cy, r):
    ov.add_patch(Circle((cx, cy), r, fc=GRAY, ec="k", lw=1.0, zorder=2))


base, cy, r = 318, 352, 21

# mu = 0
peaks(92, 132, base, [(112, 1.0, 42)])
disc(112, cy, r)
ov.text(112, 388, r"$\mu=0$", ha="center", va="center", fontsize=13)

# |mu| << 1
peaks(172, 220, base, [(195, 5.5, 36)])
disc(195, cy, r)
ov.text(195, 388, r"$|\mu|\ll 1$", ha="center", va="center", fontsize=13)

# 0 < mu < 1
peaks(245, 312, base, [(263, 2.5, 14), (293, 6.0, 32)])
disc(262, 350, 10)
disc(295, cy, r)
ov.text(278, 388, r"$0<\mu<1$", ha="center", va="center", fontsize=13)

# mu = 1 (circulos tangentes)
peaks(347, 432, base, [(369, 1.0, 42), (409, 1.0, 42)])
disc(369, cy, 20)
disc(409, cy, 20)
ov.text(389, 388, r"$\mu=1$", ha="center", va="center", fontsize=13)
ov.text(389, 262, r"$d=1$", ha="center", va="center", fontsize=13)

# ================================================================ guardar
figA.savefig("figura_gc_A.pdf", bbox_inches="tight")
figB.savefig("figura_gc_B.pdf", bbox_inches="tight")
print("Guardado: figura_gc_A.pdf y figura_gc_B.pdf")
plt.show()