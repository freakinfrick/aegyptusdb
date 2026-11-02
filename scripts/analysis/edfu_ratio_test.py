"""Edfu building inscription: recorded dimensions (cubits) vs the golden ratio.

Dimensions are facts transcribed from the sources named per row; extend DIMS as
more rooms are located (full list: Dümichen, Tempelinschriften I, pls. 92ff).
"""
from fractions import Fraction as F

PHI = (1 + 5 ** 0.5) / 2
DIMS = [  # (element, a, b, source)
    ("Mesen sanctuary, L/W (Brugsch 1870 reading)", F(25, 3), F(20, 3), "Brugsch, ZÄS 8 (1870) 159"),
    ("Mesen sanctuary, L/W (modern reading)", F(25, 3), F(17, 3), "Kurth tr., quoted interpreterfoundation.org 'Edfu and Exodus'"),
    ("Great Seat (bark shrine), L/W", F(119, 6), F(31, 3), "Kurth tr., same"),
    ("Courtyard gate, W/D", F(80, 3), F(10), "Kurth-based tr., binks.substack.com"),
    ("Courtyard gate, H/W", F(40), F(80, 3), "same"),
    ("Pylon, H/thickness", F(120), F(60), "pylon base inscription tr., same article"),
]
SIMPLE = [F(p, q) for q in range(1, 9) for p in range(q, 3 * q + 1)]

print(f"{'element':48} {'ratio':>7} {'|r-phi|':>8}  nearest simple")
hits = 0
for name, a, b, _ in DIMS:
    r = a / b
    near = min(SIMPLE, key=lambda s: abs(float(s) - float(r)))
    d = abs(float(r) - PHI)
    hits += d < 0.02
    print(f"{name:48} {float(r):7.3f} {d:8.3f}  {near.numerator}:{near.denominator}"
          f" ({float(near):.3f}, off {abs(float(near) - float(r)):.3f})")
print(f"\nwithin 0.02 of phi: {hits}/{len(DIMS)}   (phi = {PHI:.4f})")
