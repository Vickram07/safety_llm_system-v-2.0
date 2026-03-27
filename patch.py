with open("server.py", "r") as f:
    text = f.read()

text = text.replace(
    '"Zone Zeta (Lobby)":        ["Exit Zeta South", "West Corridor"],',
    '"Zone Zeta (Lobby)":        ["Exit Zeta South", "West Corridor", "Zone Eta (R&D)"],'
)
text = text.replace(
    '"Zone Eta (R&D)":           ["Exit Eta South", "West Corridor", "Zone Zeta (Lobby)"],',
    '"Zone Eta (R&D)":           ["Exit Eta South", "West Corridor", "Zone Zeta (Lobby)", "Zone Theta (Cafeteria)"],'
)
text = text.replace(
    '"Zone Iota (Medical)":      ["Exit Iota South", "East Corridor", "Zone Theta (Cafeteria)"],',
    '"Zone Iota (Medical)":      ["Exit Iota South", "East Corridor", "Zone Theta (Cafeteria)", "Zone Kappa (Security)"],'
)

with open("server.py", "w") as f:
    f.write(text)
print("Patched ADJACENCY graph")
