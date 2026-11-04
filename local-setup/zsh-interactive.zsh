# Interactive Zsh preferences. Non-interactive tools use shell-env.sh.
[[ -o interactive ]] || return 0
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
[ ! -s "$NVM_DIR/nvm.sh" ] || . "$NVM_DIR/nvm.sh"
[ ! -s "$NVM_DIR/bash_completion" ] || . "$NVM_DIR/bash_completion"
alias ll='ls -alFG'
alias la='ls -AG'
alias l='ls -CFG'
[ ! -r "$HOME/.config/ais/zsh-helpers.zsh" ] || . "$HOME/.config/ais/zsh-helpers.zsh"
