# Kodi Arr Bridge

Add media to your Arr instances directly from within Kodi.

Version **0.1.1** adds selected movies to Radarr and TV series to Sonarr, using TMDb Helper for browsing and searching. The add dialog lets you choose quality profiles, root folders, monitoring, tags, and whether to search after adding. Includes the explicit **Save settings** button and Arctic Fuse 2 information-screen integration.

## Install

1. Open [script.arr.bridge-0.1.1.zip](dist/script.arr.bridge-0.1.1.zip) and use GitHub's **Download raw file** button to save it to your Kodi device.
2. In Kodi, enable **Settings → System → Add-ons → Unknown sources**, then select **Add-ons → Install from zip file** and choose that ZIP.
3. Open **Program add-ons → Arr Bridge → Server settings**, enter your Radarr/Sonarr URLs and API keys, and choose **Save settings**.
4. Run **Test server connections**. Install/enable TMDb Helper for searching.
5. Select a movie or series and choose **Add to Radarr / Sonarr** from its context menu. For the Arctic Fuse 2 information button, select **Enable Arctic Fuse 2 info button** in Arr Bridge.

Use the packaged ZIP above for installation; GitHub's **Code → Download ZIP** downloads the development repository.

**Search after adding is off by default.** Enable it in the add dialog or settings when you want Radarr/Sonarr to search immediately.

## Documentation

- [Full setup, options, skin integration and API behavior](script.arr.bridge/README.md)
- [Original validation record and device test checklist](script.arr.bridge/TESTING.md)
- [MIT license](LICENSE)

Target setup: **Kodi 22.0 beta with Arctic Fuse 2**, Radarr v3 API and Sonarr 4 v3 API. The user reported the plugin working on their setup. The original validation record is preserved with the source; its device-test caveat describes the build environment at packaging time.

## Development

The complete add-on source is in `script.arr.bridge/`. The original installation package is in `dist/`.

Run the existing tests:

```sh
cd script.arr.bridge
python3 -m unittest discover -s tests -v
```

All **42 tests passed** again before this repository upload. Tests use Kodi UI doubles and a local HTTP server; they do not run Kodi itself or contact your Arr servers.

Configure credentials inside Kodi. No personal API keys or runtime settings are included in this repository.
