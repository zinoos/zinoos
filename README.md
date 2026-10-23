<!--
            .        *          .               .
      *          you found the source.     ✶
                  hi, fellow explorer.            .
        .                                  *
                       /\
                      /  \        every image below is plain text:
          .          |    |       ascii characters, drawn into svgs
                     | () |       by scripts/build.py, refreshed daily.
             *       |    |
                    /|    |\           .
                   / |    | \                  *
                  /__|____|__\
                     ||  ||       .
          .          /\  /\
                    '  ''  '              .
-->

<p align="center">
  <img src="assets/hero.svg" width="100%" alt="ZINO in large ascii block letters beside a rotating ascii gas giant with rings, among twinkling stars. hi, i'm zino, developer from zürich. giving ai agents their own desktops.">
</p>

<p align="center">
  <img src="assets/sky.svg" width="100%" alt="The night sky above zürich, drawn in ascii: every star is a day of my github contributions from the last year, brighter stars for busier days, over an ascii alpine skyline and lake, with tonight's real moon phase.">
</p>

<p align="center">
  <img src="assets/telemetry.svg" width="100%" alt="Telemetry readout from an ascii satellite: callsign, base, mission day, contributions, streak, public repos and stars, plus a bar of the languages I write.">
</p>

<p align="center">
  <a href="https://github.com/zinoos/agent-control"><img src="assets/mission-agent-control.svg" width="49%" alt="mission 01: agent-control. watch and talk to your claude code agents."></a>
  <a href="https://github.com/zinoos/hypr-computer"><img src="assets/mission-hypr-computer.svg" width="49%" alt="mission 02: hypr-computer. computer use for hyprland as an mcp server."></a>
</p>

<details>
<summary><sub>how this profile works</sub></summary>
<br>

- **No screenshots, no GIFs.** Everything above is monospace text drawn into hand-written SVGs.
- **The planet** is ray-traced into ascii: sphere and ring intersections, diffuse light, the ring's shadow, and a storm that rotates across 24 frames.
- **The sky** is my contribution graph. Each star is a day in the last year, and the dashed line joins my busiest days.
- **The moon** is tonight's real phase over Zürich, recomputed every morning.
- **A GitHub Action** runs [`scripts/build.py`](scripts/build.py) daily. It uses only the Python standard library and the GraphQL API, with [JetBrains Mono](https://github.com/JetBrains/JetBrainsMono) (OFL) subset and embedded so the ascii lines up everywhere.

</details>

<p align="center">
  <img src="assets/footer.svg" width="100%" alt="A small ascii rocket flying across the stars. end of transmission.">
</p>
