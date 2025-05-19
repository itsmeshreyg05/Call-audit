import re
import json
from typing import Dict, List, Any, Optional
from src.schemas import DiarizationSegment

def format_conversation(segments: List[Any]) -> str:
    """
    Format the diarization segments into a clean conversation transcript.
    Handles both DiarizationSegment objects and dictionary formats.
    """
    formatted_text = ""
    
    for segment in segments:
        # Handle DiarizationSegment objects
        if isinstance(segment, DiarizationSegment):
            speaker = segment.speaker
            text = segment.text if segment.text else ""
        # Handle dictionary format
        elif isinstance(segment, dict):
            speaker = segment.get("speaker", "Unknown")
            text = segment.get("text", "").strip()
        else:
            continue
            
        if text:  # Only include segments with actual text
            formatted_text += f"{speaker}: {text}\n"
    
    return formatted_text

def create_mistral_prompt(conversation_text: str) -> str:
    """
    Create a detailed prompt for the Mistral model to analyze the conversation
    """
    prompt = f"""
    You are an expert conversation analyst. Analyze the following call transcript 
    between two speakers and provide detailed insights.
    
    CONVERSATION TRANSCRIPT:
    {conversation_text}
    
    Please analyze this conversation across the following dimensions:
    
    1. Introduction/Hook (Score 1-100):
       - Was the introduction clear, confident, and engaging?

    2. Script Adherence (Score 1-100):
       - Did the speaker follow the script or expected conversation flow?
       - Mention any deviations.

    3. Product Knowledge (Score 1-100):
       - How well does the speaker demonstrate understanding of the product/service?

    4. Actively Listening/Responding Appropriately (Score 1-100):
       - Evaluate how well the speaker listens and tailors responses.

    5. Fumble Score (Score 1-100):
       - Identify unclear statements, fillers, hesitations.
       - Lower score means more fumbling.

    6. Probing (Score 1-100):
       - Were the questions relevant and useful?
       - How deep were the follow-ups?

    7. Closing (Score 1-100):
       - Was the call concluded confidently and with clarity?

    8. Overall Score (Score 1-100):
       - General effectiveness and communication throughout the call.
    
       
    
    Provide your analysis in JSON format with scores, percentages, and brief explanations for each dimension.
    Include a short summary of the overall conversation quality and key observations.
    """
    return prompt

def parse_mistral_response(response_text: str) -> Dict[str, Any]:
    """
    Parse the raw text response from Mistral into structured analysis
    """
    try:
        # First try to extract any JSON content from the response
        # Look for JSON-like structure between curly braces
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        
        if json_match:
            json_str = json_match.group(0)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass  # If direct JSON parsing fails, fallback to structured extraction
        
        # Fallback: Extract information in a structured way
        analysis = {
    "introduction_score": extract_score(response_text, "Introduction"),
    "script_adherence_score": extract_score(response_text, "Script Adherence"),
    "product_knowledge": extract_score(response_text, "Product Knowledge"),
    "active_listening": extract_score(response_text, "Actively Listening"),
    "fumble_score": extract_score(response_text, "Fumble"),
    "probing_score": extract_score(response_text, "Probing"),
    "closing_score": extract_score(response_text, "Closing"),
    "overall_score": extract_score(response_text, "Overall Score"),
    "summary": extract_section(response_text, "Summary") or 
               extract_section(response_text, "Overall") or
               "Analysis complete but no summary provided."
}
        
        return analysis
    
    except Exception as e:
        # If parsing fails, return a simplified analysis
        return {
            "raw_analysis": response_text,
            "parsing_error": str(e),
            "summary": "Could not parse structured analysis from model output"
        }

def extract_score(text: str, category: str, default: int) -> int:
    """
    Extract numerical score for a category from text
    """
    pattern = rf"{category}.*?(\d+)[\s/]100"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return default

def extract_tone_percentages(text: str) -> Dict[str, float]:
    """
    Extract tone percentages from analysis text
    """
    tones = {}
    
    # Look for patterns like "formal: 70%" or "formal (70%)"
    tone_matches = re.finditer(r'(\w+)(?:\s*:\s*|\s*\()(\d+)%', text, re.IGNORECASE)
    
    for match in tone_matches:
        tone = match.group(1).lower()
        try:
            percentage = float(match.group(2)) / 100.0
            tones[tone] = percentage
        except ValueError:
            continue
    
    # If no tones found, provide default analysis
    if not tones:
        # Extract the tone analysis section
        tone_section = extract_section(text, "Tone Analysis")
        if tone_section:
            # Add some default tones based on keywords in the section
            keywords = {
                "formal": ["formal", "professional", "business"],
                "friendly": ["friendly", "warm", "casual"],
                "urgent": ["urgent", "pressing", "immediate"],
                "frustrated": ["frustrated", "annoyed", "impatient"],
                "neutral": ["neutral", "balanced", "even"]
            }
            
            for tone, words in keywords.items():
                # Count occurrences of keywords
                count = sum(1 for word in words if word.lower() in tone_section.lower())
                if count > 0:
                    tones[tone] = min(count * 0.2, 1.0)  # Scale up to 100% max
    
    # If still no tones, add a default tone
    if not tones:
        tones = {"neutral": 0.7, "formal": 0.5}
    
    return tones

def extract_section(text: str, section_name: str) -> Optional[str]:
    """
    Extract a specific section from the analysis text
    """
    pattern = rf"{section_name}.*?:(.*?)(?=\d+\.|$|\n\s*\n)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return None