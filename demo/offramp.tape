# offramp launch demo — analyze -> real live replay-eval (Groq) -> governed optimize
# Record with:  vhs demo/offramp.tape   (produces demo/offramp.gif)
# The live replay makes REAL Groq API calls; the key is sourced from ~/dev/.env
# inside a Hide block, so its value never appears on screen.

Output demo/offramp.gif

Set Shell bash
Set FontSize 15
Set Width 1240
Set Height 820
Set Padding 28
Set Theme "Catppuccin Mocha"
Set TypingSpeed 30ms

# --- hidden setup: cwd, key, a clean `offramp` alias, a minimal prompt ---
Hide
Type `cd ~/dev/offramp`
Enter
Type `set -a; source ~/dev/.env; set +a`
Enter
Type `offramp() { python3 -m offramp.cli "$@"; }`
Enter
Type `export PS1=$'\033[38;5;117m❯\033[0m '`
Enter
Type `clear`
Enter
Show
Sleep 800ms

# 1) ANALYZE — one read-only pass across AWS + Google + Azure
Type "offramp analyze --dry-run"
Sleep 400ms
Enter
Sleep 4s

# 2) REPLAY-EVAL — prove a swap on real prompts, live on Groq, LLM-as-judge
Type "offramp replay llama-3.3-70b gpt-oss-120b --live --limit 4"
Sleep 400ms
Enter
Sleep 11s

# 3) OPTIMIZE — governed plan: APPLY the safe wins, STAGE the bets, HOLD the fails
Type "offramp optimize --dry-run"
Sleep 400ms
Enter
Sleep 5s

Sleep 1500ms
