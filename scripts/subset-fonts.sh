#!/usr/bin/env bash
# One-off: subset JetBrains Mono (OFL) to the glyphs the SVGs use, so build.py
# can embed them without any dependencies. Re-run only when adding new glyphs.
set -euo pipefail
cd "$(dirname "$0")/fonts"
src=$(nix build nixpkgs#jetbrains-mono --no-link --print-out-paths)/share/fonts/truetype
extra="─│╭╮╰╯├┤┬┴┼═║╔╗╚╝█▓▒░▀▄▌▐·✶⋆◆◇●○◉◦•°↗→←↑↓▮▯äöüÄÖÜéèàç—–…‾¯˙∙⊛◌☾☽≡≈∿⌁"
for w in Regular Bold; do
  uv run -q --with fonttools --with brotli pyftsubset "$src/JetBrainsMono-$w.ttf" \
    --unicodes="U+0020-007E" --text="$extra" --flavor=woff2 \
    --layout-features='' --no-hinting --output-file="jbm-${w,,}.woff2"
done
ls -l
