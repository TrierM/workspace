# Login shell setup; common environment remains lightweight and silent.
_ais_login_brew=
if [ -n "${HOMEBREW_PREFIX:-}" ] && [ -x "$HOMEBREW_PREFIX/bin/brew" ]; then
    _ais_login_brew="$HOMEBREW_PREFIX/bin/brew"
elif [ -x /opt/homebrew/bin/brew ]; then
    _ais_login_brew=/opt/homebrew/bin/brew
elif [ -x /usr/local/bin/brew ]; then
    _ais_login_brew=/usr/local/bin/brew
fi
if [ -n "$_ais_login_brew" ]; then
    eval "$("$_ais_login_brew" shellenv)"
fi
unset _ais_login_brew
[ ! -r "$HOME/.config/ais/shell-env.sh" ] || . "$HOME/.config/ais/shell-env.sh"
