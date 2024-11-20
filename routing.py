#===============================================================================

import pandas as pd
import networkx as nx
import itertools
from connectivity_graph import display_connectivity_graph, display_connectivity_for_entity

import logging as log
import requests
from json import JSONDecodeError
import os
import json

#===============================================================================

LOOKUP_TIMEOUT = 30
SCICRUNCH_API_KEY = os.environ.get('SCICRUNCH_API_KEY', '-')

def request_json(endpoint, **kwds):
    try:
        response = requests.get(endpoint,
                                headers={'Accept': 'application/json'},
                                timeout=LOOKUP_TIMEOUT,
                                **kwds)
        if response.status_code == requests.codes.ok:
            try:
                return response.json()
            except JSONDecodeError:
                error = 'Invalid JSON returned'
        else:
            error = response.reason
    except requests.exceptions.RequestException as exception:
        error = f'Exception: {exception}'
    log.warning(f"Couldn't access {endpoint}: {error}")
    return None

#===============================================================================

class NervePathways:
    """
    This class is to load knowledge from M2.6 files
    """
    def __init__(self, path):
        self.__nerve_df = pd.read_csv(path)

        self.__extract_kowledge()

    def __extract_kowledge(self):
        self.__nerves = {}
        
        # extract laterality
        ### filter by removing all lines with 'In man-in-box?' having NaN value
        # df_3d_nerves = self.__nerve_df[self.__nerve_df['In man-in-box?'].notna()]

        for _, row in self.__nerve_df.iterrows():
            # get id
            if pd.isna(preferred_id := row['Preferred ID for nerve name']):
                if pd.isna(row['Name']):
                    continue
                id = (row['Name'].replace('* ', '').splitlines()[0],)
            elif 'REQUESTED' in preferred_id or 'NEEDS CLARIFICATION' in preferred_id:
                if preferred_id in ['REQUESTED', 'NEEDS CLARIFICATION']:
                    id = (row['Name'].replace('* ', '').splitlines()[0],)
                else:
                    if len(k_names:= row['Name'].replace('* ', '').splitlines()) != len(k_ids:=preferred_id.replace('* ', '').splitlines()):
                        id = (k_names[0],)
                    else:
                        id = tuple(k_id if k_id not in ['REQUESTED', 'NEEDS CLARIFICATION'] else k_name for k_id, k_name in zip(k_ids, k_names))

            else:
                id = tuple(preferred_id.replace('* ', '').splitlines())

            ## temporarily get one id only
            id = (id[0], )

            if id not in self.__nerves:
                self.__nerves[id] = {
                    'id': id,
                    'name': row['Name'].replace('* ', '').splitlines()[0],
                    'in_3d_map': pd.notna(row['In man-in-box?'])
                }
                # check lateral and bilateral
                if pd.notna(row['Superclass']):
                    bilateral_id = tuple(row['Superclass'].splitlines())

                    ## temporarily get one id only
                    bilateral_id = (bilateral_id[0], )

                    self.__nerves[id]['bilaterals'] = bilateral_id
                    self.__nerves[bilateral_id]['laterals'] = self.__nerves[bilateral_id].get('laterals', []) + [id]
                # check origin 
                if pd.notna(row['Preferred ID for Origin/Central connection/Parent nerve']):
                    origins = str(row['Preferred ID for Origin/Central connection/Parent nerve']).replace('* ', '').splitlines()
                elif len(bilateral_id:=self.get_bilateral(id)) > 0:
                    origins = self.get_origins(bilateral_id)
                else:
                    origins = []
                self.__nerves[id]['origins'] = origins
                # check destination
                if pd.notna(row['Preferred ID (of destination)']):
                    destinations = str(row['Preferred ID (of destination)']).replace('* ', '').splitlines()
                elif len(bilateral_id:=self.get_bilateral(id)) > 0:
                    destinations = self.get_destinations(bilateral_id)
                else:
                    destinations = []
                self.__nerves[id]['destinations'] = destinations
                # check landmarks
                if pd.notna(row['Preferred ID for landmarks']):
                    landmarks = str(row['Preferred ID for landmarks']).replace('* ', '').splitlines()
                elif len(bilateral_id:=self.get_bilateral(id)) > 0:
                    landmarks = self.get_landmarks(bilateral_id)
                else:
                    landmarks = []
                self.__nerves[id]['landmarks'] = landmarks

    def get_laterals(self, id):
        id = id if isinstance(id, tuple) else (id,)
        laterals = {'right':[], 'left':[]}
        for lateral_id in self.__nerves.get(id, {}).get('laterals', []):
            if 'left' in self.__nerves.get(lateral_id, {}).get('name', '').lower():
                laterals['left'] += [lateral_id[0]]
            elif 'right' in self.__nerves.get(lateral_id, {}).get('name', '').lower():
                laterals['right'] += [lateral_id[0]]
            else:
                nested_laterals = self.get_laterals(lateral_id)
                laterals['left'] += nested_laterals['left']
                laterals['right'] += nested_laterals['right']

        return laterals
        
    def get_bilateral(self, id):
        id = id if isinstance(id, tuple) else (id,)
        return self.__nerves.get(id, {}).get('bilaterals', [])

    def get_lateral_right(self, id):
        id = id if isinstance(id, tuple) else (id,)
        return self.get_laterals(id).get('right')

    def get_lateral_left(self, id):
        id = id if isinstance(id, tuple) else (id,)
        return self.get_laterals(id).get('left')

    def get_origins(self, id):
        id = id if isinstance(id, tuple) else (id,)
        return self.__nerves.get(id, {}).get('origins', [])
    
    def get_destinations(self, id):
        id = id if isinstance(id, tuple) else (id,)
        return self.__nerves.get(id, {}).get('destinations', [])
    
    def get_landmarks(self, id):
        id = id if isinstance(id, tuple) else (id,)
        return self.__nerves.get(id, {}).get('landmarks', [])
    
    def is_nerve_available(self, id):
        id = id if isinstance(id, tuple) else (id,)
        return id in self.__nerves
    
    def __get_data_from_scicrunch(self, id):
        params = {
                'api_key': SCICRUNCH_API_KEY,
                'limit': 9999,
            }
        SCICRUNCH_API_ENDPOINT = 'https://scicrunch.org/api/1'
        query = f'{SCICRUNCH_API_ENDPOINT}/ilx/search/curie/{id}'
        data = request_json(query, params=params)

        result = {}
        if data is not None:    
            idxs = [concept['curie'] for concept in data.get('data', {}).get('existing_ids')]
            if idxs is None or len(idxs)==0:
                return {}
            result['idxs'] = idxs
            part_of = [r.get('term2_curie') for r in data['data'].get('relationships', {}) if r.get('relationship_term_ilx','') == 'ilx_0112785']
            if not any('UBERON' in po  for po in part_of):
                new_part_of = []
                for part in part_of:
                    query_part = f'{SCICRUNCH_API_ENDPOINT}/ilx/search/curie/{part}'
                    data_part = request_json(query_part, params=params)
                    new_part_of += [concept['curie'] for concept in data_part.get('data', {}).get('existing_ids')]
                part_of = list(set(new_part_of))

            result['partOf'] = part_of
    
        return result
    
    def get_broader_concepts(self, id):
        data = self.__get_data_from_scicrunch(id)
        return data.get('partOf', [])
    
    def get_label(self, id):
        id = id if isinstance(id, tuple) else (id,)
        return self.__nerves.get(id, {}).get('name', id[0])
    
    def get_nerve(self, id):
        id = id if isinstance(id, tuple) else (id,)
        return self.__nerves.get(id, {'id':id})
    
#===============================================================================

class Nerves:
    def __init__(self, path):
        with open(path, 'r') as f:
            nerve_data = json.load(f)


        # get nerves from man in box
        self.__nerves = {}
        self.__id_map = {}
        for nerve_point in nerve_data:
            nerve_id = (nerve_point.get('region', '').split('/')[-1].lower()) if (nerve_id:=nerve_point.get('model')) is None else nerve_id
            nerve_id = nerve_id.lower()
            if nerve_id not in self.__nerves:
                self.__nerves[nerve_id] = {
                    'id': nerve_id,
                    'label': nerve_point.get('region', '').split('/')[-1].lower(), 
                    'points': {}
                }
            if '(origin)' in (group:=nerve_point.get('group', '').lower()):
                self.__nerves[nerve_id]['points'][0] = {
                    'group': group
                }
            elif '(waypoint' in group:
                if '(waypoint)' in group:
                    point_id = 1
                else:
                    point_id = int(group.split('(waypoint ')[-1].split(')')[0])
                self.__nerves[nerve_id]['points'][point_id] = {
                    'group': group
                }
            elif '(destination)' in group:
                self.__nerves[nerve_id]['points']['destination'] = {
                    'group': group
                }
            
            # s
            self.__id_map[nerve_id] = nerve_id
            self.__id_map[self.__nerves[nerve_id]['label']] = nerve_id
            
        # update destination to the last integer
        for nerve_id, nerve in self.__nerves.items():
            if 'destination' in nerve['points']:
                nerve['points'][len(nerve['points'])-1] = nerve['points']['destination']
                del nerve['points']['destination']
    
    def get_nerve(self, node):
        nerve_id = self.__id_map.get(node.lower())
        return self.__nerves.get(nerve_id)

    def __get_point(self, nerve, edge_terms):
        if nerve is not None:
            point_weight = {}
            for point, point_data in nerve['points'].items():
                group_terms= set(point_data['group'].lower().split())
                point_weight[point] = len(edge_terms & group_terms)
            selected_point = max(point_weight, key=point_weight.get)
            return [{
                'id': nerve['id'],
                'label': nerve['label'],
                'point': (selected_point, nerve['points'][selected_point]['group'])
            }]
                    
        return []

    def get_points(self, u, v):
        edge_terms = set(u.get('name', '').lower().split() + v.get('name', '').lower().split())
        nerve_u = nerve_u if (nerve_u:=self.get_nerve(u['id'][0])) is not None else self.get_nerve(u.get('name', u['id'][0]))
        nerve_v = nerve_v if (nerve_v:=self.get_nerve(v['id'][0])) is not None else self.get_nerve(v.get('name', v['id'][0]))
        if nerve_u is None and nerve_v is None:
            points = []
        elif nerve_u is None or nerve_v is None:
            nerve = nerve_v if nerve_u is None else nerve_u
            non_nerve = u if nerve_u is None else v
            is_nerve =  v if nerve_u is None else u
            if non_nerve['id'][0] in is_nerve['origins']:
                point = (0, nerve['points'][0]['group'])
            elif non_nerve['id'][0] in is_nerve['destinations']:
                point = (max(nerve['points'].keys()), nerve['points'][max(nerve['points'].keys())]['group'])
            else:
                point = (-1, '')
            points = [{
                'id': nerve['id'],
                'label': nerve['label'],
                'point': point
            }]
        else:
            points = self.__get_point(nerve_u, edge_terms) + self.__get_point(nerve_v, edge_terms)

        return points
        
    @property
    def nerves(self):
        return self.__nerves

#===============================================================================

class Rerouting:
    def __init__(self, path_hierarchy, path_maninbox):
        self.__nerve_pathways = NervePathways(path_hierarchy)
        self.__nerve_maninbox = Nerves(path_maninbox)

    def check_laterality(self, G):
        lateral_map = {}
        for node in G.nodes():
            for n in [node[0]] + list(node[1]):
                if len((laterals:=self.__nerve_pathways.get_laterals(n))['left']) > 0:
                    lateral_map[node] = laterals
                    break
        return lateral_map

    def add_lateralised_edge(self, G_reconstructed, u, v, laterality_mapping):
        for laterality in ['left', 'right']:
            u_laterals = [(ul, ()) for ul in laterality_mapping[u][laterality]] if u in laterality_mapping else [u]
            v_laterals = [(vl, ()) for vl in laterality_mapping[v][laterality]] if v in laterality_mapping else [v]

            for ul, vl in itertools.product(u_laterals, v_laterals):
                G_reconstructed.add_edge(ul, vl)

    def replace_node(self, G, old_node, new_node):
        if old_node in G and new_node not in G:
            G.add_node(new_node, **G.nodes[old_node])
            for neighbor in G.neighbors(old_node):
                G.add_edge(new_node, neighbor)
            G.remove_node(old_node)

    def reroute_for_3d_map(self, store, entity):
        import copy
        entity_knowledge = copy.deepcopy(store.entity_knowledge(entity))
        
        G = nx.Graph()
        G.add_edges_from(entity_knowledge['connectivity'])
        G_reconstructed = nx.Graph()
        
        # create G_reconstructed and add laterality
        if len(lateral_map := self.check_laterality(G)) > 0:
            for u, v in G.edges():
                # Add to right path
                self.add_lateralised_edge(G_reconstructed, u, v, lateral_map)
        
        # update G_reconstructed based on origin
        retained_nodes = []
        availabel_origs_dests = []
        for lateral_nodes in lateral_map.values():
            for nodes in lateral_nodes.values():
                for n in nodes:
                    availabel_origs_dests += self.__nerve_pathways.get_origins(n)
                    availabel_origs_dests += self.__nerve_pathways.get_destinations(n)
                    retained_nodes += [(n, ())]
        
        # remove nodes not in origins, destinations and retained_nodes
        for node in list(G_reconstructed.nodes):
            if len(flat_node:=set([node[0]] + list(node[1]))-set(availabel_origs_dests)) == len(set([node[0]] + list(node[1]))) and node not in retained_nodes:
                # check in scicrunch
                super_container = set([spr for fn in flat_node for spr in self.__nerve_pathways.get_broader_concepts(fn)])
                if len(containers := list(super_container & set(availabel_origs_dests))) > 0:
                    self.replace_node(G_reconstructed, node, (containers[0], ()))
                else:
                    neighbors = list(G_reconstructed.neighbors(node))
                    for neighbor1, neighbor2 in itertools.combinations(neighbors, 2):
                        if neighbor1 in retained_nodes and neighbor2 in retained_nodes:
                            continue
                        G_reconstructed.add_edge(neighbor1, neighbor2)
                    G_reconstructed.remove_node(node)
            elif len(selected_layer:=set([node[0]] + list(node[1])) & set(availabel_origs_dests)) < len(set([node[0]] + list(node[1])) ) and len(selected_layer) > 0:
                self.replace_node(G_reconstructed, node, (list(selected_layer)[0], ()))
            

        entity_knowledge['connectivity'] = list(G_reconstructed.edges())    
        entity_knowledge['dendrites'] = [d for d in entity_knowledge['dendrites'] if d in list(G_reconstructed.nodes)]
        entity_knowledge['axons'] = [a for a in entity_knowledge['axons'] if a in list(G_reconstructed.nodes)]
        return entity_knowledge
    
    def get_3d_pathways_graph(self, store, entity):
        G =  store.connectivity_from_knowledge(knowledge=self.reroute_for_3d_map(store, entity))
        return G

    @property
    def nerve_pathways(self):
        return self.__nerve_pathways
    
    def get_3d_edges(self, G:nx.Graph):
        points = []
        
        #  get points in 3d map for the identified edges
        for e in G.edges:
            n_0 = self.__nerve_pathways.get_nerve(e[0][0])
            n_1 = self.__nerve_pathways.get_nerve(e[1][0])
            points += [self.__nerve_maninbox.get_points(n_0, n_1)]

        # points should be reconstruct to get full coverage
        # as an example the is edge of A0-B4 and A2-C1. 
        # There should be edge of A0-A1 and abd A1-A2 to make the connectivity complete
        new_points = []
        for pair in list(itertools.combinations([px for p in points for px in p], 2)):
            if pair[0]['id'] == pair[1]['id']:
                p0 = pair[0] if pair[0]['point'][0] < pair[1]['point'][0] else pair[1]
                p1 = pair[0] if pair[0]['point'][0] > pair[1]['point'][0] else pair[1]
                for group_num in range(p0['point'][0], p1['point'][0]):
                    new_points += [[
                        {
                            'id': p0['id'],
                            'label': p0['label'],
                            'point': (group_num, (nerve_points:=self.__nerve_maninbox.get_nerve(p0['id'])['points'])[group_num]['group'])
                        },
                        {
                            'id': p1['id'],
                            'label': p1['label'],
                            'point': (group_num+1, nerve_points[group_num+1]['group'])
                        }
                    ]]
        return [p for p in points + new_points if len(p)==2]

#===============================================================================

def draw_entity(store, rerouting, entity):
    print(entity)
    print('SCKAN:')
    display_connectivity_for_entity(store, entity)
    print('Reroute for 3D Map:')
    knowledge=rerouting.reroute_for_3d_map(store, entity)
    graph = store.connectivity_from_knowledge(knowledge)
    display_connectivity_graph(graph)
    return graph

def draw_waypoints(rerouting, g):
    edges_3d = rerouting.get_3d_edges(g)
    g_3d = nx.Graph([(edge[0]['point'][1], edge[1]['point'][1]) for edge in edges_3d])
    for n in g_3d.nodes:
        g_3d.nodes[n]['label'] = n
        g_3d.nodes[n]['dendrite'] = []
        g_3d.nodes[n]['axon'] = []
        g_3d.nodes[n]['both-a-d'] = []
    display_connectivity_graph(g_3d)
