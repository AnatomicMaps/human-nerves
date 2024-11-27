#===============================================================================
#
# This code is adopted from:
#  - Code: https://github.com/AnatomicMaps/map-tools/blob/main/connectivity-graph/connectivity_graph.py
#  - SHA: 384ef274a77b3995ae4c16d7ad726bd97b57a7fa
# updates are made to suit this repo's needs
#
#===============================================================================

import ipycytoscape
import networkx as nx
import os

#===============================================================================

from mapknowledge import KnowledgeStore

#===============================================================================

LABEL_WIDTH = 16
SCICRUNCH_API_KEY = os.environ.get('SCICRUNCH_API_KEY', '-')

def wrap_text(text, max_width=LABEL_WIDTH):
    words = text.strip().split()
    s = 0
    while True:
        l = 0
        e = s
        while e < len(words) and l < max_width:
            l += len(words[e])
            e += 1
        if l < max_width:
            yield ' '.join(words[s:e])
            return
        else:
            if e > (s + 1):
                e -= 1
            yield ' '.join(words[s:e])
            s = e

NPO = 'npo'

#===============================================================================

class ConnectivityKnowledge(KnowledgeStore):
    def __init__(self, store_directory=None, clean_connectivity=False, 
                 sckan_version=None, use_npo=True, sckan_provenance=True):
        super().__init__(store_directory=store_directory,
                         clean_connectivity=clean_connectivity,
                         sckan_version=sckan_version,
                         sckan_provenance=sckan_provenance,
                         scicrunch_key=SCICRUNCH_API_KEY)

    def formatted_label(self, term):
        if term is not None:
            label = self.entity_knowledge(term).get('label', term)
            return '\n'.join(wrap_text(f'{term}: {label}' if label is not None else term))
        return ''

    @staticmethod
    def matched_term(node, layer_region_terms):
        layer, regions = node
        for region in regions:
            if (layer, region) in layer_region_terms:
                return True
        return False

    def node_id(self, node):
        names = [self.formatted_label(node[0])]
        for term in node[1]:
            names.append(self.formatted_label(term))
        return '\n'.join(names)

    def connectivity(self, neuron_population_id):
        knowledge = self.entity_knowledge(neuron_population_id)
        return self.connectivity_from_knowledge(knowledge)

    def connectivity_from_knowledge(self, knowledge):
        axon_nodes = knowledge.get('axons', [])
        dendrite_nodes = knowledge.get('dendrites', [])
        def set_node_attributes(G, node):
            G.nodes[node]['label'] = self.node_id(node)
            G.nodes[node]['axon'] = node in axon_nodes
            G.nodes[node]['dendrite'] = node in dendrite_nodes
        G = nx.Graph()
        for n, pair in enumerate(knowledge.get('connectivity', [])):
            node_0 = (pair[0][0], tuple(pair[0][1]))
            node_1 = (pair[1][0], tuple(pair[1][1]))
            G.add_edge(node_0, node_1, directed=True, id=n)
            set_node_attributes(G, node_0)
            set_node_attributes(G, node_1)
        return G

#===============================================================================

STYLING = [
    {
        'selector': 'node',
        'style': {
            'label': 'data(label)',
            'background-color': '#80F0F0',
            'text-valign': 'center',
            'text-wrap': 'wrap',
            'text-max-width': '80px',
            'font-size': '10px'
        }
    },
    {'selector': 'node[axon]',
     'style': {'background-color': 'green',},},
    {'selector': 'node[dendrite]',
     'style': {'background-color': 'red',},},
    {'selector': 'node[both-a-d]',
     'style': {'background-color': 'gray',},},
    {
        'selector': 'edge',
        'style': {
            'width': 2,
            'line-color': '#9dbaea',
        }
    }
]

#===============================================================================

def display_connectivity_for_entity(store, entity):
    display_connectivity_graph(
        graph := store.connectivity_from_knowledge(
            knowledge:=store.entity_knowledge(entity)))
    return (knowledge, graph)

def display_connectivity_graph(graph):
    connected_nodes = list(nx.connected_components(graph))
    for nodes in connected_nodes:
        G = graph.subgraph(nodes)
        G.nodes[list(G.nodes.keys())[1]]
        g = ipycytoscape.CytoscapeWidget()
        g.layout.height = '400px'
        g.graph.add_graph_from_networkx(G, directed=True)
        g.set_style(STYLING)
        [n.data.pop('dendrite') for n in g.graph.nodes if not n.data['dendrite']]
        [n.data.pop('axon') for n in g.graph.nodes if not n.data['axon']]
        for n in g.graph.nodes:
            if ('axon' in n.data and 'dendrite' in n.data and
                n.data['axon'] and n.data['dendrite']):
                n.data['both-a-d'] = True
                n.data.pop('axon')
                n.data.pop('dendrite')
        display(g)

#===============================================================================
