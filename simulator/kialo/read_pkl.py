import pickle
import csv
import os

file_path = 'datasets/2222.pkl'
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

# 1. Load data
with open(file_path, 'rb') as f:
    data = CompatUnpickler(f).load()

raw_nodes = data.__dict__.get('node', {})
raw_succ  = data.__dict__.get('succ', {})  # succ[node] = {parent_id: {weight:...}}

# 2. Sort nodes by creation time
sorted_nodes = sorted(raw_nodes.items(), key=lambda x: x[1].get('created', ''))

# 3. Build node -> index map
node_to_index = {node_id: i for i, (node_id, _) in enumerate(sorted_nodes, start=1)}

# 4. Build author -> kialo_replicator_N map
author_map = {}
author_counter = 1
for _, attrs in sorted_nodes:
    author = attrs.get('author', '')
    if author and author not in author_map:
        author_map[author] = f'{agent_name}_{author_counter}'
        author_counter += 1

# 5. Build CSV rows
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

    # succ[node_id] -> parent node
    neighbors = raw_succ.get(node_id, {})
    if neighbors:
        parent_node_id = next(iter(neighbors))
        parent_index   = node_to_index.get(parent_node_id, '')
    else:
        parent_index = ''  # root node

    rows[col_name] = f'{idx},{author},{text},{parent_index},"{votes}",{relation}'

# 6. Determine output path with debate_ prefix and .csv extension
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
    print(f"  {col}: {val[:80]}")