import pandas as pd
from collections import defaultdict
import networkx as nx
import matplotlib.pyplot as plt

# Load dataset
file_path = "datasets/acl23_unrevised.csv"  
df = pd.read_csv(file_path)

# Basic inspection
print("Dataset shape:", df.shape)
print("Columns:", df.columns.tolist())

# Check missing parent_claims
missing_parents = df['parent_claim'].isna().sum()
print(f"Missing parent_claim entries: {missing_parents}")

# Build mapping from claim_text to claim_id (may have duplicates)
claim_text_to_ids = defaultdict(list)
for _, row in df.iterrows():
    claim_text_to_ids[row['claim_text']].append(row['claim_id'])

# Build graph
G = nx.DiGraph()

# Add nodes
for _, row in df.iterrows():
    G.add_node(row['claim_id'], text=row['claim_text'])

# Add edges based on parent_claim text matching
missing_links = 0
multiple_matches = 0

for _, row in df.iterrows():
    parent_text = row['parent_claim']
    child_id = row['claim_id']

    if pd.isna(parent_text):
        continue

    matches = claim_text_to_ids.get(parent_text, [])

    if len(matches) == 1:
        G.add_edge(matches[0], child_id)
    elif len(matches) > 1:
        multiple_matches += 1
        # connect to all possible parents (ambiguous)
        for m in matches:
            G.add_edge(m, child_id)
    else:
        missing_links += 1

print(f"Missing parent links: {missing_links}")
print(f"Ambiguous parent matches: {multiple_matches}")

# Analyze connected components (trees/forests)
components = list(nx.weakly_connected_components(G))
print(f"Number of debate trees (components): {len(components)}")

# Size distribution
sizes = [len(c) for c in components]
print("Component size stats:")
print(f"  Min: {min(sizes)}")
print(f"  Max: {max(sizes)}")
print(f"  Mean: {sum(sizes)/len(sizes):.2f}")

# Find roots (nodes with no incoming edges)
roots = [n for n, d in G.in_degree() if d == 0]
print(f"Number of root nodes: {len(roots)}")

# Sample a few trees
print("\nSample trees (first 5):")
for i, comp in enumerate(components[:5]):
    subgraph = G.subgraph(comp)
    roots_sub = [n for n, d in subgraph.in_degree() if d == 0]
    print(f"Tree {i+1}: size={len(comp)}, roots={roots_sub[:3]}")

# Visualize a small tree
# Pick the smallest non-trivial component
small_comps = [c for c in components if 2 < len(c) < 20]

if small_comps:
    comp = small_comps[0]
    subgraph = G.subgraph(comp)

    pos = nx.spring_layout(subgraph)
    labels = {n: str(n) for n in subgraph.nodes()}

    plt.figure(figsize=(8, 6))
    nx.draw(subgraph, pos, with_labels=True, labels=labels, node_size=500, font_size=8)
    plt.title("Example Debate Tree")
    plt.show()
else:
    print("No small components to visualize.")

# Detect potential missing intermediate nodes
# Heuristic: parent text not found in dataset
print("\nInvestigating missing parent claims...")
missing_parent_texts = []

for _, row in df.iterrows():
    parent_text = row['parent_claim']
    if pd.isna(parent_text):
        continue
    if parent_text not in claim_text_to_ids:
        missing_parent_texts.append(parent_text)

print(f"Unique missing parent texts: {len(set(missing_parent_texts))}")

# Save missing parent examples
pd.Series(list(set(missing_parent_texts))).to_csv("missing_parents.csv", index=False)
print("Saved missing parent texts to missing_parents.csv")

# Optional: export graph
nx.write_gexf(G, "debate_graph.gexf")
print("Graph saved as debate_graph.gexf (can be opened in Gephi)")

# Summary
print("\nSummary:")
print("- Graph constructed using text matching")
print("- Missing links likely indicate missing intermediate claims")
print("- Ambiguities arise when multiple claims share identical text")
