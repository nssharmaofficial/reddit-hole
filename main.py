import math
from pathlib import Path
from PIL import Image

from utils import reddit
from utils.tts import create_tts
from utils.helpers import (
    load_config,
    create_fancy_title,
    split_text,
    get_length,
    add_pause,
    create_thumbnail,
    sanitize_text
)
from utils.reddit import load_database
from utils.videomaker import make_final_video
import shutil


def main():
    """
    Main function to create a video from a Reddit thread's post
    or its comments, depending on storymode.
    """

    # Load configuration settings
    my_config = load_config()

    storymode = my_config['settings']['storymode']
    if storymode:
        print(f"Storymode is on for subreddit: {my_config['Reddit']['subreddit']}")
    elif not storymode:
        print(f"Comments mode is on for subreddit: {my_config['Reddit']['subreddit']}")

    # Log into Reddit
    my_reddit = reddit.login()

    # Get a Reddit thread
    thread = reddit.get_thread(reddit=my_reddit,
                               subreddit=my_config['Reddit']['subreddit'])
    if thread is None:
        print('No thread found! Exiting...')
        exit()

    # Create necessary directories
    Path("./assets/temp").mkdir(parents=True, exist_ok=True)
    thread_id_path = f"./assets/temp/{thread.id}"

    # Create directories for TTS files
    Path(f"{thread_id_path}/mp3").mkdir(parents=True, exist_ok=True)
    Path(f"{thread_id_path}/mp3_clean").mkdir(parents=True, exist_ok=True)
    Path(f"{thread_id_path}/png").mkdir(parents=True, exist_ok=True)

    # Convert thread title to TTS and save as MP3
    thread_title = sanitize_text(text=thread.title)
    title_audio_path = f'{thread_id_path}/mp3/title.mp3'
    title_audio_clean_path = f'{thread_id_path}/mp3_clean/title.mp3'
    create_tts(text=thread_title, path=title_audio_path)

    # Create fancy title
    title_template = Image.open("assets/my_title_template.png")
    title_img = create_fancy_title(image=title_template,
                                   text=thread_title,
                                   text_color="#000000",
                                   padding=5)
    title_image_path = f'{thread_id_path}/png/fancytitle.png'
    title_img.save(title_image_path)
    print("Saved: ", title_image_path)

    # Handle storymode
    if storymode:
        # Convert body to TTS and save as MP3
        thread_body = sanitize_text(thread.selftext)

        body_audio_paths = []
        if len(thread_body) >= 4000:
            print("Splitting too much big text...")
            thread_body_chunks = split_text(text=thread_body)
            for i, thread_body_chunk in enumerate(thread_body_chunks):
                body_audio_path = f'{thread_id_path}/mp3/body_{i}.mp3'
                body_audio_paths.append(body_audio_path)
                create_tts(text=thread_body_chunk, path=body_audio_path)
        elif len(thread_body) < 4000:
            print("Post too short. Exiting...")
            db = load_database()
            db.insert({'id': thread.id, 'title': thread.title})
            db.close()
            exit()

        # Get the duration of the title TTS
        total_video_duration = 0
        pause = my_config['settings']['pause']
        tts_title_path = f'{thread_id_path}/mp3/title.mp3'
        title_duration = get_length(path=tts_title_path)
        total_video_duration += title_duration + pause

        # Get the duration of the body TTS
        for body_audio_path in body_audio_paths:
            body_duration = get_length(path=body_audio_path)
            total_video_duration += body_duration

        # Convert the pause (in seconds) into milliseconds
        mp3_pause = pause * 1000
        add_pause(title_audio_path, title_audio_clean_path, mp3_pause)

        # Create the final video
        final_folder_path = f"./results/long/{thread_title}/"
        Path(final_folder_path).mkdir(parents=True, exist_ok=True)

        # Create thumbnail from fancy title
        thumbnail = create_thumbnail(image=title_img)
        thumbnail_image_path = f'{final_folder_path}/thumbnail.png'
        thumbnail.save(thumbnail_image_path)
        print("Saved: ", thumbnail_image_path)

        make_final_video(
            title_audio_path=title_audio_clean_path,
            title_image_path=title_image_path,
            thread_title=thread_title,
            length=math.ceil(total_video_duration),
            body_audio_paths=body_audio_paths,
        )

    elif not storymode:
        # Get comments from the thread
        comments = reddit.get_comments(thread=thread)
        if comments is None:
            print('No comments found! Exiting...')
            exit()

        # Download screenshots of Reddit post and its comments
        reddit.get_screenshots_of_reddit_posts(reddit_thread=thread,
                                               reddit_comments=comments)

        # Convert each comment to TTS and save as MP3
        for idx, comment in enumerate(comments):
            path = f"{thread_id_path}/mp3/{idx}.mp3"
            create_tts(text=comment.body, path=path)

        # Calculate the total video duration and add pauses
        total_video_duration = my_config['settings']['total_video_duration']
        pause = my_config['settings']['pause']
        current_video_duration = 0

        # Get the duration of the title TTS
        tts_title_path = f'{thread_id_path}/mp3/title.mp3'
        title_duration = get_length(path=tts_title_path)
        current_video_duration += title_duration + pause

        # Prepare lists for comments' audio and image paths
        comments_audio_path = []
        comments_audio_clean_path = []
        comments_image_path = []

        # Add comments to the video if their duration fits within the total video duration
        for idx, comment in enumerate(comments):
            comment_audio_path = f'{thread_id_path}/mp3/{idx}.mp3'
            comment_audio_clean_path = f'{thread_id_path}/mp3_clean/{idx}.mp3'
            comment_image_path = f'{thread_id_path}/png/{idx}.png'
            comment_duration = get_length(comment_audio_path)

            if current_video_duration + comment_duration + pause <= total_video_duration:
                comments_audio_path.append(comment_audio_path)
                comments_audio_clean_path.append(comment_audio_clean_path)
                comments_image_path.append(comment_image_path)
                current_video_duration += comment_duration + pause

        # Convert the pause duration from seconds to milliseconds
        mp3_pause = pause * 1000
        add_pause(title_audio_path, title_audio_clean_path, mp3_pause)

        # Add pauses to each comment audio
        for input_path, output_path in zip(comments_audio_path, comments_audio_clean_path):
            add_pause(input_path, output_path, mp3_pause)

        # Create the final video
        final_folder_path = f"./results/short/"
        Path(final_folder_path).mkdir(parents=True, exist_ok=True)

        make_final_video(
            title_audio_path=title_audio_clean_path,
            title_image_path=title_image_path,
            thread_title=thread_title,
            length=math.ceil(total_video_duration),
            comments_audio_path=comments_audio_clean_path,
            comments_image_paths=comments_image_path
        )

    # Insert the thread ID and title into the database
    db = load_database()
    db.insert({'id': thread.id, 'title': thread.title})
    db.close()

    # Remove the temporary directory at the end
    shutil.rmtree("./assets/temp")

    print("Done! See result in the results folder!")

if __name__ == '__main__':
    main()
