from modules.subtitle_clipper import create_shorts_from_srt

# Example usage
if __name__ == "__main__":
    # Paths
    video_path = "output/test_with_subs.mp4"
    srt_path = "subtitles/test.srt"
    output_dir = "output/shorts"

    # Keywords to look for in subtitles
    keywords = [
        "funny", "lol", "crazy", "omg", "joke", "laugh",
        "busted", "i'm dead", "what", "insane", "wow",
        "amazing", "unbelievable", "holy", "damn"
    ]

    # Create shorts
    clip_paths = create_shorts_from_srt(
        video_path=video_path,
        srt_path=srt_path,
        keywords=keywords,
        output_dir=output_dir,
        min_duration=15,
        max_duration=20
    )

    print(f"Created {len(clip_paths)} shorts:")
    for path in clip_paths:
        print(f"- {path}") 