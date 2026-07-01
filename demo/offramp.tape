# offramp launch demo — analyze -> real live replay-eval (Groq) -> governed optimize
# Record with:  vhs demo/offramp.tape   (produces demo/offramp.gif)
# Focused on AWS so every screen FITS the viewport; a hidden `clear` resets between
# beats. The live replay makes REAL Groq calls of VARIABLE latency, so instead of a
# fixed Sleep we Wait for the "VERDICT" line to actually appear before moving on —
# that keeps the tape in sync no matter how long the API round-trip takes.
# The key is sourced from ~/dev/.env inside a Hide block, so it never appears.

Output demo/offramp.gif

Set Shell bash
Set FontSize 16
Set Width 1200
Set Height 1100
Set Padding 24
Set Theme "Catppuccin Mocha"
Set TypingSpeed 22ms
Set WaitTimeout 45s

# --- hidden setup: cwd, key, a clean `offramp` command, a minimal prompt ---
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
Sleep 1500ms

# 1) ANALYZE — read-only: total spend, the SAFE lane, the ADVISORY lane
Type "offramp analyze --dry-run --cloud aws"
Sleep 700ms
Enter
Sleep 8s

Hide
Type `clear`
Enter
Show
Sleep 500ms

# 2) REPLAY-EVAL — prove a swap live on Groq (real API round-trip, variable latency).
#    n=8 so the verdict is stable (one hard prompt can't swing a 4-prompt sample).
Type "offramp replay llama-3.3-70b gpt-oss-120b --live --limit 8"
Sleep 700ms
Enter
Wait+Screen@45s /VERDICT/
Sleep 7s

Hide
Type `clear`
Enter
Show
Sleep 500ms

# 3) OPTIMIZE — governed plan: APPLY the safe wins, STAGE the eval-passed, HOLD the rest
Type "offramp optimize --dry-run --cloud aws"
Sleep 700ms
Enter
Sleep 10s

Sleep 2500ms
