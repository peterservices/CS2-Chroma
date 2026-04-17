from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as WindowsMediaManager,
)
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackState,
)


async def stop_playback():
    """
    Stop playing media if it is currently playing.
    """

    sessions = await WindowsMediaManager.request_async()

    current_session = sessions.get_current_session()

    if current_session is not None and current_session.get_playback_info().playback_status == PlaybackState.PLAYING:
        await current_session.try_toggle_play_pause_async()

async def start_playback():
    """
    Start playing media if it is currently paused.
    """

    sessions = await WindowsMediaManager.request_async()

    current_session = sessions.get_current_session()

    if current_session is not None and current_session.get_playback_info().playback_status == PlaybackState.PAUSED:
        await current_session.try_toggle_play_pause_async()

# By @peterservices
