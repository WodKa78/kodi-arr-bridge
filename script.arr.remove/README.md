# Arr Remove

Companion add-on for **Arr Bridge** that adds **Remove from Kodi / Arr** to the context menu of library movies and TV shows.

The removal menu always requires a confirmation and provides four explicit scopes:

1. Kodi library only
2. Kodi + Radarr/Sonarr record, retaining files
3. Kodi + Arr record + managed files
4. Kodi + Arr record + managed files + import-list exclusion, to prevent a configured list from adding it again

Arr is handled before Kodi. If a requested Arr operation cannot be completed or a unique match cannot be established, the Kodi entry is left unchanged.

## Install

Install `script.arr.bridge` 0.1.2 or newer first and configure Radarr/Sonarr in it. Then install `script.arr.remove-0.1.0.zip` using **Add-ons → Install from zip file**.

This add-on targets Kodi 22 / Python 3 and Radarr v3 or Sonarr v4.
