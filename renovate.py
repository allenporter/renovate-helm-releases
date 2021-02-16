#!/usr/bin/env python3

import logging
from pathlib import Path

import click
import yaml

DEFAULT_NAMESPACE = "default"
INCLUDE_FILES = [".yaml", ".yml"]
HELM_REPOSITORY_APIVERSIONS = ["source.toolkit.fluxcd.io/v1beta1"]
HELM_RELEASE_APIVERSIONS = ["helm.toolkit.fluxcd.io/v2beta1"]
RENOVATE_STRING = "# renovate: registryUrl="

class ClusterPath(click.ParamType):
    name = "cluster-path"
    def convert(self, value, param, ctx):
        clusterPath = Path(value)
        if not isinstance(value, tuple):
            if not clusterPath.exists:
                self.fail(f"invalid --cluster-path '{value}'")
        return clusterPath

@click.command()
@click.option(
    "--cluster-path", envvar="CLUSTER_PATH", 
    type=ClusterPath(), 
    required=True,
    help="Path to cluster root, e.g. './cluster'"
)
@click.option(
    "--debug", envvar="DEBUG", 
    is_flag=True,
    default=False,
    required=False,
    help="Turn on debug logging"
)
@click.option(
    "--dry-run", envvar="DRY_RUN", 
    is_flag=True,
    default=False,
    required=False,
    help="Do not alter Helm Release files"
)
@click.pass_context
def cli(ctx, cluster_path, debug, dry_run):
    ctx.obj = {
        "cluster_path": cluster_path,
        "debug": debug,
        "dry_run": dry_run
    }

    # pylint: disable=no-value-for-parameter
    log = logger()

    annotations = {}

    files = [p for p in cluster_path.rglob('*') if p.suffix in INCLUDE_FILES]
    for file in files:
        for doc in yaml.safe_load_all(file.read_bytes()):
            if doc:
                if "apiVersion" in doc and doc["apiVersion"] in HELM_REPOSITORY_APIVERSIONS \
                        and "kind" in doc and doc["kind"] == "HelmRepository":
                    helm_repo_name = doc["metadata"]["name"]
                    helm_repo_url = doc["spec"]["url"]
                    
                    log.info(f"Discovered Helm Repository '{helm_repo_name}' with chart url '{helm_repo_url}'")
                    
                    if helm_repo_name in annotations:
                        annotations[helm_repo_name]["chart_url"] = helm_repo_url
                    else:
                        annotations[helm_repo_name] = { 
                            "chart_url": helm_repo_url,
                            "files": []
                        }
                else:
                    log.debug(f"Skipping '{file}' because this file is not a Helm Repository")

                if "apiVersion" in doc and doc["apiVersion"] in HELM_RELEASE_APIVERSIONS \
                        and "kind" in doc and doc["kind"] == "HelmRelease" \
                        and doc["spec"]["chart"]["spec"]["sourceRef"]["kind"] == "HelmRepository":
                    helm_release_name = doc["metadata"]["name"]
                    if "namespace" in doc["metadata"]:
                        helm_release_namespace = doc["metadata"]["namespace"]
                    else:
                        helm_release_namespace = DEFAULT_NAMESPACE
                    
                    helm_release_repository = doc["spec"]["chart"]["spec"]["sourceRef"]["name"]

                    log.info(f"Discovered Helm Release '{helm_release_name}'' in the namespace '{helm_release_namespace}'")
                    
                    if not helm_release_repository in annotations:
                        annotations[helm_release_repository] = { 
                            "chart_url": None,
                            "files": []
                        }                   
                    annotations[helm_release_repository]["files"].append(file)
                else:
                    log.debug(f"Skipping '{file}' because this file is not a Helm Release")

    for chart_name, value in annotations.items():
        if "files" in value and "chart_url" in value:
            if value["chart_url"]:
                for file in value["files"]:
                    if dry_run:
                        log.warning(f"Skipping '{chart_name}' annotations in '{file}' with '{value['chart_url']}' because this is a dry run")
                        continue

                    log.info(f"Updating '{chart_name}' renovate annotations in '{file}' with '{value['chart_url']}'")
                    with open(file, mode='r') as fid:
                        lines = fid.read().splitlines()

                    with open(file, mode='w') as fid:
                        for line in lines:
                            if RENOVATE_STRING in line:
                                continue

                            if " chart: " in line:
                                indent_spaces = len(line) - len(line.lstrip())
                                fid.write(f"{' ' * indent_spaces}{RENOVATE_STRING}{value['chart_url']}\n")
                                pass

                            fid.write(f"{line}\n")
            else:
                log.warning(f"Skipping '{chart_name}' because no matching Helm Repository was found")
        else:
            log.warning(f"Skipping '{chart_name}' no Helm Release found using '{value['chart_url']}'")
            continue

@click.pass_context
def logger(ctx):
    """Set up logging
    """
    logging.basicConfig(
        level=(logging.DEBUG if ctx.obj["debug"] else logging.INFO),
        format="%(asctime)s %(name)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    return logging.getLogger("Renovate Helm Releases")

if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    cli()
