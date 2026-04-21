from backend.app.youtube import extract_video_id, is_youtube_url


def test_extract_video_id_from_watch_url():
    assert extract_video_id("https://www.youtube.com/watch?v=abcdefghijk&t=12s") == "abcdefghijk"


def test_extract_video_id_from_shorts_url():
    assert extract_video_id("https://youtube.com/shorts/abcdefghijk?feature=share") == "abcdefghijk"


def test_rejects_playlist_only_url():
    assert not is_youtube_url("https://www.youtube.com/playlist?list=123")

