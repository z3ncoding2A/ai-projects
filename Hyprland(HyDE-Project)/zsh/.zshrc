# Add user configurations here
# For HyDE to not touch your beloved configurations,
# we added a config file for you to customize HyDE before loading zshrc
# Edit $ZDOTDIR/.user.zsh to customize HyDE before loading zshrc

#  Plugins 
# oh-my-zsh plugins are loaded  in $ZDOTDIR/.user.zsh file, see the file for more information



# # Always mkdir a path (this doesn't inhibit functionality to make a single dir)
alias mkdir='mkdir -p'

if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi


#typeset -g POWERLEVEL9K_INSTANT_PROMPT=quiet
typeset -g POWERLEVEL9K_INSTANT_PROMPT=off


## Set the directory we want to store zinit and plugins
ZINIT_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}/zinit/zinit.git"

## Download Zinit, if it's not already there yet
if [ ! -d "$ZINIT_HOME" ]; then
	mkdir -p "$(dirname $ZINIT_HOME)"
	git clone https://github.com/zdharma-continuum/zinit.git "$ZINIT_HOME"
fi

[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh


## Source/Load zinit
source "${ZINIT_HOME}/zinit.zsh"

## Add in Powerlevel10k
zinit ice depth=1; zinit light romkatv/powerlevel10k

## Add in zsh plugins
zinit light zsh-users/zsh-syntax-highlighting
zinit light zsh-users/zsh-completions
zinit light zsh-users/zsh-autosuggestions 
zinit light Aloxaf/fzf-tab
zinit light zdharma-continuum/fast-syntax-highlighting

## Add in snippets
zinit snippet OMZP::git
zinit snippet OMZP::sudo 
zinit snippet OMZP::archlinux
zinit snippet OMZP::command-not-found
zinit snippet OMZP::colored-man-pages

## Load completions 
autoload -U compinit && compinit

zinit cdreplay -q

## Keybindings
bindkey -e
bindkey '^p' history-search-backward
bindkey '^n' history-search-forward

## History
HISTSIZE=70000
HISTFILE=~/.zsh_history
SAVEHIST=$HISTSIZE
HISTDUP=erase 
setopt appendhistory 
setopt sharehistory
setopt hist_ignore_space
setopt hist_ignore_all_dups
setopt hist_save_no_dups
setopt hist_ignore_dups
setopt hist_find_no_dups

## Completion styling
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Za-z}'
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"
zstyle ':completion:*' menu no
zstyle ':fzf-tab:complete:cd:*' fzf-preview 'exa --long --group-directories-first --header --icons=always --no-time --no-permissions $realpath'
zstyle ':fzf-tab:complete:__zoxide_z:*' fzf-preview 'exa --long --group-directories-first --header --icons=always --no-time --no-permissions $realpath'
## Shell intergrations
eval "$(fzf --zsh)"
eval "$(zoxide init --cmd cd zsh)"
eval "$(direnv hook zsh)"

###################################################################
###################################################################

################	My ZSH Configuration   #################
#==========================================================#

# Startup Message
#fastfetch --bright-color true --color-output yellow --color-keys red 

# Exports / Sources
#export PATH="$HOME/.cargo/bin:$PATH"
export EDITOR=nano
source ~/.config/zshrc.conf

# Yazi Stuff
function y() {
	local tmp="$(mktemp -t "yazi-cwd.XXXXXX")" cwd
	command yazi "$@" --cwd-file="$tmp"
	IFS= read -r -d '' cwd < "$tmp"
	[ -n "$cwd" ] && [ "$cwd" != "$PWD" ] && builtin cd -- "$cwd"
	rm -f -- "$tmp"
}

#export PATH="$HOME/.local/bin:$PATH"
export GEMINI_API_KEY="AIzaSyDQpjRmmob48QHz0PmVBZb5c_msK7f2wJA"
