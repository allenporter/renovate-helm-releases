from pathlib import Path

import logging

import click
import ruamel.yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

LOG = logging.getLogger("Renovate Helm Releases")

class ClusterPath(click.ParamType):
    name = 'cluster-path'
    def convert(self, value, param, ctx):
        clusterPath = Path(value)
        if not isinstance(value, tuple):
            if not clusterPath.exists:
                self.fail('invalid --cluster-path (%s) ' % value, param, ctx)
        return clusterPath

@click.command()
@click.option(
    '--cluster-path', '-d', envvar='CLUSTER_PATH', 
    type=ClusterPath(), 
    required=True,
    help='Path to cluster root, e.g. "./cluster"'
)
@click.option(
    '--dry-run', '-d', envvar='DRY_RUN', 
    is_flag=True,
    default=False,
    required=False,
    help='Do not annotate Helm Releases, only log changes'
)
@click.pass_context
def cli(ctx, cluster_path, dry_run):
    # ctx.obj = {
    #     'cluster_path': cluster_path,
    #     'dry_run': dry_run
    # }

    include_files = [".yaml", ".yml"]
    helm_repository_apiversions = ["source.toolkit.fluxcd.io/v1beta1"]
    helm_release_apiversions = ["helm.toolkit.fluxcd.io/v2beta1"]

    annotations = {}

    files = [p for p in cluster_path.rglob('*') if p.suffix in include_files]
    for file in files:
        for doc in ruamel.yaml.round_trip_load_all(file.read_bytes()):
            if doc:
                if 'apiVersion' in doc and doc['apiVersion'] in helm_repository_apiversions \
                        and 'kind' in doc and doc['kind'] == "HelmRepository":
                    LOG.info(f"Found Helm Repository \"{doc['metadata']['name']}\" with chart url \"{doc['spec']['url']}\"")
                    
                    if doc['metadata']['name'] in annotations:
                        annotations[doc['metadata']['name']]['chart_url'] = doc['spec']['url']
                    else:
                        annotations[doc['metadata']['name']] = { 
                            'chart_url': doc['spec']['url'],
                            'files': []
                        }
                else:
                    LOG.debug(f"Skipping {file}, not a Helm Repository")

                if 'apiVersion' in doc and doc['apiVersion'] in helm_release_apiversions \
                        and 'kind' in doc and doc['kind'] == "HelmRelease" \
                        and doc['spec']['chart']['spec']['sourceRef']['kind'] == "HelmRepository":
                    LOG.info(f"Found Helm Release '{doc['metadata']['name']}' in namespace '{doc['metadata']['namespace']}'")
                    
                    if not doc['spec']['chart']['spec']['sourceRef']['name'] in annotations:
                        annotations[doc['spec']['chart']['spec']['sourceRef']['name']] = { 
                            'chart_url': None,
                            'files': []
                        }                   
                    annotations[doc['spec']['chart']['spec']['sourceRef']['name']]['files'].append(file)
                else:
                    LOG.debug(f"Skipping {file}, not a Helm Release")

    for chart_name, value in annotations.items():
        if 'files' in value and 'chart_url' in value:
            for file in value['files']:
                LOG.info(f"Updating {chart_name} annotations in {file} with {value['chart_url']}")
        else:
            LOG.warning(f"Skipping {chart_name} no Helm Release found using {value['chart_url']}")
            continue

if __name__ == "__main__":
    cli()
