# Lightweight environment shared by Zsh, Bash, and POSIX login shells.
# Keep startup silent: no package managers, interactive tools, or logins.
[ ! -r "$HOME/.config/ais/credentials.sh" ] || . "$HOME/.config/ais/credentials.sh"
export KIND_EXPERIMENTAL_PROVIDER=podman
export CODEX_DISABLE_UPDATE_CHECK=1
_ais_brew_prefix=${HOMEBREW_PREFIX:-}
if [ -z "$_ais_brew_prefix" ]; then
    if [ -x /opt/homebrew/bin/brew ]; then
        _ais_brew_prefix=/opt/homebrew
    elif [ -x /usr/local/bin/brew ]; then
        _ais_brew_prefix=/usr/local
    fi
fi
if [ -n "$_ais_brew_prefix" ]; then
    if [ -z "${JAVA_HOME:-}" ] && [ -d "$_ais_brew_prefix/opt/openjdk/libexec/openjdk.jdk/Contents/Home" ]; then
        export JAVA_HOME="$_ais_brew_prefix/opt/openjdk/libexec/openjdk.jdk/Contents/Home"
    fi
    if [ -z "${MAVEN_HOME:-}" ] && [ -d "$_ais_brew_prefix/opt/maven/libexec" ]; then
        export MAVEN_HOME="$_ais_brew_prefix/opt/maven/libexec"
    fi
    if [ -z "${GRADLE_HOME:-}" ] && [ -d "$_ais_brew_prefix/opt/gradle" ]; then
        export GRADLE_HOME="$_ais_brew_prefix/opt/gradle"
    fi
fi
export KAFKA_HEAP_OPTS="${KAFKA_HEAP_OPTS:--Xmx2G}"
export NO_PROXY="${NO_PROXY:-127.0.0.1,localhost,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16}"
export no_proxy="${no_proxy:-$NO_PROXY}"

if [ -z "${ZSCALER_CERTIFICATE_PATH:-}" ] && [ -r "$HOME/.config/ais/zscaler-certificate" ]; then
    {
        IFS= read -r _ais_certificate <&3 || :
        IFS= read -r _ais_certificate_extra <&3 || :
    } 3< "$HOME/.config/ais/zscaler-certificate"
    case "$_ais_certificate" in
        /*)
            if [ -z "$_ais_certificate_extra" ]; then
                export ZSCALER_CERTIFICATE_PATH="$_ais_certificate"
            fi
            ;;
    esac
    unset _ais_certificate _ais_certificate_extra
fi

_ais_prepend_path() {
    [ -d "$1" ] || return 0
    case ":$PATH:" in
        *":$1:"*) ;;
        *) PATH="$1${PATH:+:$PATH}" ;;
    esac
}
_ais_append_path() {
    [ -d "$1" ] || return 0
    case ":$PATH:" in
        *":$1:"*) ;;
        *) PATH="${PATH:+$PATH:}$1" ;;
    esac
}
if [ -n "$_ais_brew_prefix" ]; then
    _ais_prepend_path "$_ais_brew_prefix/sbin"
    _ais_prepend_path "$_ais_brew_prefix/bin"
fi
[ -z "${GRADLE_HOME:-}" ] || _ais_prepend_path "$GRADLE_HOME/bin"
[ -z "${MAVEN_HOME:-}" ] || _ais_prepend_path "$MAVEN_HOME/bin"
[ -z "${JAVA_HOME:-}" ] || _ais_prepend_path "$JAVA_HOME/bin"
# Podman Desktop installs its CLI outside the Homebrew prefix.
_ais_prepend_path /opt/podman/bin
_ais_prepend_path "$HOME/bin"
_ais_prepend_path "$HOME/.local/bin"
if [ -n "$_ais_brew_prefix" ]; then
    _ais_append_path "$_ais_brew_prefix/opt/go/bin"
fi
unset _ais_brew_prefix
if [ -r "$HOME/.config/ais/workspace" ]; then
    IFS= read -r _ais_workspace < "$HOME/.config/ais/workspace" || :
    case "$_ais_workspace" in
        /*) _ais_append_path "$_ais_workspace/iip-tooling/iip-mani" ;;
    esac
    unset _ais_workspace
fi
# Deduplicate inherited PATH entries as well, preserving order and empty entries.
_ais_path_remaining=${PATH-}
_ais_path_unique=
_ais_path_seen=:
_ais_path_sep=
while :; do
    case "$_ais_path_remaining" in
        *:*) _ais_path_item=${_ais_path_remaining%%:*}; _ais_path_remaining=${_ais_path_remaining#*:}; _ais_path_last=0 ;;
        *) _ais_path_item=$_ais_path_remaining; _ais_path_last=1 ;;
    esac
    case "$_ais_path_seen" in
        *":$_ais_path_item:"*) ;;
        *) _ais_path_unique="$_ais_path_unique$_ais_path_sep$_ais_path_item"; _ais_path_sep=:; _ais_path_seen="$_ais_path_seen$_ais_path_item:" ;;
    esac
    [ "$_ais_path_last" = 1 ] && break
done
PATH=$_ais_path_unique
export PATH
unset _ais_path_remaining _ais_path_unique _ais_path_seen _ais_path_sep _ais_path_item _ais_path_last
unset -f _ais_prepend_path _ais_append_path
