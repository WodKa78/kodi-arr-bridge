# Arr Bridge 0.1.1

Add a movie or TV series selected in Kodi directly to Radarr or Sonarr, with a remote-friendly options dialog. Built for the requested Kodi 22 beta / Arctic Fuse 2 setup; live testing on that setup is still required. Uses Kodi's Python 3 API, with no pip packages or separate server component.

## Installation and setup

1. Download `script.arr.bridge-0.1.1.zip` to your Kodi device.
2. In Kodi, enable **Settings → System → Add-ons → Unknown sources** if needed. Choose **Add-ons → Install from zip file** and select the ZIP. Do not unzip it first.
3. Open **Program add-ons → Arr Bridge → Server settings**. Enter your Radarr and Sonarr addresses and API keys. Find each key in that application's **Settings → General → Security**. Choose **Save settings** at the bottom to apply your changes; a confirmation appears. **Cancel** or Back discards edits. Existing values are loaded when the form opens. Enter keys on your device; do not send them in chat.
4. Use full reachable addresses such as `http://192.168.1.50:7878` and `http://192.168.1.50:8989`. Include a reverse-proxy URL base if used, for example `https://media.example/radarr`. `localhost` means the Kodi device itself. Root folder paths are paths on the Arr server, not the Kodi device.
5. Choose **Test server connections**. Configure quality profiles and root folders in each Arr application before adding media.
6. Ensure TMDb Helper is installed and enabled. Existing Arctic Fuse 2 installations normally already have it. It is optional in the add-on manifest so a missing third-party repository does not block ZIP installation; searching requires it.
7. With Arctic Fuse 2 active, open Arr Bridge and choose **Enable Arctic Fuse 2 info button**. The skin reloads. The action appears as **Add to Arr** in the movie/series information action bar.

## Daily use

Search using TMDb Helper directly, your Arctic Fuse 2 TMDb Helper search/widgets, or Arr Bridge's **Search movies / Search TV series** entries. Arr Bridge opens TMDb Helper's own results, preserving your existing browse experience.

On a selected movie or show, open the context menu (long-press OK, C, or right-click as supported by your remote) and choose **Add to Radarr / Sonarr**. Alternatively, open its information screen and select **Add to Arr** after enabling the AF2 integration.

The dialog loads the server's current choices:

| Setting | Movies / Radarr | Series / Sonarr |
|---|---|---|
| Quality profile | Existing server profiles | Existing server profiles |
| Allowed qualities | Summary from the selected profile | Summary from the selected profile |
| Root folder | Server movie folders | Server series folders |
| Monitoring | On / off | All, future, missing, first season, last season, none, selected seasons |
| Availability | Announced, in cinemas, released | — |
| Season selection | — | Choose seasons, optionally including specials |
| Series type | — | Standard, daily, anime |
| Season folders | — | On / off |
| Tags | Existing server tags | Existing server tags |
| Search after adding | Optional | Optional, for monitored episodes |

Select **Add** to submit. Back/Escape or Cancel makes no addition. Search is off by default and can be enabled per addition or in settings. The last quality profile and folder are remembered separately per configured server. Choices are revalidated against the current lists each time.

**Quality profile is the quality selector:** the Arr API assigns a `qualityProfileId`; it does not accept a standalone “download in 1080p” property on add. Create profiles such as *1080p* and *2160p* in your servers to select these targets here. The add-on does not rewrite shared server profiles. Language and custom-format rules stay in the selected profile; Sonarr 3's separate language-profile API is not implemented. Sonarr 4 is the target.

Adding an episode or season adds its **parent series**. Use **Selected seasons** if you want only particular seasons monitored. With the All monitoring option, Sonarr applies its own All behavior; choose explicit seasons to control specials. This version does not add a single episode independently or change a series that already exists.

## System-wide integration and its boundary

The context action is registered globally for recognizable video items, including library items, TMDb Helper lists, and skin widgets that expose a Kodi context menu. A provider must supply a title and/or external IDs. Unknown IDs are never treated as a guaranteed match.

The **Install Ctrl+Shift+A shortcut** menu option creates an isolated `special://profile/keymaps/arrbridge.xml`. Use the shortcut on a focused media item or its information screen. The corresponding Remove option deletes only that unmodified file. You can map a spare remote button to the same command with your preferred keymap editor:

```text
RunScript(script.arr.bridge,action=add)
```

Kodi does not provide a universal hook that inserts a visible button into every skin or third-party custom information window. This package includes a specific Arctic Fuse 2 integration and a general RunScript entry point. Other custom windows may need their own button or explicit media arguments. If an item lacks IDs, the add-on asks you to confirm an Arr title match; it does not silently pick the first search result.

## Arctic Fuse 2 information button

The installer changes only `1080i/Includes_Items.xml` in the active `skin.arctic.fuse.2` add-on. It inserts a marked button in `Items_DialogVideoInfo_MenuBar` and reuses AF2's `DialogInfo_Button_Expansion` styling. It validates XML, checks its insertion point and control IDs, and preserves an initial `.arrbridge-backup` file beside the original. Unsupported layouts are refused.

Use **Remove Arctic Fuse 2 info button** to remove only the marked insertion. It preserves unrelated skin edits. Remove the integration before uninstalling Arr Bridge if you also want the inserted XML gone. A skin update can remove the button; enable it again if needed. A read-only skin directory prevents installation; the context action and shortcut remain available.

The upstream AF2 project was archived and points future development to AF3. This integration intentionally targets your AF2 installation. It is not an AF3 patch.

## Explicit calls for skin/add-on authors

```text
RunScript(script.arr.bridge,action=add,type=movie,tmdb_id=603)
RunScript(script.arr.bridge,action=add,type=tv,tvdb_id=81189)
RunScript(script.arr.bridge,action=add,type=tv,tmdb_id=1396,title=Breaking%20Bad)
RunScript(script.arr.bridge,action=settings)
RunScript(script.arr.bridge,action=test)
```

Supported arguments: `action`, `type` (`movie` or `tv`), `tmdb_id`, `tvdb_id`, `imdb_id`, `title`, `year`. URL-encode argument values. For a season/episode, pass **parent show IDs**. Explicit IDs replace focused-item metadata rather than mixing identities. For a TV item without a TVDb ID, supply the show title too: Sonarr title lookup is used, with explicit match confirmation when its response has no comparable external ID. No additional TMDb API key or access to TMDb Helper's internal Python modules is needed.

## Network behavior and duplicates

Uses `/api/v3/movie[/lookup]`, `/api/v3/series[/lookup]`, `/api/v3/qualityprofile`, `/api/v3/rootfolder`, `/api/v3/tag`, and `/api/v3/system/status`. POST is limited to the final movie/series addition. Existing titles are checked before displaying the form and immediately before adding. Server-side duplicate validation also handles races.

API keys are transmitted in `X-Api-Key`, not query strings. HTTPS certificate validation is enabled. HTTP redirects are refused so API keys are not forwarded to another host or login page. Credentials are stored in Kodi add-on settings; masking the field does not encrypt Kodi's settings file. Use HTTPS when the connection needs transport encryption.

No automatic retry is made after an uncertain POST failure. If an add times out, inspect the Arr library before trying again. Successful “search requested” means the Arr API accepted the add/search options; it does not guarantee that a release exists or that a download has completed.

## Validation and source references

See `TESTING.md` for completed checks and the remaining device test. Full editable source and tests are inside this ZIP. Run tests from the add-on directory with `python -m unittest discover -s tests -v`.

- [Kodi context-item extension and selected ListItem](https://kodi.wiki/view/Context_Item_Add-ons)
- [Kodi RunScript and other built-ins](https://kodi.wiki/view/List_of_built-in_functions)
- [Radarr API](https://radarr.video/docs/api/)
- [Sonarr API](https://sonarr.tv/docs/api/)
- [TMDb Helper source](https://github.com/jurialmunkey/plugin.video.themoviedb.helper), inspected commit `1420564c7a714e9537e6aef849c5cb555805d415`
- [Arctic Fuse 2 source](https://github.com/jurialmunkey/skin.arctic.fuse.2), inspected commit `e138a25fe11f24254c6456711d37ac9d1053f541`

This is an independent add-on, not an official Kodi, TMDb Helper, Radarr, Sonarr, or Arctic Fuse release.
