#!/usr/bin/env python3
"""Updates HelmReleases with an annotation consumeable by rennovate.

This script adds annotations fo HelmRelease files so that rennovate can manage
chart upgrades. This script accepts a --cluster-path argument which should
point at a fluxv2 repository that contains Kustomization yaml files, referring
to HelmReleases.

The script takes two passes:
  - Pass #1: Run 'kustomize build' on all kustomizations and parse the output
    HelmRelease and HelmReposistory entries. In particular, this applies any
    overlays so that for all HelmReleases we have a full picture of the chart
    spec referencing a HelmRepository.
  - Pass #2: Read all yaml files and look for a HelmRelease chart and version.
    When found, update the file with an annotation reference to the helm
    chart in the HelmRepository. The yaml file may be an overlay with a
    partially specified chart spec.
"""

import logging
import subprocess
from pathlib import Path

import click
import yaml
import os

DEFAULT_NAMESPACE = "default"
INCLUDE_FILES = [".yaml", ".yml"]
FLUX_KUSTOMIZE_API_VERSIONS = ["kustomize.toolkit.fluxcd.io/v1beta1"]
KUSTOMIZE_API_VERSION = ["kustomize.config.k8s.io/v1beta1"]
HELM_REPOSITORY_APIVERSIONS = ["source.toolkit.fluxcd.io/v1beta1"]
HELM_RELEASE_APIVERSIONS = ["helm.toolkit.fluxcd.io/v2beta1"]
RENOVATE_STRING = "# renovate: registryUrl="
KUSTOMIZE_BIN = "kustomize"

class ClusterPath(click.ParamType):
    name = "cluster-path"
    def convert(self, value, param, ctx):
        clusterPath = Path(value)
        if not isinstance(value, tuple):
            if not clusterPath.exists:
                self.fail(f"invalid --cluster-path '{value}'")
        return clusterPath

def run_command(command):
    """Runs the specified command arguments and returns the string output."""
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = proc.communicate()
    if proc.returncode:
        log = logger()
        log.error(
            "Subprocess failed %s with return code %s", command, proc.returncode
        )
        log.info(out.decode("utf-8"))
        log.error(err.decode("utf-8"))
        return None
    return out.decode("utf-8")


def kustomize_grep(cluster_path, kind):
    """Loads all Kustomizations for a specific kind as a yaml object."""
    log = logger()
    log.debug(f"Finding resources in '{cluster_path}' for kind '{kind}'")
    command = [KUSTOMIZE_BIN, "cfg", "grep", f"kind={kind}", cluster_path]
    doc_contents = run_command(command)
    for doc in yaml.safe_load_all(doc_contents):
        yield doc


def namespaced_name(doc):
    """Returns a name for the yaml resource, falling back to a default namespace."""
    name = doc["name"]
    namespace = doc.get("namespace", DEFAULT_NAMESPACE)
    return f"{namespace}/{name}"


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

    # Build a map of HelmRepository name to chart url
    helm_repo_charts = {}
    for doc in kustomize_grep(cluster_path, "HelmRepository"):
        api_version = doc.get("apiVersion")
        if api_version not in HELM_REPOSITORY_APIVERSIONS:
            log.debug(f"Skipping HelmRepository with api_version '{api_version}'")
            continue
        helm_repo_name = namespaced_name(doc["metadata"])
        helm_repo_url = doc["spec"]["url"]
        log.info(
            f"Discovered HelmRepository '{helm_repo_name}' chart url '{helm_repo_url}'"
        )
        helm_repo_charts[helm_repo_name] = helm_repo_url

    helm_release_docs = list(kustomize_grep(cluster_path, "HelmRelease"))
    helm_releases = {}
    for doc in helm_release_docs:
        api_version = doc.get("apiVersion")
        if api_version not in HELM_RELEASE_APIVERSIONS:
            log.debug(f"Skipping HelmRelease with api_version '{api_version}'")
            continue
        # kustomize cfg adds an annotation with the source filename for the resource
        helm_release_name = namespaced_name(doc["metadata"])
        chart_spec = doc["spec"]["chart"]["spec"]
        source_ref = chart_spec.get("sourceRef")
        if not source_ref:
            # This release may be an overlay, so the repo name could be inferred from the
            # release name of the base HelmRelease in a second pass.
            log.debug(f"Skipping '{helm_release_name}': No 'sourceRef' in spec.chart.spec")
            continue
        helm_repo_name = namespaced_name(source_ref)
        if helm_repo_name not in helm_repo_charts:
            log.debug(f"Skipping '{helm_release_name}': No HelmRepository for '{helm_repo_name}'")
            continue
        if helm_release_name in helm_releases:
            if helm_releases[helm_release_name] != helm_repo_name:
                log.warning(f"Found HelmRelease '{helm_release_name}' with mismatched repo '{helm_repo_name}'")
                continue
        log.info(f"Discovered HelmRelease '{helm_release_name}' with repo '{helm_repo_name}'")
        helm_releases[helm_release_name] = helm_repo_name

    # Walk all HelmReleases and find the referenced HelmRepository by the
    # chart sourceRef and update the renovate annotation.
    for doc in helm_release_docs:
        api_version = doc.get("apiVersion")
        if api_version not in HELM_RELEASE_APIVERSIONS:
            log.debug(f"Skipping HelmRelease with api_version '{api_version}'")
            continue
        helm_release_name = namespaced_name(doc["metadata"])
        if helm_release_name not in helm_releases:
            log.debug(f"Skipping '{helm_release_name}': Could not determine repo")
            continue
        # Renovate can only update chart specs that contain a name and version,
        # so don't bother annotating if its not present.
        chart_spec = doc["spec"]["chart"]["spec"]
        if "chart" not in chart_spec or "version" not in chart_spec:
            log.debug(f"Skipping '{helm_release_name}': No 'chart' or 'version' in spec.chart.spec")
            continue
        helm_repo_name = helm_releases[helm_release_name]
        if helm_repo_name not in helm_repo_charts:
            log.debug(f"Skipping '{file}': HelmRepostory '{helm_repo_name}' not found")
            continue

        chart_url = helm_repo_charts[helm_repo_name]

        # kustomize cfg adds an annotation with the source filename for the resource
        source_filename = doc["metadata"]["annotations"]["config.kubernetes.io/path"]
        filename = os.path.join(cluster_path, source_filename)
        if not os.path.exists(filename):
            log.warning(f"Unable to update '{helm_release_name}': file '{filename}' does not exist")
            continue

        if dry_run:
            log.warning(
                f"Skipping '{helm_repo_name}' annotations in '{filename}' with '{chart_url}' as this is a dry run"
            )
            continue

        log.info(
            f"Updating '{helm_repo_name}' renovate annotations in '{filename}' with '{chart_url}'"
        )
        with open(filename, mode="r") as fid:
            lines = fid.read().splitlines()

        with open(filename, mode="w") as fid:
            for line in lines:
                if RENOVATE_STRING in line:
                    continue

                if " chart: " in line:
                    indent_spaces = len(line) - len(line.lstrip())
                    fid.write(f"{' ' * indent_spaces}{RENOVATE_STRING}{chart_url}\n")
                    pass

                fid.write(f"{line}\n")


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
