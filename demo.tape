# Demo recording for comp-evals.
# Produces demo.gif. Requires VHS (https://github.com/charmbracelet/vhs):
#   brew install vhs
#   vhs demo.tape
#
# This renders the report on an existing run (fast, no API calls). Make sure you
# have run `uv run comp-evals run --models all` at least once so results/ exists.

Output demo.gif

Set Shell "bash"
Set FontSize 15
Set Width 1200
Set Height 820
Set Padding 18
Set Theme "Catppuccin Mocha"

Type "# comp-evals: score frontier models on synthetic comp-reasoning scenarios"
Enter
Sleep 1s

Type "uv run comp-evals report --run latest"
Sleep 800ms
Enter
Sleep 6s

Type "# leaderboard + per-category + most-failed traps -> RESULTS.md"
Enter
Sleep 2s
