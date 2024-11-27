import argparse
import logging
from tqdm import tqdm

from mapknowledge import KnowledgeStore
from routing import Rerouting, SCICRUNCH_API_KEY

logger = logging.getLogger()
# logger.setLevel(logging.INFO)
logging.basicConfig(
    format='%(asctime)s [%(levelname)-9s] %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

def _parse_args():
    parser = argparse.ArgumentParser(prog="nerve-testing")
    # direct file argument for now, could use release or sha instead in the future?
    parser.add_argument("sckan_version", help="The version of SKAN, e.g. sckan-2024-09-21")

    # Later this must refer to a standard repo and SHA
    parser.add_argument("points", help="The nerve point annotation file location")
    parser.add_argument("pathways", help="The full nerve pathway csv")

    return parser.parse_args()

def _coverage_testing(args):
    store = KnowledgeStore(store_directory='production', sckan_version=args.sckan_version, clean_connectivity=True)
    try:
        rerouting = Rerouting(args.pathways, args.points, store)
        
        # get paths, edges and nodes
        all_edges = []
        all_nodes = []
        human_paths = {}
        human_edges = []
        human_nodes = []
        for path in store.connectivity_paths():
            path_kn = store.entity_knowledge(path)
            all_edges += [(edge[0], edge[1]) for edge in path_kn['connectivity'] if (edge[0], edge[1]) not in all_edges and (edge[1], edge[0]) not in all_edges]
            all_nodes += [n for edge in path_kn['connectivity'] for n in edge if n not in all_nodes]

            # filter for human neuron population only (NCBITaxon:9606/human) (NCBITaxon:40674/mammal)
            if len(taxons:=path_kn.get('taxons', [])) == 0 \
                or 'NCBITaxon:9606' in taxons \
                or 'NCBITaxon:40674' in taxons:
                human_paths[path] = path_kn
                human_edges += [(edge[0], edge[1]) for edge in path_kn['connectivity'] if (edge[0], edge[1]) not in human_edges and (edge[1], edge[0]) not in human_edges]
                human_nodes += [n for edge in path_kn['connectivity'] for n in edge if n not in human_nodes]

        # rerouting to 3d whole body map test
        covered_paths = set()
        covered_nodes = set()
        covered_edges = set()
        for path in human_paths:
            reroute_knowledge = rerouting.reroute_for_3d_map(path)
            covered_nodes.update(reroute_knowledge['covered_nodes'])
            covered_edges.update([c_e for c_e in reroute_knowledge['covered_edges'] if c_e not in covered_edges and (c_e[1], c_e[0]) not in covered_edges])
            if len(reroute_knowledge['connectivity']) >= 4:
                covered_paths.add(path)

        # log testing results
        logger.info(f'Nerve point annotation file: {args.points}')
        logger.info(f'Full nerve pathway file: {args.pathways}')
        logger.info(f'Number of paths in SCKAN: {len(store.connectivity_paths())}')
        logger.info(f'Number of edges in SCKAN: {len(all_edges)}')
        logger.info(f'Number of nodes in SCKAN: {len(all_nodes)}')
        logger.info(f'Number of human paths in SCKAN: {len(human_paths)}')
        logger.info(f'Number of human edges in SCKAN: {len(human_edges)}')
        logger.info(f'Number of human nodes in SCKAN: {len(human_nodes)}')
        logger.info(f'Number of paths in 3D whole body map: {len(covered_paths)}')
        logger.info(f'Number of edges in 3D whole body map: {len(covered_edges)}')
        logger.info(f'Number of nodes in 3D whole body map: {len(covered_nodes)}')

    except Exception as e:
        logger.error(e)

    store.close()

if __name__ == "__main__":
    args = _parse_args()
    _coverage_testing(args)
