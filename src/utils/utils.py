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
    
    1. Professionalism (Score 1-10):
       - Evaluate the overall professionalism of the speakers
       - Consider language formality, respect, and business etiquette
    
    2. Tone Analysis (Score 1-10 for each tone):
        - Identify the dominant tones used (formal, friendly, urgent, frustrated, etc.)
        - Assign a score (1-10) to each tone detected, instead of percentages
        - Explain how each tone was identified and its impact on the conversation
    
    3. Context Awareness & Active Listening (Score 1-10):
       - Evaluate how well speakers understand and respond to context
       - Assess if speakers acknowledge and build upon previous statements
    
    4. Response Time Analysis:
       - Analyze pauses and response times between speakers
       - Note any particularly long delays and their impact
    
    5. Fluency vs. Fumbling (Score 1-10):
       - Rate the overall verbal fluency of each speaker
       - Identify hesitations, filler words, or unclear statements
    
    6. Probing Effectiveness (Score 1-10):
       - Evaluate how effectively questions elicit useful information
       - Assess the quality and relevance of follow-up questions
    
    7. Call Closing Quality (Score 1-10):
       - Analyze how effectively the call was concluded
       - Evaluate clarity on next steps (if applicable)
    
    8. Script Adherence (if applicable):
       - Determine if the call followed a standard script or protocol
       - Identify deviations from expected conversation flow
    
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
            "professionalism_score": extract_score(response_text, "Professionalism", 7),
            "tone_analysis": extract_tone_percentages(response_text),
            "context_awareness_score": extract_score(response_text, "Context Awareness", 6),
            "response_time_analysis": {
                "description": extract_section(response_text, "Response Time Analysis")
            },
            "fluency_score": extract_score(response_text, "Fluency", 5),
            "probing_effectiveness": extract_score(response_text, "Probing Effectiveness", 4),
            "call_closing_quality": extract_score(response_text, "Call Closing", 6),
            "script_adherence": {
                "description": extract_section(response_text, "Script Adherence")
            },
            "summary": extract_section(response_text, "summary") or 
                       extract_section(response_text, "overall") or
                       "Analysis complete but no summary provided"
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
    pattern = rf"{category}.*?(\d+)[\s/]10"
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