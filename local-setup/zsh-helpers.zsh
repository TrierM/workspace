# Executables own login/mirroring; these functions only update the interactive parent.
aws-dev() {
    if (( $# )); then
        command aws-dev "$@"
    else
        command aws-dev && export AWS_PROFILE=dev
    fi
}
aws-staging() {
    if (( $# )); then
        command aws-staging "$@"
    else
        command aws-staging && export AWS_PROFILE=staging
    fi
}
aws-prod() {
    if (( $# )); then
        command aws-prod "$@"
    else
        command aws-prod && export AWS_PROFILE=prod
    fi
}
