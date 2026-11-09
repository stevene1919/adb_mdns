"""Known Android TV application catalogue, icons and fuzzy name matching."""

from __future__ import annotations

import difflib

LAUNCHER_PACKAGES: frozenset[str] = frozenset(
    {
        "com.google.android.apps.tv.launcherx",
        "com.google.android.tvlauncher",
        "com.google.android.leanbacklauncher",
        "com.android.tv.launcher",
        "com.amazon.tv.launcher",
        "com.amazon.firebat",
    }
)

# Popular Android TV applications (package -> friendly name)
APPS: dict[str, str] = {
    "ca.bellmedia.cravetv": "Crave",
    "ca.cbc.android.cbctv": "CBC Gem",
    "com.HBO": "HBO GO (2)",
    "com.aetn.aetv.watch": "A&E",
    "com.amazon.amazonvideo.livingroom": "Prime Video",
    "com.amazon.avod": "Amazon Video",
    "com.amazon.avod.thirdpartyclient": "Amazon Prime Video",
    "com.amazon.firebat": "Prime Video (FireTV)",
    "com.amazon.firetv.youtube": "YouTube (FireTV)",
    "com.amazon.firetv.youtube.kids": "YouTube Kids (FireTV)",
    "com.amazon.imdb.tv.android.app": "IMDb TV",
    "com.amazon.venezia": "FireTV Store",
    "com.amazon.webapps.nbc.syfy": "Syfy",
    "com.android.tv.settings": "Settings",
    "com.android.vending": "Play Store",
    "com.apple.atve.amazon.appletv": "Apple TV+ (Fire TV)",
    "com.apple.atve.android.appletv": "Apple TV+",
    "com.apple.atve.sony.appletv": "Apple TV+ (Sony)",
    "com.cbs.ott": "Paramount+",
    "com.dailymotion.dailymotion": "Dailymotion",
    "com.disney.disneyplus": "Disney+",
    "com.ellation.vrv": "VRV",
    "com.estrongs.android.pop": "ES File Explorer",
    "com.facebook.katana": "Facebook Watch",
    "com.future.moviesByFawesomeAndroidTV": "Fawsome",
    "com.google.android.apps.mediashell": "Google Cast",
    "com.google.android.apps.tv.launcherx": "Google TV Launcher",
    "com.google.android.music": "Play Music",
    "com.google.android.play.games": "Play Games",
    "com.google.android.tv": "Live Channels",
    "com.google.android.tvlauncher": "Android TV Launcher",
    "com.google.android.videos": "Play Movies & TV",
    "com.google.android.youtube.tv": "YouTube",
    "com.google.android.youtube.tvkids": "YouTube Kids",
    "com.google.android.youtube.tvmusic": "YouTube Music",
    "com.google.android.youtube.tvunplugged": "YouTube TV",
    "com.graymatrix.did": "ZEE5",
    "com.haystack.android": "Haystack News",
    "com.hbo.hbonow": "HBO Max",
    "com.hulu.livingroomplus": "Hulu (2)",
    "com.hulu.plus": "Hulu",
    "com.hungama.movies.tv": "Hungama Play",
    "com.jio.media.stb.ondemand": "Jio Cinema",
    "com.liskovsoft.videomanager": "Smart YouTube TV",
    "com.mtvn.vh1android": "VH1",
    "com.mxtech.videoplayer.ad": "MX Player",
    "com.netflix.ninja": "Netflix",
    "com.nst.iptvsmarterstvbox": "IPTV Smarters Pro",
    "com.orange.ocsgo": "OCS",
    "com.peacocktv.peacockandroid": "Peacock",
    "com.phonegap.voyo": "VOYO",
    "com.plexapp.android": "Plex",
    "com.quickplay.android.bellmediaplayer": "Bell Fibe",
    "com.shawmedia.smglobal": "Global TV",
    "com.sony.dtv.bravialifehack": "BRAVIA Tutorials",
    "com.sony.dtv.braviasyncmenu": "Sync Menu",
    "com.sony.dtv.discovery": "Discover",
    "com.sony.dtv.networkapp.wifidirect": "Screen mirroring",
    "com.sony.dtv.osat.album": "Album",
    "com.sony.dtv.osat.music": "Music",
    "com.sony.dtv.osat.video": "Video",
    "com.sony.dtv.scrums.action": "Action Menu",
    "com.sony.dtv.smarthelp": "Help",
    "com.sony.dtv.sonyselect": "Sony Select",
    "com.sony.dtv.timers": "Timers",
    "com.sony.dtv.tvx": "TV",
    "com.sonyliv": "SonyLIV",
    "com.spotify.tv.android": "Spotify",
    "com.synology.dsphoto": "DS photo",
    "com.synology.dsvideo": "DS video",
    "com.ted.android.tv": "TED",
    "com.turner.tnt.android.networkapp": "Watch TNT",
    "com.valvesoftware.steamlink": "Steam Link",
    "com.vevo.tv": "Vevo",
    "com.vewd.core.integration.dia": "Internet Browser",
    "com.viewlift.hoichoi": "Hoichoi",
    "com.viki.android": "Rakuten Viki",
    "com.vimeo.android.videoapp": "Vimeo",
    "com.vmn.android.comedycentral": "Comedy Central",
    "com.ziggo.tv": "Ziggo GO TV",
    "de.cbc.tvnow.firetv": "RTL Plus",
    "de.cyberdream.dreamepg.tvh.tv.player": "DreamPlayer TVHeadend",
    "de.exaring.waipu.firetv.live": "Waipu TV",
    "de.sport1.firetv.video": "Sport 1",
    "de.telekom.magentatv.atv": "Magenta TV",
    "deezer.android.tv": "Deezer",
    "eu.hbogo.androidtv.production": "HBO GO",
    "fr.francetv.pluzz": "France TV",
    "in.startv.hotstar": "Disney+ Hotstar",
    "nl.nlziet": "NLZIET",
    "nl.nos.app": "NOS",
    "nl.uitzendinggemist": "NPO",
    "org.jellyfin.androidtv": "Jellyfin",
    "org.mozilla.tv.firefox": "Firefox",
    "org.samsonsen.nederlandse.radio.holland.nl": "Mijn Radio",
    "org.videolan.vlc": "VLC",
    "org.xbmc.kodi": "Kodi",
    "ru.iptvremote.android.iptv": "IPTV",
    "tunein.player": "TuneIn Radio",
    "tv.accedo.foodnetwork": "Food Network GO",
    "tv.emby.embyatv": "Emby",
    "tv.molotov.app": "Molotov",
    "tv.mrmc.mrmc": "MrMC",
    "tv.mrmc.mrmc.lite": "MrMC Lite",
    "tv.perception.clients.tv.android": "T-2 TV",
    "tv.twitch.android.app": "Twitch",
    "tv.twitch.android.viewer": "Twitch (FireTV)",
    # Australian & Regional Streaming apps
    "au.com.stan.and": "Stan",
    "au.net.abc.iview": "ABC iview",
    "au.streamotion.ares": "Binge",
    "tv.standard.nebula": "Nebula",
    "org.localsend.localsend_app": "LocalSend",
    "com.tpn.adbautoenable": "ADB Auto Enable",
}


# Package -> Material Design icon for the current-app sensor.
APP_ICONS: dict[str, str] = {
    "com.netflix.ninja": "mdi:netflix",
    "com.google.android.youtube.tv": "mdi:youtube",
    "com.google.android.youtube.tvkids": "mdi:youtube",
    "com.google.android.youtube.tvmusic": "mdi:youtube",
    "com.google.android.youtube.tvunplugged": "mdi:youtube-tv",
    "com.liskovsoft.videomanager": "mdi:youtube",
    "com.plexapp.android": "mdi:plex",
    "com.spotify.tv.android": "mdi:spotify",
    "org.xbmc.kodi": "mdi:kodi",
    "com.disney.disneyplus": "mdi:disney-plus",
    "tv.twitch.android.app": "mdi:twitch",
    "com.amazon.amazonvideo.livingroom": "mdi:amazon",
    "com.amazon.avod.thirdpartyclient": "mdi:amazon",
    "org.videolan.vlc": "mdi:vlc",
    "org.jellyfin.androidtv": "mdi:jellyfish",
    "tv.emby.embyatv": "mdi:emby",
    "com.android.vending": "mdi:google-play",
    "com.android.tv.settings": "mdi:cog",
    "com.google.android.apps.mediashell": "mdi:cast",
    "com.valvesoftware.steamlink": "mdi:steam",
    "org.mozilla.tv.firefox": "mdi:firefox",
    "com.apple.atve.android.appletv": "mdi:apple",
    "com.hulu.plus": "mdi:hulu",
    "au.com.stan.and": "mdi:television-classic",
    "au.net.abc.iview": "mdi:television-classic",
    "au.streamotion.ares": "mdi:television-classic",
    "tv.standard.nebula": "mdi:play-circle",
    "org.localsend.localsend_app": "mdi:share-variant",
    "com.tpn.adbautoenable": "mdi:android-debug-bridge",
}
DEFAULT_APP_ICON = "mdi:application"
LAUNCHER_ICON = "mdi:television-guide"

# Official brand logo CDN URLs for Media Browser
APP_THUMBNAILS: dict[str, str] = {
    "com.netflix.ninja": "https://brands.home-assistant.io/_/netflix/logo.png",
    "com.google.android.youtube.tv": "https://brands.home-assistant.io/_/youtube/logo.png",
    "com.google.android.youtube.tvkids": "https://brands.home-assistant.io/_/youtube/logo.png",
    "com.google.android.youtube.tvmusic": "https://brands.home-assistant.io/_/youtube_music/logo.png",
    "com.amazon.amazonvideo.livingroom": "https://brands.home-assistant.io/_/prime_video/logo.png",
    "com.amazon.avod.thirdpartyclient": "https://brands.home-assistant.io/_/prime_video/logo.png",
    "com.disney.disneyplus": "https://brands.home-assistant.io/_/disneyplus/logo.png",
    "com.spotify.tv.android": "https://brands.home-assistant.io/_/spotify/logo.png",
    "org.xbmc.kodi": "https://brands.home-assistant.io/_/kodi/logo.png",
    "com.plexapp.android": "https://brands.home-assistant.io/_/plex/logo.png",
    "org.jellyfin.androidtv": "https://brands.home-assistant.io/_/jellyfin/logo.png",
    "tv.emby.embyatv": "https://brands.home-assistant.io/_/emby/logo.png",
    "org.videolan.vlc": "https://brands.home-assistant.io/_/vlc/logo.png",
    "tv.twitch.android.app": "https://brands.home-assistant.io/_/twitch/logo.png",
    "com.apple.atve.android.appletv": "https://brands.home-assistant.io/_/apple_tv/logo.png",
    "com.google.android.apps.mediashell": "https://brands.home-assistant.io/_/google_cast/logo.png",
}


def app_thumbnail(package: str | None) -> str | None:
    """Return a logo/thumbnail URL for an app package if available."""
    if not package:
        return None
    return APP_THUMBNAILS.get(package)


def app_name(package: str | None, custom_apps: dict[str, str] | None = None) -> str | None:
    """Return the friendly name for a package (or the package id itself)."""
    if not package:
        return None
    if custom_apps and package in custom_apps:
        return custom_apps[package]
    return APPS.get(package, package)


def app_icon(package: str | None) -> str:
    """Return a Material Design icon for a package."""
    if not package:
        return DEFAULT_APP_ICON
    if package in LAUNCHER_PACKAGES:
        return LAUNCHER_ICON
    return APP_ICONS.get(package, DEFAULT_APP_ICON)


def is_launcher(package: str | None) -> bool:
    """Return True if the package is a home-screen launcher."""
    return bool(package) and package in LAUNCHER_PACKAGES


def resolve_app(
    query: str,
    installed: list[str] | None = None,
    custom_apps: dict[str, str] | None = None,
) -> str | None:
    """Resolve a friendly name, package id or fuzzy name to a package id.

    Resolution order: exact package id, exact friendly name (case-insensitive),
    then a fuzzy match over friendly names and package ids of installed apps
    (or the whole catalogue if the installed list is unknown).
    """
    if not query:
        return None
    q = query.strip()
    all_apps = {**APPS, **(custom_apps or {})}
    candidates = list(installed) if installed else list(all_apps)
    if q in candidates or (installed is None and q in all_apps):
        return q
    if "." in q and " " not in q:
        # Looks like a package id: trust it even if not in the installed list.
        return q
    lowered = q.lower()
    names = {app_name(pkg, custom_apps).lower(): pkg for pkg in candidates}  # type: ignore[union-attr]
    if lowered in names:
        return names[lowered]
    for name, pkg in names.items():
        if name.startswith(lowered) or lowered in name:
            return pkg
    close = difflib.get_close_matches(lowered, list(names), n=1, cutoff=0.6)
    if close:
        return names[close[0]]
    return None
