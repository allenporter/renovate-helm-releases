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

INCLUDE_FILES = [".yaml", ".yml"]
DEFAULT_NAMESPACE = 'default'
HELM_REPOSITORY_APIVERSIONS = ["source.toolkit.fluxcd.io/v1beta1"]
HELM_RELEASE_APIVERSIONS = ["helm.toolkit.fluxcd.io/v2beta1"]

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

    annotations = {}

    files = [p for p in cluster_path.rglob('*') if p.suffix in INCLUDE_FILES]
    for file in files:
        for doc in ruamel.yaml.round_trip_load_all(file.read_bytes()):
            if doc:
                if 'apiVersion' in doc and doc['apiVersion'] in HELM_REPOSITORY_APIVERSIONS \
                        and 'kind' in doc and doc['kind'] == "HelmRepository":
                    helm_repo_name = doc['metadata']['name']
                    helm_repo_url = doc['spec']['url']
                    
                    LOG.info(f"Found Helm Repository \"{helm_repo_name}\" with chart url \"{helm_repo_url}\"")
                    
                    if helm_repo_name in annotations:
                        annotations[helm_repo_name]['chart_url'] = helm_repo_url
                    else:
                        annotations[helm_repo_name] = { 
                            'chart_url': helm_repo_url,
                            'files': []
                        }
                else:
                    LOG.debug(f"Skipping {file}, not a Helm Repository")

                if 'apiVersion' in doc and doc['apiVersion'] in HELM_RELEASE_APIVERSIONS \
                        and 'kind' in doc and doc['kind'] == "HelmRelease" \
                        and doc['spec']['chart']['spec']['sourceRef']['kind'] == "HelmRepository":
                    helm_release_name = doc['metadata']['name']
                    if 'namespace' in doc['metadata']:
                        helm_release_namespace = doc['metadata']['namespace']
                    else:
                        helm_release_namespace = DEFAULT_NAMESPACE
                    
                    helm_release_repository = doc['spec']['chart']['spec']['sourceRef']['name']

                    LOG.info(f"Found Helm Release '{helm_release_name}' in namespace '{helm_release_namespace}'")
                    
                    if not helm_release_repository in annotations:
                        annotations[helm_release_repository] = { 
                            'chart_url': None,
                            'files': []
                        }                   
                    annotations[helm_release_repository]['files'].append(file)
                else:
                    LOG.debug(f"Skipping {file}, not a Helm Release")

    for chart_name, value in annotations.items():
        if 'files' in value and 'chart_url' in value:
            if value['chart_url']:
                for file in value['files']:
                    LOG.info(f"Updating {chart_name} annotations in {file} with {value['chart_url']}")
            else:
                LOG.warning(f"Skipping {chart_name} because no matching Helm Repository was found.")
        else:
            LOG.warning(f"Skipping {chart_name} no Helm Release found using {value['chart_url']}")
            continue

if __name__ == "__main__":
    cli()
