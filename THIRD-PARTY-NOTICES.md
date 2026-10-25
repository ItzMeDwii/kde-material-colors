# Third-party notices

The code in this repository is MIT-licensed (see `LICENSE`). It renders themes
and templates that originate elsewhere; their provenance and terms follow.

## Vendored theme templates

`hook/templates/discord-midnight.css`, `hook/templates/discord-system24.css` and
`hook/templates/discord-material.css` are copied verbatim from Noctalia's
community templates:

- Source: https://github.com/noctalia-dev/community-templates (`discord/`)
- That repository declares no license file. It redistributes forks of the
  upstream themes below, each of which keeps its own header attribution.

### Midnight — MIT

- Upstream: https://github.com/refact0r/midnight-discord
- Copyright (c) 2025 refact0r

### system24 — MIT

- Upstream: https://github.com/refact0r/system24
- Copyright (c) 2025 refact0r

MIT license text covering the two themes above:

```
MIT License

Copyright (c) 2025 refact0r

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Material Discord

- Fork of "Material Discord" by CapnKitten:
  https://github.com/CapnKitten/BetterDiscord (themes/Material-Discord)
- Neither that repository nor the standalone
  https://github.com/CapnKitten/Material-Discord declares a license, so no
  redistribution right is granted upstream. The file is kept here as user
  configuration that `@import`s the upstream stylesheet at runtime rather than
  embedding it, and is attributed to its author. Remove it if you require a
  strictly licensed set.

## Role / palette mapping reference

`hook/mycolors.py` follows the ANSI slot mapping documented in Noctalia's
`src/theme/fixed_palette.cpp`:

- https://github.com/noctalia-dev/noctalia — MIT

## Input format reference

`hook/mycolors.py` reads the JSON written by kde-material-you-colors:

- https://github.com/LuisBocanegra/kde-material-you-colors — GPL-3.0
  (read as a file format only; no code is copied from it)
