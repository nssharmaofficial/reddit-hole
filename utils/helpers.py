import os
import textwrap
from bs4 import BeautifulSoup
from markdown import markdown
import re
from PIL import Image, ImageDraw, ImageFont
from pydub import AudioSegment
from mutagen.mp3 import MP3
from tinydb import TinyDB
import toml
from typing import List
from dotenv import load_dotenv
from emoji import demojize


### Database and Configuration Functions ###

def load_database() -> TinyDB:
    """
    Loads the TinyDB database.

    Returns:
        TinyDB: The TinyDB instance connected to the database.
    """
    return TinyDB('./assets/database.json')


def load_config() -> dict:
    """
    Load configuration settings from a TOML and .env file.

    Returns:
        dict: A dictionary containing the configuration settings.
    """
    load_dotenv()

    config = toml.load('./assets/config.toml')

    # Replace placeholders with environment variables
    config['paths']['background'] = os.getenv('BACKGROUND')

    config['RedditCredential']['client_id'] = os.getenv('REDDIT_CLIENT_ID')
    config['RedditCredential']['client_secret'] = os.getenv('REDDIT_CLIENT_SECRET')
    config['RedditCredential']['username'] = os.getenv('REDDIT_USERNAME')
    config['RedditCredential']['passkey'] = os.getenv('REDDIT_PASSKEY')

    config['AmazonAWSCredential']['aws_access_key_id'] = os.getenv('AWS_ACCESS_KEY_ID')
    config['AmazonAWSCredential']['aws_secret_access_key'] = os.getenv('AWS_SECRET_ACCESS_KEY')
    config['AmazonAWSCredential']['region_name'] = os.getenv('AWS_REGION_NAME')

    return config


### Text Processing Functions ###

def sanitize_text(text: str) -> str:
    """
    Sanitizes the provided text by converting Markdown to plain text, removing age
    and gender indicators, cleaning unwanted characters, and eliminating URLs and emojis.

    Args:
        text (str): The input text to be sanitized, which may contain Markdown, age
        and gender indicators, URLs, and emojis.

    Returns:
        str: The sanitized text with Markdown converted to plain text, age and gender indicators removed,
              unwanted characters cleaned, URLs and emojis stripped, and extra whitespace condensed.
    """
    # Convert Markdown to HTML and then to plain text
    html = markdown(text)
    html = re.sub(r'<pre>(.*?)</pre>', ' ', html)
    html = re.sub(r'<code>(.*?)</code>', ' ', html)
    soup = BeautifulSoup(html, "html.parser")
    result = ''.join(soup.findAll(text=True))

    # Remove age and gender indicators
    result = re.sub(r'\(\d+\s?[MFmf]\)|\d+\s?[MFmf]', '', result)
    result = ' '.join(result.split())

    # Replace "/" with "or"
    result = re.sub(r'/', ' or', result)

    # Remove URLs
    result = re.sub(r"((http|https)\:\/\/)?[a-zA-Z0-9\.\/\?\:@\-_=#]+\.([a-zA-Z]){2,6}([a-zA-Z0-9\.\&\/\?\:@\-_=#])*", " ", result)

    # Remove specific unwanted characters and replace "+" and "&"
    result = re.sub(r"\s['|’]|['|’]\s|[\^_~@!&;#:\-%—“”‘\"%\*/{}\[\]\(\)\\|<>=+]", " ", result)
    result = result.replace("+", "plus").replace("&", "and")

    # Remove emojis
    result = demojize(result, delimiters=("", ""))

    # Remove extra whitespace
    return " ".join(result.split())


def split_text(text: str, max_length: int = 2000) -> List[str]:
    """
    Split the given text into chunks of a specified maximum length, ensuring that words are not broken.

    Args:
        text (str): The text to be split.
        max_length (int, optional): The maximum length of each chunk. Defaults to 2000.

    Returns:
        List[str]: A list of text chunks, each of which is no longer than the specified maximum length.
    """
    split_pattern = r'(.{1,' + str(max_length) + r'})(?:\s|$)'
    chunks = re.findall(split_pattern, text)
    return chunks


### Audio Processing Functions ###

def get_length(path: str) -> float:
    """
    Retrieves the length of an MP3 audio file in seconds.

    Args:
        path (str): The file path of the MP3 audio file.

    Returns:
        float: The length of the audio file in seconds, or None if an error occurs.

    Raises:
        Exception: If there is an error reading the audio file, the exception is printed.
    """
    try:
        # Load the MP3 file
        audio = MP3(path)
        # Get the length of the audio file in seconds
        length = audio.info.length
        return length
    except Exception as e:
        # Handle errors in reading the audio file
        print(f"Exception: {e}")
        return None


def add_pause(input_path: str, output_path: str, pause: int) -> None:
    """
    Adds a pause of specified duration to an MP3 file.

    Args:
        input_path (str): Path to the input MP3 file.
        output_path (str): Path to the output MP3 file.
        pause (int): Duration of the pause in milliseconds.
    """
    original_file = AudioSegment.from_mp3(input_path)
    silenced_file = AudioSegment.silent(duration=pause)
    combined_file = original_file + silenced_file

    # Export the combined file
    combined_file.export(output_path, format="mp3")


### Image Processing Functions ###

def getsize(font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
            text: str) -> tuple[int, int]:
    """
    Calculate the width and height of a given text string with the specified font.

    Args:
        font (ImageFont.ImageFont | ImageFont.FreeTypeFont): The font to use for 
        measuring the text.
        text (str): The text string to measure.

    Returns:
        tuple[int, int]: A tuple containing the width and height of the text.
    """
    left, top, right, bottom = font.getbbox(text)
    width = right - left
    height = bottom - top
    return width, height


def getheight(font: ImageFont.ImageFont | ImageFont.FreeTypeFont, text: str) -> int:
    """
    Calculate the height of a given text string with the specified font.

    Args:
        font (ImageFont.ImageFont | ImageFont.FreeTypeFont): The font to use for 
        measuring the text.
        text (str): The text string to measure.

    Returns:
        int: The height of the text.
    """
    _, height = getsize(font, text)
    return height


def create_fancy_title(image: Image.Image,
                       text: str,
                       text_color: str,
                       padding: int,
                       wrap: int = 35) -> Image.Image:
    """
    Create a fancy thumbnail image with wrapped text.

    Args:
        image (Image.Image): The background image for the thumbnail.
        text (str): The text to be added to the thumbnail.
        text_color (str): The color of the text.
        padding (int): The padding between lines of text.
        wrap (int, optional): The maximum number of characters per line. Defaults to 35.

    Returns:
        Image.Image: The modified image with the added text.
    """

    font_title_size = 47
    font = ImageFont.truetype(os.path.join("assets", "fonts", "Roboto-Bold.ttf"), font_title_size)
    _, image_height = image.size
    lines = textwrap.wrap(text, width=wrap)
    y = (
        (image_height / 2)
        - (((getheight(font, text) + (len(lines) * padding) / len(lines)) * len(lines)) / 2)
        + 30
    )
    draw = ImageDraw.Draw(image)

    if len(lines) == 3:
        lines = textwrap.wrap(text, width=wrap + 10)
        font_title_size = 40
        font = ImageFont.truetype(os.path.join("assets", "fonts", "Roboto-Bold.ttf"), font_title_size)
        y = (
            (image_height / 2)
            - (((getheight(font, text) + (len(lines) * padding) / len(lines)) * len(lines)) / 2)
            + 35
        )
    elif len(lines) == 4:
        lines = textwrap.wrap(text, width=wrap + 10)
        font_title_size = 35
        font = ImageFont.truetype(os.path.join("assets", "fonts", "Roboto-Bold.ttf"), font_title_size)
        y = (
            (image_height / 2)
            - (((getheight(font, text) + (len(lines) * padding) / len(lines)) * len(lines)) / 2)
            + 40
        )
    elif len(lines) > 4:
        lines = textwrap.wrap(text, width=wrap + 10)
        font_title_size = 30
        font = ImageFont.truetype(os.path.join("assets", "fonts", "Roboto-Bold.ttf"), font_title_size)
        y = (
            (image_height / 2)
            - (((getheight(font, text) + (len(lines) * padding) / len(lines)) * len(lines)) / 2)
            + 30
        )

    for line in lines:
        draw.text((120, y), line, font=font, fill=text_color, align="left")
        y += getheight(font, line) + padding

    return image


def convert_to_16_9(image: Image) -> Image:
    """
    Convert an image with a 9:16 aspect ratio to 16:9 by adding padding.

    Args:
        image (Image): The input image with a 9:16 aspect ratio.

    Returns:
        Image: The converted image with a 16:9 aspect ratio.
    """
    # Get the original dimensions
    original_width, original_height = image.size

    # Calculate the new dimensions for 16:9 aspect ratio
    new_width = int((original_height * 16) / 9)
    new_height = original_height

    # Create a new image with the desired aspect ratio and a black background
    new_img = Image.new("RGB", (new_width, new_height), color=(0, 0, 0))

    # Calculate the padding (centering the original image)
    padding_left = (new_width - original_width) // 2

    # Paste the original image onto the new image, centered
    new_img.paste(image, (padding_left, 0))

    return new_img


def zoom_image(image: Image, zoom_factor: float) -> Image:
    """
    Zoom in on an image and return the result.

    Args:
        image (Image): The input image object.
        zoom_factor (float): The zoom factor (e.g., 2 for 2x zoom).

    Returns:
        Image: The zoomed image.
    """
    # Get the dimensions of the original image
    width, height = image.size

    # Calculate the dimensions of the zoomed area
    zoomed_width = int(width / zoom_factor)
    zoomed_height = int(height / zoom_factor)

    # Calculate the coordinates for the crop box
    left = (width - zoomed_width) // 2
    top = (height - zoomed_height) // 2
    right = (width + zoomed_width) // 2
    bottom = (height + zoomed_height) // 2

    # Crop the image to the zoomed area
    zoomed_image = image.crop((left, top, right, bottom))

    # Resize the zoomed area back to the original image size
    zoomed_image = zoomed_image.resize((width, height), Image.LANCZOS)

    return zoomed_image


def create_thumbnail(image: Image) -> Image:
    """
    Convert an image to 16:9 and zoom in.

    Args:
        image (Image): The input image object.
    """
    image = convert_to_16_9(image)
    image = zoom_image(image, 3.5)
    return image