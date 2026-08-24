from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
from urllib.parse import urlparse

app = Flask(__name__)
CORS(app)

# केवल अभी test किए हुए 10 platforms
DOMAINS = {
    "facebook.com",
    "fb.watch",

    "instagram.com",

    "x.com",
    "twitter.com",

    "pinterest.com",
    "pin.it",

    "reddit.com",
    "redd.it",

    "snapchat.com",

    "telegram.me",
    "t.me",
    "telegram.org",

    "linkedin.com",

    "mojapp.in",

    "joshapp.com",
    "joshapp.in",
    "myjosh.in",
    "joshapp.net",
    "share.myjosh.in",
}


def host(url):
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


def allowed(url):
    h = host(url)

    return any(
        h == domain or h.endswith("." + domain)
        for domain in DOMAINS
    )


def kind(item):
    """
    Better video detection.

    कई extractors ext/mime_type खाली दे सकते हैं,
    लेकिन vcodec उपलब्ध होता है।
    """

    mime = (
        item.get("mime_type")
        or ""
    ).lower()

    ext = (
        item.get("ext")
        or ""
    ).lower()

    url = (
        item.get("url")
        or ""
    ).lower()

    vcodec = (
        item.get("vcodec")
        or ""
    ).lower()

    # --------------------------------
    # 1. yt-dlp vcodec detection
    # --------------------------------

    if vcodec and vcodec != "none":
        return "video"

    # --------------------------------
    # 2. MIME detection
    # --------------------------------

    if mime.startswith("video/"):
        return "video"

    if mime.startswith("image/"):
        return "photo"

    # --------------------------------
    # 3. Extension detection
    # --------------------------------

    video_exts = {
        "mp4",
        "webm",
        "mov",
        "m4v",
        "flv",
        "mkv",
        "ts",
    }

    photo_exts = {
        "jpg",
        "jpeg",
        "png",
        "webp",
        "gif",
        "avif",
    }

    if ext in video_exts:
        return "video"

    if ext in photo_exts:
        return "photo"

    # --------------------------------
    # 4. HLS
    # --------------------------------

    if ".m3u8" in url:
        return "video"

    # --------------------------------
    # 5. Direct video URL fallback
    # --------------------------------

    video_patterns = (
        ".mp4",
        ".webm",
        ".mov",
        ".m4v",
        ".m3u8",

        "video.twimg.com/",
        "v.redd.it/",
        "pinimg.com/videos/",
        "cdninstagram.com/",
        "fbcdn.net/",
        "sc-cdn.net/",
        "telesco.pe/",
        "licdn.com/",
        "myjosh.in/",
        "share.myjosh.in/",
        "mojapp.in/",
        "sharechat.com/",
    )

    if any(
        pattern in url
        for pattern in video_patterns
    ):
        return "video"

    return "media"


def collect(info):
    results = []

    def walk(item):

        if not isinstance(item, dict):
            return

        if item.get("url"):

            results.append(
                {
                    "type": kind(item),
                    "url": item["url"],
                    "ext": item.get("ext"),
                    "format_id": item.get("format_id"),
                    "mime_type": item.get("mime_type"),
                    "vcodec": item.get("vcodec"),
                    "acodec": item.get("acodec"),
                    "width": item.get("width"),
                    "height": item.get("height"),
                }
            )

        for entry in (
            item.get("entries")
            or []
        ):
            walk(entry)

    walk(info)

    # Remove duplicate URLs
    seen = set()
    unique = []

    for item in results:

        url = item["url"]

        if url not in seen:

            seen.add(url)
            unique.append(item)

    return unique


@app.get("/")
def home():

    return jsonify(
        status="online",
        service="VixRola Universal Video API",
        version="4.1",
        engine="yt-dlp"
    )


@app.get("/health")
def health():

    return jsonify(
        status="ok",
        version="4.1"
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

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        url = data.get("url")

    if not url:

        return jsonify(
            status="error",
            message="URL is required."
        ), 400

    # Domain check
    if not allowed(url):

        return jsonify(
            status="error",
            message="This domain is not enabled."
        ), 400

    platform = host(url)

    options = {
        "quiet": True,
        "no_warnings": True,

        "skip_download": True,

        "extract_flat": False,

        "noplaylist": False,

        "socket_timeout": 30,

        "retries": 2,
    }

    try:

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

        media = collect(info)

        videos = [
            item
            for item in media
            if item["type"] == "video"
        ]

        # --------------------------------
        # Extra fallback:
        # If yt-dlp returned a top-level
        # direct URL but classification
        # failed, inspect it again.
        # --------------------------------

        if not videos:

            direct_url = (
                info.get("url")
                if isinstance(info, dict)
                else None
            )

            if direct_url:

                fallback = {
                    "url": direct_url,
                    "ext": info.get("ext"),
                    "format_id": info.get(
                        "format_id"
                    ),
                    "mime_type": info.get(
                        "mime_type"
                    ),
                    "vcodec": info.get(
                        "vcodec"
                    ),
                    "acodec": info.get(
                        "acodec"
                    ),
                    "width": info.get(
                        "width"
                    ),
                    "height": info.get(
                        "height"
                    ),
                }

                if (
                    kind(fallback)
                    == "video"
                ):

                    videos.append(
                        {
                            "type": "video",
                            **fallback,
                        }
                    )

        if not videos:

            return jsonify(
                status="error",
                platform=platform,
                message=(
                    "No accessible video "
                    "media was returned "
                    "by yt-dlp."
                )
            ), 422

        # --------------------------------
        # Best video selection
        # --------------------------------

        def score(item):

            score_value = 0

            ext = (
                item.get("ext")
                or ""
            ).lower()

            media_url = (
                item.get("url")
                or ""
            ).lower()

            # MP4 preferred
            if ext == "mp4":
                score_value += 100

            # Direct file preferred
            if ".m3u8" not in media_url:
                score_value += 30

            # Higher resolution preferred
            height = item.get("height")

            if height:

                try:

                    score_value += min(
                        int(height),
                        2160
                    ) / 10

                except Exception:
                    pass

            return score_value

        videos.sort(
            key=score,
            reverse=True
        )

        best = videos[0]

        return jsonify(

            status="success",

            platform=platform,

            title=(
                info.get("title")
                or info.get("description")
                or "Video"
            ),

            media_type="video",

            download_url=best["url"],

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
            "Extraction failed"
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
