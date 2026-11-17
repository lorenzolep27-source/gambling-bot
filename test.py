import os
import numpy as np

file_path = os.path.join("data", "hands.csv")
data = np.genfromtxt(file_path, delimiter=",", skip_header=1, dtype=str)

outcome = data[:, -1]
print(f"Max Occurances: {len(outcome)}\n# Wins: {len(outcome[outcome=="win"])}\n# Loss: {len(outcome[outcome=="loss"]) + len(outcome[outcome=="bust"])}\n# Push: {len(outcome[outcome=="push"])}")
