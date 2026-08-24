from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

# Supported public video domains
DOMAINS = {
    "facebook.com",
    "fb.watch",

    "instagram.com",

    "youtube.com",
    "youtu.be",

    "tiktok.com",

    "x.com",
    "twitter.com",

    "snapchat.com",

    "telegram.me",
    "t.me",
    "telegram.org",

    "pinterest.com",
    "pin.it",

    "linkedin.com",

    "reddit.com",
    "redd.it",

    # Threads
    "threads.net",
    "threads.com",

    "tumblr.com",

    "vimeo.com",

    "dailymotion.com",
    "dai.ly",

    "likee.video",

    "kwai.com",
    "kwai-video.com",

    "rumble.com",

    "bilibili.com",
    "b23.tv",

    "triller.co",

    "mojapp.in",

    # Josh
    "joshapp.com",
    "joshapp.in",
    "myjosh.in",
    "joshapp.net",
    "myjosh.in",

    "chingari.io",

    "sharechat.com",

    "kooapp.com",

    "roposo.com",

    "public.com",

    "mitron.tv",
}


def get_host(url):
    try:
        return (
            urlparse(url)
            .netloc
            .lower()
            .split(":")[0]
            .removeprefix("www.")
        )
    except Exception:
        return ""


def is_allowed(url):
    host = get_host(url)

    return any(
        host == domain or host.endswith("." + domain)
        for domain in DOMAINS
    )


def get_media_type(media):
    mime = (media.get("mime_type") or "").lower()
    ext = (media.get("ext") or "").lower()
    url = (media.get("url") or "").lower()

    # Video
    if (
        mime.startswith("video/")
        or ext in {
            "mp4",
            "webm",
            "mov",
            "m4v",
            "flv",
            "mkv",
        }
        or ".m3u8" in url
    ):
        return "video"

    # Photo
    if (
        mime.startswith("image/")
        or ext in {
            "jpg",
            "jpeg",
            "png",
            "webp",
            "gif",
            "avif",
        }
    ):
        return "photo"

    return "media"


def collect_media(info):
    results = []

    def walk(item):

        if not isinstance(item, dict):
            return

        if item.get("url"):

            results.append(
                {
                    "type": get_media_type(item),
                    "url": item["url"],
                    "ext": item.get("ext"),
                    "format_id": item.get("format_id"),
                    "mime_type": item.get("mime_type"),
                    "width": item.get("width"),
                    "height": item.get("height"),
                }
            )

        for entry in item.get("entries") or []:
            walk(entry)

    walk(info)

    # Remove duplicate URLs
    seen = set()
    unique = []

    for media in results:

        url = media["url"]

        if url not in seen:
            seen.add(url)
            unique.append(media)

    return unique


def extract_video(url):

    options = {
        "quiet": True,
        "no_warnings": True,

        # Extraction only
        "skip_download": True,

        "extract_flat": False,

        "noplaylist": False,

        "socket_timeout": 30,

        "retries": 2,
    }

    with yt_dlp.YoutubeDL(options) as ydl:

        return ydl.extract_info(
            url,
            download=False
        )


@app.get("/")
def home():

    return jsonify(
        status="online",
        service="VixRola Universal Video API",
        version="5",
        engine="yt-dlp"
    )


@app.get("/health")
def health():

    return jsonify(
        status="ok",
        version="5"
    )


@app.route(
    "/download",
    methods=["GET", "POST"]
)
def download():

    # GET
    url = request.args.get("url")

    # POST JSON
    if not url and request.is_json:

        data = request.get_json(
            silent=True
        ) or {}

        url = data.get("url")

    # Missing URL
    if not url:

        return jsonify(
            status="error",
            message="URL is required."
        ), 400

    # Domain check
    if not is_allowed(url):

        return jsonify(
            status="error",
            message="This domain is not enabled."
        ), 400

    platform = get_host(url)

    try:

        info = extract_video(url)

        media = collect_media(info)

        # VIDEO ONLY
        videos = [
            item
            for item in media
            if item["type"] == "video"
        ]

        if not videos:

            return jsonify(
                status="error",
                platform=platform,
                message=(
                    "No accessible video media "
                    "was returned by yt-dlp."
                )
            ), 422

        # Prefer direct MP4
        def video_score(item):

            score = 0

            ext = (
                item.get("ext") or ""
            ).lower()

            media_url = (
                item.get("url") or ""
            ).lower()

            # MP4 preferred
            if ext == "mp4":
                score += 100

            # Direct file preferred over HLS
            if ".m3u8" not in media_url:
                score += 30

            # Prefer higher resolution
            height = item.get("height")

            if height:

                try:

                    score += min(
                        int(height),
                        2160
                    ) / 10

                except Exception:
                    pass

            return score

        videos.sort(
            key=video_score,
            reverse=True
        )

        best_video = videos[0]

        return jsonify(

            status="success",

            platform=platform,

            title=(
                info.get("title")
                or info.get("description")
                or "Video"
            ),

            media_type="video",

            download_url=best_video["url"],

            media=videos,

            count=len(videos)
        )

    except yt_dlp.utils.DownloadError as error:

        return jsonify(

            status="error",

            platform=platform,

            message=(
                "yt-dlp could not "
                "extract this video."
            ),

            details=str(error)

        ), 422

    except Exception as error:

        app.logger.exception(
            "Video extraction failed"
        )

        return jsonify(

            status="error",

            platform=platform,

            message="Extraction failed.",

            details=str(error)

        ), 500


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000
    )
