import os
import re

LOG_DIR = "results/simulating_social_media_non_partisan/good"

agent10_pattern = re.compile(
    r"\[agent10\]\s+LR=(\d+)\s+LD=(\d+)\s+HR=(\d+)\s+HD=(\d+)"
)

files = [f for f in os.listdir(LOG_DIR) if f.endswith(".log")]

diffs = []

republicans = 0
democrats = 0
republicans_polarized = 0
democrats_polarized = 0
#high outgrup is republicans_polarized + democrats_polarized

for filename in files:
    path = os.path.join(LOG_DIR, filename)
    with open(path, "r") as f:
        content = f.read()

    matches = agent10_pattern.findall(content)

    first = tuple(map(int, matches[0]))
    second = tuple(map(int, matches[1]))

    LR1, LD1, HR1, HD1 = first
    LR2, LD2, HR2, HD2 = second

    # Store differences
    diffs.append({
        "file": filename,
        "LR": (LR2 - LR1),
        "LD": (LD2 - LD1),
        "HR": (HR2 - HR1),
        "HD": (HD2 - HD1)
    })

    # In-Group condition
    if LR2 >= 5:
        republicans += 1
    if LD2 >= 5:
        democrats += 1

    # Polarization condition
    if LR2 >= 5 and HD2 > 5:
        republicans_polarized += 1
    if LD2 >= 5 and HR2 > 5:
        democrats_polarized += 1


# ----- Reporting -----

total = len(files)
print(total)
print(republicans, democrats, republicans_polarized, democrats_polarized)

avg_LR = sum(d['LR'] for d in diffs) / total
avg_LD = sum(d['LD'] for d in diffs) / total
avg_HR = sum(d['HR'] for d in diffs) / total
avg_HD = sum(d['HD'] for d in diffs) / total
print("\nAverage differences across all files:")
print(f"ΔLR={avg_LR:.2f} ΔLD={avg_LD:.2f} ΔHR={avg_HR:.2f} ΔHD={avg_HD:.2f}")

print("\nStatistics:")
print(
    f"Percentage republicans: "
    f"{(republicans / total) * 100:.2f}%"
)

print(
    f"Percentage democrats: "
    f"{(democrats / total) * 100:.2f}%"
)

print(
    f"Percentage republicans polarized: "
    f"{(republicans_polarized / total) * 100:.2f}%"
)

print(
    f"Percentage democrats polarized: "
    f"{(democrats_polarized / total) * 100:.2f}%"
)
