
from boto3 import Session
from botocore.exceptions import BotoCoreError, ClientError
from contextlib import closing
import sys
from utils.helpers import load_config
import random


def create_session() -> Session:
    """
    Creates and returns a Boto3 session using AWS credentials from the configuration file.

    Returns:
        Session: The Boto3 session.

    Raises:
        Exception: If the session creation fails, the exception is raised.
    """
    # Load configuration settings
    my_config = load_config()

    # Create a Boto3 session using the AWS credentials from the configuration
    session = Session(
        aws_access_key_id=my_config['AmazonAWSCredential']['aws_access_key_id'],
        aws_secret_access_key=my_config['AmazonAWSCredential']['aws_secret_access_key'],
        region_name=my_config['AmazonAWSCredential']['region_name']
    )
    return session


def create_tts(text: str, path: str):
    """
    Creates a Text-to-Speech (TTS) audio file using AWS Polly and saves it to the specified path.

    Args:
        text (str): The text to be converted to speech.
        path (str): The file path to save the generated audio file.

    Raises:
        SystemExit: If there is an error during TTS creation or file writing, the program exits.
    """
    # Load configuration settings
    my_config = load_config()

    # Create a Boto3 session and Polly client
    session = create_session()
    polly = session.client("polly")

    try:
        # Select the voice ID for TTS
        voice_id = my_config['settings']['voice_id']
        if my_config['settings']['multiple_voices']:
            voices = ["Joanna", "Justin", "Kendra", "Matthew"]
            voice_id = random.choice(voices)

        # Request TTS from Polly
        response = polly.synthesize_speech(
            Text=text,
            OutputFormat="mp3",
            VoiceId=voice_id,
            Engine="neural"
        )
    except (BotoCoreError, ClientError) as error:
        # Handle errors from Boto3 or AWS Polly
        print(error)
        sys.exit(-1)

    # Check if the response contains an audio stream
    if "AudioStream" in response:
        with closing(response["AudioStream"]) as stream:
            try:
                # Write the audio stream to the specified file path
                with open(path, "wb") as file:
                    file.write(stream.read())
                print("Saved: ", path)
            except IOError as error:
                # Handle file writing errors
                print(error)
                sys.exit(-1)
    else:
        # Handle the case where no audio data is returned
        print("Could not stream audio")
        sys.exit(-1)

