# Capture crisp stills of the REAL offramp output for the Remotion hero video.
# Produces demo/remotion/public/{analyze,replay,optimize}.png
Output demo/remotion/.screens-throwaway.gif

Set Shell bash
Set FontSize 20
Set Width 1280
Set Height 1300
Set Padding 40
Set Theme "Catppuccin Mocha"
Set WaitTimeout 45s

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

Type "offramp analyze --dry-run --cloud aws"
Enter
Sleep 2s
Screenshot demo/remotion/public/analyze.png

Type `clear`
Enter
Sleep 300ms
Type "offramp replay llama-3.3-70b gpt-oss-120b --live --limit 8"
Enter
Wait+Screen@45s /VERDICT/
Sleep 600ms
Screenshot demo/remotion/public/replay.png

Type `clear`
Enter
Sleep 300ms
Type "offramp optimize --dry-run --cloud aws"
Enter
Sleep 2s
Screenshot demo/remotion/public/optimize.png
Show
Sleep 300ms
