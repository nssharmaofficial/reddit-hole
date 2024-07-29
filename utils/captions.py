import whisper
from typing import List, Tuple


def transcribe_audio_with_whisper(audio_path: str) -> List[dict]:
    """
    Transcribe audio using the Whisper model.

    Args:
        audio_path (str): The path to the audio file to be transcribed.

    Returns:
        List[dict]: A list of segments containing the transcription results. 
                    Each segment is a dictionary with 'start', 'end', and 'text' keys.
    """
    model = whisper.load_model("medium")
    result = model.transcribe(audio_path)
    return result['segments']


def format_captions_whisper(segments: List[dict]) -> List[Tuple[float, float, str]]:
    """
    Format the transcribed segments into captions.

    Args:
        segments (List[dict]): A list of transcription segments where each segment 
                               is a dictionary with 'start', 'end', and 'text' keys.

    Returns:
        List[Tuple[float, float, str]]: A list of tuples, each containing the start time, 
                                        end time, and text of a caption.
    """
    captions = []
    for segment in segments:
        start = segment['start']
        end = segment['end']
        text = segment['text'].strip()
        captions.append((start, end, text))
    return captions