import fnmatch
import logging
import os
import re
import sys

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
        if not isinstance(value, tuple):
            if not os.path.exists(value):
                self.fail('invalid --cluster-path (%s) ' % value, param, ctx)
        return os.path.abspath(value)

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

    include_files = ["*.yaml", "*.yml"]
    include_files = r'|'.join([fnmatch.translate(x) for x in include_files])

    annotations = dict()

    for root, _, files in os.walk(cluster_path):
        files = [os.path.join(root, f) for f in files]
        files = [f for f in files if re.match(include_files, f)]
        for file in files:
            with open(file) as f_yaml:
                for doc in ruamel.yaml.round_trip_load_all(f_yaml):
                    try:
                        if doc['apiVersion'] == "source.toolkit.fluxcd.io/v1beta1" and doc['kind'] == "HelmRepository":
                            LOG.info(f"Found Helm Repository '{doc['metadata']['name']}' with chart url '{doc['spec']['url']}'")
                            annotations[doc['metadata']['name']] = { 'chart_url': doc['spec']['url'] }
                            # annotations[doc['metadata']['name']] = doc['spec']['url']
                    except (TypeError):
                        LOG.warning(f"Skipping {file} not a Helm Repository")
                        continue

    for root, _, files in os.walk(cluster_path):
        files = [os.path.join(root, f) for f in files]
        files = [f for f in files if re.match(include_files, f)]
        for file in files:
            with open(file) as f_yaml:
                for doc in ruamel.yaml.round_trip_load_all(f_yaml):
                    try:
                        if doc['apiVersion'] == "helm.toolkit.fluxcd.io/v2beta1" and doc['kind'] == "HelmRelease":
                            LOG.info(f"Found Helm Release '{doc['spec']['chart']['spec']['chart']}'")
                            annotations[doc['spec']['chart']['spec']['sourceRef']['name']].update({ 'file': file })
                    except (TypeError):
                        LOG.warning(f"Skipping {file} not a Helm Release")
                        continue

    print(annotations)

    for item in annotations.values():
        print("File: %s Url: %s" % (item['file'], item['chart_url']))

if __name__ == "__main__":
    cli()
