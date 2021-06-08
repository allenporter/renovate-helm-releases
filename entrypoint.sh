#!/bin/sh -l

CLUSTER_PATH="${1}"
EXCLUDE_FOLDERS="${2}"
DEBUG="${3}"
DRY_RUN="${4}"
TOLERATE_YAML_ERRORS="${5}"

FLAGS=(--cluster-path="${CLUSTER_PATH}")

if [ ! -z "${EXCLUDE_FOLDERS}" ]; then
  FLAGS+=(--excluded-folders=${EXCLUDE_FOLDERS})
fi

if [ "${DEBUG}" = "yes" ]; then
    FLAGS+=("--debug")
fi

if [ "${DRY_RUN}" = "yes" ]; then
    FLAGS+=("--dry-run")
fi

if [ "${TOLERATE_YAML_ERRORS}" = "yes" ]; then
    FLAGS+=("--tolerate-yaml-errors")
fi

/usr/local/bin/python /app/renovate.py ${FLAGS[@]}
