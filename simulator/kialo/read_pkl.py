import pickle
import csv
import os

file_path = 'datasets/15876.pkl'
agent_name = 'kialo_replicator'  

class CompatUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if name in ('_CachedPropertyResetterNode', '_CachedPropertyResetterAdj'):
            class Stub:
                def __set_name__(self, owner, name): pass
                def __set__(self, obj, value): pass
                def __get__(self, obj, objtype=None): return {}
            return Stub
        return super().find_class(module, name)

def compute_abs(node_id):
    if node_id in relation_abs_map:
        return relation_abs_map[node_id]

    parent = parent_map.get(node_id)

    # Root node
    if parent is None:
        relation_abs_map[node_id] = 1
        return 1

    # Local relation
    rel = raw_nodes[node_id].get('relation')
    try:
        rel = int(rel)
        if rel not in (-1, 1):
            rel = 1
    except:
        rel = 1

    abs_parent = compute_abs(parent)
    relation_abs_map[node_id] = rel * abs_parent
    return relation_abs_map[node_id]

# Load data
with open(file_path, 'rb') as f:
    data = CompatUnpickler(f).load()

raw_nodes = data.__dict__.get('node', {})
raw_succ  = data.__dict__.get('succ', {})  # succ[node] = {parent_id: {weight:...}}

# Sort nodes by creation time
sorted_nodes = sorted(raw_nodes.items(), key=lambda x: x[1].get('created', ''))
# Drop the first node (title)
sorted_nodes = sorted_nodes[1:]

# Build node -> index map
node_to_index = {node_id: i for i, (node_id, _) in enumerate(sorted_nodes, start=1)}

# Compute absolute stance
parent_map = {}
for node_id, neighbors in raw_succ.items():
    if neighbors:
        parent_map[node_id] = next(iter(neighbors))
    else:
        parent_map[node_id] = None  # root

relation_abs_map = {}

for node_id in raw_nodes:
    compute_abs(node_id)

# Build author -> kialo_replicator_N map
author_map = {}
author_counter = 1
for _, attrs in sorted_nodes:
    author = attrs.get('author', '')
    if author and author not in author_map:
        author_map[author] = f'{agent_name}_{author_counter}'
        author_counter += 1

# Build CSV rows
rows = {}
for node_id, attrs in sorted_nodes:
    idx      = node_to_index[node_id]
    col_name = f'debate:{idx}'

    author   = author_map.get(attrs.get('author', ''), '')
    text = attrs.get('text', '') \
                .replace('\\', '') \
                .replace(',', ' ') \
                .replace('\n', ' ') \
                .strip()
    votes    = attrs.get('votes', '')
    relation = attrs.get('relation', '')
    relation_abs = relation_abs_map.get(node_id)

    # succ[node_id] -> parent node
    neighbors = raw_succ.get(node_id, {})
    if neighbors:
        parent_node_id = next(iter(neighbors))
        parent_index   = node_to_index.get(parent_node_id, '')
    else:
        parent_index = ''  # root node

    rows[col_name] = f'{idx},{author},{text},{parent_index},"{votes}",{relation},{relation_abs}'

# Determine output path
output_path = os.path.join(
    os.path.dirname(file_path),
    f"debate_{os.path.splitext(os.path.basename(file_path))[0]}.csv"
)

# 7. Write CSV
with open(output_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=list(rows.keys()))
    writer.writeheader()
    writer.writerow(rows)

print(f"Done. {len(rows)} nodes written to {os.path.basename(output_path)}")
print(f"Authors mapped: {len(author_map)} unique -> {agent_name}_0 .. {agent_name}_{author_counter-1}")
print("\nFirst 3 columns preview:")
for col, val in list(rows.items())[:3]:
    print(f"  {col}: {val[:100]}")
