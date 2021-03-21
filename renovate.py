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

DEFAULT_NAMESPACE = "default"
INCLUDE_FILES = [".yaml", ".yml"]
HELM_REPOSITORY_APIVERSIONS = ["source.toolkit.fluxcd.io/v1beta1"]
HELM_RELEASE_APIVERSIONS = ["helm.toolkit.fluxcd.io/v2beta1"]
RENOVATE_STRING = "# renovate: registryUrl="
KUSTOMIZE_BIN = "kustomize"
KUSTOMIZE_CONFIG = "kustomization.yaml"


class ClusterPath(click.ParamType):
    name = "cluster-path"

    def convert(self, value, param, ctx):
        clusterPath = Path(value)
        if not isinstance(value, tuple):
            if not clusterPath.exists:
                self.fail(f"invalid --cluster-path '{value}'")
        return clusterPath


def kustomize(filename):
    command = [KUSTOMIZE_BIN, "build", filename]
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


def kustomize_build_files(files):
    """A generatoer that loads all Kustomizations and overlays in yaml."""
    log = logger()
    for file in files:
        if file.parts[-1] != KUSTOMIZE_CONFIG:
            continue
        log.debug(f"Building kustomization '{file}'")
        doc_contents = kustomize(file.parent)
        for doc in yaml.safe_load_all(doc_contents):
            yield (file.parent, doc)


def yaml_load_files(files):
    """A generator that loads the contents of all files in yaml."""
    for file in files:
        for doc in yaml.safe_load_all(file.read_bytes()):
            if doc:
                yield (file, doc)


def namespaced_name(doc):
    """Returns a name for the yaml resource, falling back to a default namespace."""
    name = doc["name"]
    namespace = doc.get("namespace", DEFAULT_NAMESPACE)
    return f"{namespace}/{name}"


@click.command()
@click.option(
    "--cluster-path",
    envvar="CLUSTER_PATH",
    type=ClusterPath(),
    required=True,
    help="Path to cluster root, e.g. './cluster'",
)
@click.option(
    "--debug",
    envvar="DEBUG",
    is_flag=True,
    default=False,
    required=False,
    help="Turn on debug logging",
)
@click.option(
    "--dry-run",
    envvar="DRY_RUN",
    is_flag=True,
    default=False,
    required=False,
    help="Do not alter Helm Release files",
)
@click.pass_context
def cli(ctx, cluster_path, debug, dry_run):
    ctx.obj = {
        "cluster_path": cluster_path,
        "debug": debug,
        "dry_run": dry_run,
    }

    # pylint: disable=no-value-for-parameter
    log = logger()

    # The name of each HelmRepository and its chart url
    helm_repo_charts = {}
    # The name of each HelmRelease and the referenced HelmRepository
    helm_releases = {}

    # Walk the Kustomizations and find HelmRepository and HelmRelease entries including all overlays
    files = [p for p in cluster_path.rglob("*") if p.suffix in INCLUDE_FILES]
    for (basename, doc) in kustomize_build_files(files):
        api_version = doc.get("apiVersion")
        kind = doc.get("kind")

        if api_version in HELM_REPOSITORY_APIVERSIONS and kind == "HelmRepository":
            helm_repo_name = namespaced_name(doc["metadata"])
            helm_repo_url = doc["spec"]["url"]
            log.info(
                f"Discovered HelmRepository '{helm_repo_name}' chart url '{helm_repo_url}'"
            )
            helm_repo_charts[helm_repo_name] = helm_repo_url

        if api_version in HELM_RELEASE_APIVERSIONS and kind == "HelmRelease":
            if doc["spec"]["chart"]["spec"]["sourceRef"]["kind"] != "HelmRepository":
                continue
            helm_release_name = namespaced_name(doc["metadata"])
            helm_repo_name = namespaced_name(doc["spec"]["chart"]["spec"]["sourceRef"])
            log.info(f"Discovered HelmRelease '{helm_release_name}' in {basename}")
            if helm_release_name not in helm_releases:
                helm_releases[helm_release_name] = helm_repo_name
            else:
                if helm_releases[helm_release_name] != helm_repo_name:
                    log.error(
                        f"HelmRelease '{helm_release_name}' mismatch ({helm_repo_name} != {helm_releases[helm_release_name]}"
                    )

    # Walk the underlying files, and update the HelmRelease with the appropriate
    # HelmRepository chart url as a rennovate comment.
    for (file, doc) in yaml_load_files(files):
        if (
            doc.get("apiVersion") not in HELM_RELEASE_APIVERSIONS
            or not doc.get("kind") == "HelmRelease"
        ):
            log.debug(f"Skipping '{file}': Not a Helm Release")
            continue
        helm_release_name = namespaced_name(doc["metadata"])
        if helm_release_name not in helm_releases:
            log.debug(
                f"Skipping '{file}': HelmRelease '{helm_release_name}' not found"
            )
            continue
        helm_repo_name = helm_releases[helm_release_name]
        if helm_repo_name not in helm_repo_charts:
            log.debug(
                f"Skipping '{file}': HelmRepostory '{helm_repo_name}' not found"
            )
            continue
        chart_spec = doc["spec"]["chart"]["spec"]
        if "chart" not in chart_spec or "version" not in chart_spec:
            log.debug(
                f"Skipping '{helm_repo_name}': Does not contain 'chart' or 'version' in spec.chart.spec"
            )
            continue
        chart_url = helm_repo_charts[helm_repo_name]
        if dry_run:
            log.warning(
                f"Skipping '{helm_repo_name}' annotations in '{file}' with '{chart_url}' as this is a dry run"
            )
            continue

        log.info(
            f"Updating '{helm_repo_name}' renovate annotations in '{file}' with '{chart_url}'"
        )
        with open(file, mode="r") as fid:
            lines = fid.read().splitlines()

        with open(file, mode="w") as fid:
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
    """Set up logging"""
    logging.basicConfig(
        level=(logging.DEBUG if ctx.obj["debug"] else logging.INFO),
        format="%(asctime)s %(name)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("Renovate Helm Releases")


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    cli()
