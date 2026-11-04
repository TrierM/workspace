# Executables isolate credentials for commands; no-argument shortcuts select a profile.
_ais_select_aws_profile() {
    local profile=$1
    command "aws-$profile" || return $?
    unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_SECURITY_TOKEN
    unset AWS_ACCESS_KEY AWS_SECRET_KEY AWS_CREDENTIAL_EXPIRATION
    unset AWS_ROLE_ARN AWS_ROLE_SESSION_NAME AWS_WEB_IDENTITY_TOKEN_FILE
    unset AWS_CONTAINER_CREDENTIALS_RELATIVE_URI AWS_CONTAINER_CREDENTIALS_FULL_URI
    unset AWS_CONTAINER_AUTHORIZATION_TOKEN AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE
    export AWS_PROFILE="$profile" AWS_DEFAULT_PROFILE="$profile"
}
aws-dev() {
    if (( $# )); then
        command aws-dev "$@"
    else
        _ais_select_aws_profile dev
    fi
}
aws-staging() {
    if (( $# )); then
        command aws-staging "$@"
    else
        _ais_select_aws_profile staging
    fi
}
aws-prod() {
    if (( $# )); then
        command aws-prod "$@"
    else
        _ais_select_aws_profile prod
    fi
}
