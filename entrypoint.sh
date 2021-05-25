#!/bin/sh -l

CLUSTER_PATH="${1}"
EXCLUDE_FOLDERS="${2}"
DEBUG="${3}"
DRY_RUN="${4}"
TOLERATE_YAML_ERRORS="${5}"

if [ "${DEBUG}" = "yes" ]; then
    DEBUG="--debug"
else
    DEBUG=""
fi

if [ "${DRY_RUN}" = "yes" ]; then
    DRY_RUN="--dry-run"
else
    DRY_RUN=""
fi

if [ "${TOLERATE_YAML_ERRORS}" = "yes" ]; then
    TOLERATE_YAML_ERRORS="--tolerate-yaml-errors"
else
    TOLERATE_YAML_ERRORS=""
fi

/usr/local/bin/python /app/renovate.py --cluster-path="${CLUSTER_PATH}" --excluded-folders="${EXCLUDE_FOLDERS}" ${DEBUG} ${DRY_RUN} ${TOLERATE_YAML_ERRORS}
