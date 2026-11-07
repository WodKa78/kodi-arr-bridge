# Kodi Arr Bridge

Add media to your Arr instances directly from within Kodi.

Version **0.1.2** adds selected movies to Radarr and TV series to Sonarr, using TMDb Helper for browsing and searching. The add dialog lets you choose quality profiles, root folders, monitoring, tags, and whether to search after adding. Includes the explicit **Save settings** button and Arctic Fuse 2 information-screen integration.

## Credits

This project is completely vibe coded with AI. I take no credit for the code.

## Current downloads

| Package | Current version | Download |
|---|---|---|
| Arr Bridge add-on | **0.1.2** | [script.arr.bridge-0.1.2.zip](https://raw.githubusercontent.com/WodKa78/kodi-arr-bridge/main/dist/script.arr.bridge-0.1.2.zip) |
| Repository installer for updates | **1.0.0** | [repository.arr.bridge-1.0.0.zip](https://raw.githubusercontent.com/WodKa78/kodi-arr-bridge/main/docs/repository.arr.bridge-1.0.0.zip) |

These are separate packages with independent version numbers. The repository installer **1.0.0** delivers the current Arr Bridge add-on **0.1.2** and future published updates. For easy updating, install the repository package first.

## Easy updates through the Kodi repository

Download [repository.arr.bridge-1.0.0.zip](https://raw.githubusercontent.com/WodKa78/kodi-arr-bridge/main/docs/repository.arr.bridge-1.0.0.zip) and install it using **Add-ons → Install from zip file**.
Then open **Install from repository → Arr Bridge Repository → Program add-ons → Arr Bridge → Install**.

If you installed Arr Bridge manually before, choose **Arr Bridge Repository** under **Versions** (or **Update**, depending on the skin) to install the repository copy, even if it is the same version. Do not uninstall first; keep your server settings.
Enable **Auto-update** for Arr Bridge and allow automatic installation in Kodi's global add-on update settings. Updates become available when a newer version is published in this feed.

The optional File manager address is **https://wodka78.github.io/kodi-arr-bridge/** after GitHub Pages has been enabled for `main:/docs`. The repository download and update feed work independently of Pages.

Maintainers: see [publishing instructions](tools/REPOSITORY.md).

## Manual installation — Arr Bridge 0.1.2

1. Download the current add-on: [script.arr.bridge-0.1.2.zip](https://raw.githubusercontent.com/WodKa78/kodi-arr-bridge/main/dist/script.arr.bridge-0.1.2.zip). Save the ZIP to your Kodi device.
2. In Kodi, enable **Settings → System → Add-ons → Unknown sources**, then select **Add-ons → Install from zip file** and choose that ZIP.
3. Open **Program add-ons → Arr Bridge → Server settings**, enter your Radarr/Sonarr URLs and API keys, and choose **Save settings**.
4. Run **Test server connections**. Install/enable TMDb Helper for searching.
5. Select a movie or series and choose **Add to Radarr / Sonarr** from its context menu. For the Arctic Fuse 2 information button, select **Enable Arctic Fuse 2 info button** in Arr Bridge.

Use the packaged ZIP above for installation; GitHub's **Code → Download ZIP** downloads the development repository.

**Search after adding remembers your last successful addition.** Turn it on or off in the add dialog; that choice becomes the default for both Radarr and Sonarr, even when profile/folder memory is disabled. You can also change it in Server settings. Cancelled or failed additions do not change the default. Fresh installs start with search off.

## Documentation

- [Full setup, options, skin integration and API behavior](script.arr.bridge/README.md)
- [Original validation record and device test checklist](script.arr.bridge/TESTING.md)
- [MIT license](LICENSE)

Target setup: **Kodi 22 RC1 with Arctic Fuse 2**, Radarr v3 API and Sonarr 4 v3 API. The user reported the plugin working on their setup. The original validation record is preserved with the source; its device-test caveat describes the build environment at packaging time.

## Development

The complete add-on source is in `script.arr.bridge/`. The original installation package is in `dist/`.

Run the existing tests:

```sh
cd script.arr.bridge
python3 -m unittest discover -s tests -v
```

All **48 tests passed** again before this repository upload. Tests use Kodi UI doubles and a local HTTP server; they do not run Kodi itself or contact your Arr servers.

Configure credentials inside Kodi. No personal API keys or runtime settings are included in this repository.

## Version 0.1.2

- Fixed persistence of the Search after adding switch.
- Redesigned add/settings dialogs with a dark split layout, rounded controls, separate labels and values, clearer focus, and wrapped media summaries.
- Fixed remote navigation through hidden rows.
- Reviewed Kodi 22 RC1 release notes and v22 Python/skinning API changes: no required migration identified for the APIs used. This is a source review, not live RC1 certification.
- Install the new ZIP over the existing add-on to retain server settings. See [validation notes](script.arr.bridge/TESTING.md) for device checks.
