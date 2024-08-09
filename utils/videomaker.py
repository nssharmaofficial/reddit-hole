import multiprocessing
import random

from moviepy.audio.AudioClip import concatenate_audioclips, CompositeAudioClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy.config import change_settings
from moviepy.editor import (
    CompositeVideoClip,
    TextClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips
)
from moviepy.video.fx.resize import resize
from moviepy.video.fx.crop import crop
from typing import List, Optional
import re

from utils.captions import transcribe_audio_with_whisper, format_captions_whisper
from utils.helpers import load_config


def prepare_background(length: int, W: int, H: int) -> CompositeVideoClip:
    """
    Prepares the background video clip for the final video.

    Args:s
        length (int): The length of the video in seconds.
        W (int): The width of the video.
        H (int): The height of the video.

    Returns:
        CompositeVideoClip: The prepared background video clip.
    """
    my_config = load_config()

    # Load the background video
    video = VideoFileClip(my_config['paths']['background']).without_audio()
    video_duration = video.duration

    # Select a random start time within the background video
    random_start = random.randint(0, int(video_duration - length))
    vid = video.subclip(random_start, random_start + length)
    video.close()

    # Resize and crop the video
    vid_resized = resize(vid, height=H)
    center = vid_resized.w // 2
    half_w = W // 2
    x1 = center - half_w
    x2 = center + half_w

    return crop(vid_resized, x1=x1, y1=0, x2=x2, y2=H)


def make_final_video(
    title_audio_path: str,
    title_image_path: str,
    thread_title: str,
    length: int,
    body_audio_paths: Optional[List[str]] = None,
    comments_audio_path: Optional[List[str]] = None,
    comments_image_paths: Optional[List[str]] = None
):
    """
    Creates the final video by combining the background, title, and body text or comments with captions.

    Args:
        title_audio_path (str): The file path of the title audio.
        title_image_path (str): The file path of the title image.
        thread_title (str): The title of the Reddit thread.
        length (int): The length of the video in seconds.
        body_audio_paths (Optional[List[str]]): The file paths of the body audio (for story mode).
        comments_audio_path (Optional[List[str]]): The list of file paths forcomments audio (for comments mode).
        comments_image_paths (Optional[List[str]]): The list of file paths for comments images (for comments mode).
    """

    print("Creating the final video")

    my_config = load_config()
    storymode = my_config['settings']['storymode']

    # Set video dimensions and opacity
    if storymode:
        W = my_config["settings"]["resolution_w"]
        H = my_config["settings"]["resolution_h"]
    else:
        W = my_config["settings"]["resolution_h"]
        H = my_config["settings"]["resolution_w"]
    opacity = my_config["settings"]["opacity"] or 1.0

    # Prepare the background clip
    background_clip = prepare_background(length, W, H)

    # Gather all audio clips, starting with the title audio
    audio_clips = [AudioFileClip(title_audio_path)]
    if storymode and body_audio_paths:
        audio_clips.extend(AudioFileClip(path) for path in body_audio_paths)
    elif not storymode and comments_audio_path:
        audio_clips.extend(AudioFileClip(path) for path in comments_audio_path)

    # Concatenate all audio clips into a single audio track
    audio_concat = concatenate_audioclips(audio_clips)
    audio_composite = CompositeAudioClip([audio_concat])

    if storymode and body_audio_paths:
        # Transcribe audio and generate captions for story mode
        all_captions = []
        total_duration = 0.0
        for i, body_audio_path in enumerate(body_audio_paths, start=1):
            segments = transcribe_audio_with_whisper(audio_path=body_audio_path)
            captions = format_captions_whisper(segments=segments)
            for start, end, text in captions:
                all_captions.append((start + total_duration, end + total_duration, text))
            total_duration += audio_clips[i].duration

        # Create the title image clip
        title_clip = (ImageClip(title_image_path)
                      .set_duration(audio_clips[0].duration)
                      .set_opacity(opacity)
                      .set_position("center"))

        # Create text clips for subtitles
        text_clips = []
        for start, end, text in all_captions:
            text_clip = (TextClip(txt=text,
                                  font='Ubuntu-Mono-Bold',
                                  fontsize=70,
                                  color='white',
                                  bg_color='transparent',
                                  size=(W, H),
                                  method='caption',
                                  stroke_width=2,
                                  stroke_color='orange')
                        .set_position(('center', 'center'))
                        .set_duration(end - start)
                        .set_start(start))
            text_clips.append(text_clip)

        text_concat = concatenate_videoclips(text_clips)
        final_video = CompositeVideoClip([background_clip,
                                          title_clip.set_start(0),
                                          text_concat.set_start(audio_clips[0].duration)])

    elif not storymode and comments_audio_path and comments_image_paths:
        # Initialize the list to hold all image clips
        image_clips = []

        # Calculate screenshot width based on video width
        screenshot_width = int((W * 90) // 100)

        # Create the title image clip and add to the list
        title_clip = (ImageClip(title_image_path)
                      .set_duration(audio_clips[0].duration)
                      .set_opacity(opacity)
                      .set_position("center"))
        resized_title_clip = resize(title_clip, width=screenshot_width)
        image_clips.append(resized_title_clip)

        # Create image clips for each comment and add to the list
        for idx, path in enumerate(comments_image_paths):
            comment_clip = (ImageClip(path)
                            .set_duration(audio_clips[idx + 1].duration)
                            .set_opacity(opacity)
                            .set_position("center"))
            resized_comment_clip = resize(comment_clip, width=screenshot_width)
            image_clips.append(resized_comment_clip)

        # Concatenate all image clips into a single video track
        image_concat = concatenate_videoclips(image_clips)
        final_video = CompositeVideoClip([background_clip, image_concat.set_position("center")])

    # Add the audio to the final video
    final_video = final_video.set_audio(audio_composite)

    # Write the final video file
    thread_title = re.sub(r'\?', '', thread_title)
    if storymode:
        output_path = f"./results/long/{thread_title}/{my_config['Reddit']['subreddit']} - {thread_title}.mp4"
    else:
        output_path = f"./results/short/{my_config['Reddit']['subreddit']} - {thread_title}.mp4"
    final_video.write_videofile(
        output_path,
        fps=24,
        audio_codec="aac",
        audio_bitrate="192k",
        threads=multiprocessing.cpu_count(),
    )

    # Close all clips to free up resources
    audio_composite.close()
    final_video.close()
