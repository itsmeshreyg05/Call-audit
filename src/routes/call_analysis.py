import json
import re
import ollama
from typing import Dict, List, Any
from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from google_sheets_helper import append_dict_to_sheet 
from src.database.database import get_db
from src.models.model import Audio, Analysis, Segment
from src.schemas.schema import CallAnalysisResult, DiarizationSegment
from src.routes.audio import diarize_audio
 
# Create a router
router = APIRouter(
    prefix="/call-analysis",
    tags=["call analysis"],
    responses={404: {"description": "Not found"}},
)
 
# Configure Ollama settings
MISTRAL_MODEL = "mistral"  # Use the model name as configured in Ollama
 
@router.post("/", response_model=CallAnalysisResult)
async def analyze_call(audio_id: str = Header(..., description="Audio ID to analyze"), db: Session = Depends(get_db)):
    """
    Analyze a transcribed call using Ollama's Mistral model
   
    Pass the audio_id in the request header. The segments will be retrieved from the database.
    """
    # Validate that the audio_id exists in the database
    db_audio = db.query(Audio).filter(Audio.id == audio_id).first()
    if not db_audio:
        raise HTTPException(status_code=404, detail="Audio ID not found")
   
    # Check if the audio has been processed already
    if not db_audio.processed:
        # If not processed, try to diarize it first
        diarization_result = await diarize_audio(audio_id, db)
       
        # Check if diarization was successful
        if diarization_result.status.startswith("failed"):
            raise HTTPException(
                status_code=400,
                detail=f"Failed to diarize audio: {diarization_result.status}"
            )
   
    # Get segments from the database
    db_segments = db.query(Segment).filter(Segment.audio_id == audio_id).all()
   
    # If no segments found or empty
    if not db_segments:
        raise HTTPException(
            status_code=400,
            detail="No transcribed segments found for this audio. Please diarize the audio first."
        )
   
    # Convert DB segments to schema segments
    segments = [
        DiarizationSegment(
            speaker=segment.speaker,
            start=segment.start,
            end=segment.end,
            text=segment.text
        ) for segment in db_segments
    ]
   
    # Format the conversation for analysis
    conversation_text = format_conversation(segments)
   
    # Create the prompt for Mistral
    prompt = create_mistral_prompt(conversation_text)
   
    # Call Ollama Python library with Mistral model
    try:
        analysis_result = query_ollama_mistral(prompt, MISTRAL_MODEL)
    except Exception as e:
        return CallAnalysisResult(
            audio_id=audio_id,
            analysis={"error": str(e)},
            status="failed"
        )
   
    # Parse the analysis results
    parsed_analysis = parse_mistral_response(analysis_result)
   
    # Store analysis in database
    db_analysis = db.query(Analysis).filter(Analysis.audio_id == audio_id).first()
   
    if db_analysis:
        # Update existing analysis
        for key, value in parsed_analysis.items():
            setattr(db_analysis, key, value)
        db_analysis.status = "completed"
        # Add call outcome information
        db_analysis.outcome_category = parsed_analysis.get("call_outcome", {}).get("outcome_category", "Unknown")
        db_analysis.outcome_phrases = parsed_analysis.get("call_outcome", {}).get("supporting_phrases", [])
        db_analysis.outcome_explanation = parsed_analysis.get("call_outcome", {}).get("explanation", "")
    else:
        # Create new analysis
        db_analysis = Analysis(
            audio_id=audio_id,
            professionalism_score=parsed_analysis.get("professionalism_score", 0),
            tone_analysis=parsed_analysis.get("tone_analysis", {}),
            context_awareness_score=parsed_analysis.get("context_awareness_score", 0),
            response_time_analysis=parsed_analysis.get("response_time_analysis", {}),
            fluency_score=parsed_analysis.get("fluency_score", 0),
            probing_effectiveness=parsed_analysis.get("probing_effectiveness", 0),
            call_closing_quality=parsed_analysis.get("call_closing_quality", 0),
            summary=parsed_analysis.get("summary", ""),
            # Add call outcome information
            outcome_category=parsed_analysis.get("call_outcome", {}).get("outcome_category", "Unknown"),
            outcome_phrases=parsed_analysis.get("call_outcome", {}).get("supporting_phrases", []),
            outcome_explanation=parsed_analysis.get("call_outcome", {}).get("explanation", ""),
            status="completed"
        )
        db.add(db_analysis)
   
    db.commit()
    row_data = {
    # "Call Date & Time": getattr(db_audio, "uploaded_at", ""),

    "audio_id" :getattr(db_audio, "id", ""),
    "Introduction/Hook": f"{parsed_analysis.get('introduction_score', 0)}%",
    "Adherence to script/Product Knowledge": f"{parsed_analysis.get('script_knowledge_score', 0)}%",
    "Actively listening/ Responding Appropriately": f"{parsed_analysis.get('listening_score', 0)}%",
    "Fumble": f"{parsed_analysis.get('fumble_score', 0)}%",
    "Probing": f"{parsed_analysis.get('probing_effectiveness', 0)}%",
    "Closing": f"{parsed_analysis.get('call_closing_quality', 0)}%",
    "Overall Score": f"{parsed_analysis.get('overall_score', 0)}%",
    "Summary": parsed_analysis.get("summary", ""),
    "Remarks": parsed_analysis.get("call_outcome", {}).get("outcome_category", "Unknown"), 
    "Reason": parsed_analysis.get("call_outcome", {}).get("explanation", "")}

# Append it to the Google Sheet
    append_dict_to_sheet(row_data)
   
    return CallAnalysisResult(
        audio_id=audio_id,
        analysis=parsed_analysis,
        status="completed"
    )
 

def format_conversation(segments: List[DiarizationSegment]) -> str:
    """
    Format the diarization segments into a clean conversation transcript.
    """
    formatted_text = ""
   
    for segment in segments:
        text = segment.text if segment.text else ""
        if text:  # Only include segments with actual text
            formatted_text += f"{segment.speaker}: {text}\n"
   
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
       - IMPORTANT: Provide a 1-2 sentence explanation for your score
   
    2. Tone Analysis:
        - Identify the dominant tones used (formal, friendly, urgent, frustrated, etc.)
        - Assign a score (1-10) to each tone detected
        - IMPORTANT: For each tone, provide a 1-2 sentence explanation of how it manifested in the conversation
   
    3. Context Awareness & Active Listening (Score 1-10):
       - Evaluate how well speakers understand and respond to context
       - Assess if speakers acknowledge and build upon previous statements
       - IMPORTANT: Provide a 1-2 sentence explanation for your score
   
    4. Response Time Analysis:
       - Analyze pauses and response times between speakers
       - Note any particularly long delays and their impact
       - IMPORTANT: Provide a clear explanation of your observations
   
    5. Fluency vs. Fumbling (Score 1-10):
       - Rate the overall verbal fluency of each speaker
       - Identify hesitations, filler words, or unclear statements
       - IMPORTANT: Provide a 1-2 sentence explanation for your score
   
    6. Probing Effectiveness (Score 1-10):
       - Evaluate how effectively questions elicit useful information
       - Assess the quality and relevance of follow-up questions
       - IMPORTANT: Provide a 1-2 sentence explanation for your score
   
    7. Call Closing Quality (Score 1-10):
       - Analyze how effectively the call was concluded
       - Evaluate clarity on next steps (if applicable)
       - IMPORTANT: Provide a 1-2 sentence explanation for your score
       
    8. Call Outcome Classification:
       - Classify the call outcome based on the final conversation exchanges
       - Specifically identify if the person expressed disinterest with phrases like "I'm not interested", "Not for me", etc.
       - If disinterest was expressed, note the exact phrases used
       - Provide the appropriate outcome category: "Agreed for the meeting", "Disconnected the call", "Call back requested", "Not interested", etc.
       - IMPORTANT: Provide specific phrases that indicated the outcome
   
    Provide your analysis in JSON format with scores and explanations for each dimension.
    Include a short summary of the overall conversation quality and key observations.
    
    Format each category to include both a numeric score AND an explanation field.
    For the Call Outcome Classification, include "outcome_category" and "supporting_phrases" fields.
    
    Example for one category:
    {{
      "professionalism_score": 7,
      "professionalism_explanation": "Both speakers maintained professional language but occasionally used casual expressions.",
      ...
      "call_outcome": {{
        "outcome_category": "Not interested",
        "supporting_phrases": ["I'm not interested right now", "This doesn't work for me"],
        "explanation": "The prospect clearly expressed disinterest multiple times during the call closing."
      }}
    }}
    """
    return prompt
 

def query_ollama_mistral(prompt: str, model: str) -> str:
    """
    Send a prompt to Ollama using the Python library
    """
    try:
        # Create the message structure for Ollama
        response = ollama.chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert conversation analyst."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            options={
                "temperature": 0.1,
                "num_predict": 4000
            }
        )
       
        # Extract the response content from the Ollama response structure
        if response and "message" in response and "content" in response["message"]:
            return response["message"]["content"]
        else:
            raise Exception("No content in response from Ollama")
           
    except Exception as e:
        raise Exception(f"Error communicating with Ollama library: {str(e)}")
 
def parse_mistral_response(response_text: str) -> Dict[str, Any]:
    """
    Parse the raw text response from Mistral into structured analysis with explanations
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
        professionalism_score = extract_score(response_text, "Professionalism", 7)
        professionalism_explanation = extract_explanation(response_text, "Professionalism")
        
        context_awareness_score = extract_score(response_text, "Context Awareness", 6)
        context_awareness_explanation = extract_explanation(response_text, "Context Awareness")
        
        fluency_score = extract_score(response_text, "Fluency", 5)
        fluency_explanation = extract_explanation(response_text, "Fluency")
        
        probing_effectiveness_score = extract_score(response_text, "Probing Effectiveness", 4)
        probing_explanation = extract_explanation(response_text, "Probing Effectiveness")
        
        call_closing_score = extract_score(response_text, "Call Closing", 6)
        call_closing_explanation = extract_explanation(response_text, "Call Closing")
        
        # Extract tone information with explanations
        tone_analysis = extract_tone_with_explanations(response_text)
        
        # Response time analysis
        response_time_description = extract_section(response_text, "Response Time Analysis")
        
        # Extract call outcome classification
        outcome_category = "Unknown"
        supporting_phrases = []
        outcome_explanation = ""
        
        # Look for outcome classification in the response
        outcome_section = extract_section(response_text, "Call Outcome") or extract_section(response_text, "Outcome Classification")
        if outcome_section:
            # Try to find the outcome category
            category_match = re.search(r'category[\s:]+["\'"]?([^"\'"\n]+)["\'"]?', outcome_section, re.IGNORECASE)
            if category_match:
                outcome_category = category_match.group(1).strip()
            
            # Try to find supporting phrases
            phrases_match = re.findall(r'["\'"]([^"\'"\n]{5,})["\'"]', outcome_section)
            if phrases_match:
                supporting_phrases = [phrase.strip() for phrase in phrases_match]
            
            # Get explanation
            outcome_explanation = re.sub(r'category[\s:]+["\'"]?[^"\'"\n]+["\'"]?', '', outcome_section)
            outcome_explanation = re.sub(r'phrases[\s:]+[\[\{].*?[\]\}]', '', outcome_explanation, flags=re.DOTALL)
            outcome_explanation = outcome_explanation.strip()
        
        # Summary
        summary = extract_section(response_text, "summary") or \
                 extract_section(response_text, "overall") or \
                 "Analysis complete but no summary provided"
        
        analysis = {
            "professionalism_score": professionalism_score,
            "professionalism_explanation": professionalism_explanation,
            
            "tone_analysis": tone_analysis,
            
            "context_awareness_score": context_awareness_score,
            "context_awareness_explanation": context_awareness_explanation,
            
            "response_time_analysis": {
                "description": response_time_description
            },
            
            "fluency_score": fluency_score,
            "fluency_explanation": fluency_explanation,
            
            "probing_effectiveness": probing_effectiveness_score,
            "probing_explanation": probing_explanation,
            
            "call_closing_quality": call_closing_score,
            "call_closing_explanation": call_closing_explanation,
            
            # Add call outcome information
            "call_outcome": {
                "outcome_category": outcome_category,
                "supporting_phrases": supporting_phrases,
                "explanation": outcome_explanation
            },
            
            "summary": summary
        }
        
        return analysis
    
    except Exception as e:
        # If parsing fails, return a simplified analysis
        return {
            "raw_analysis": response_text,
            "parsing_error": str(e),
            "summary": "Could not parse structured analysis from model output"
        }

def extract_explanation(text: str, category: str) -> str:
    """
    Extract explanation for a specific category
    """
    # Try to find explanations following the score mention
    score_match = re.search(rf"{category}.*?(\d+)[\s/]10(.*?)(?=\d+\.|$|\n\s*\n)", text, re.IGNORECASE | re.DOTALL)
    if score_match:
        explanation = score_match.group(2).strip()
        # Clean up the explanation (remove bullet points, etc.)
        explanation = re.sub(r'^[-:•*]+\s*', '', explanation)
        explanation = re.sub(r'\n[-:•*]+\s*', ' ', explanation)
        return explanation if explanation else f"No explanation provided for {category} score."
    
    # If not found after score, try to find general explanation for that section
    section = extract_section(text, category)
    if section:
        # Remove any score mentions from the section text
        section = re.sub(r'\d+[\s/]10', '', section).strip()
        return section
        
    return f"No explanation provided for {category} score."

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

def extract_tone_with_explanations(text: str) -> Dict[str, Any]:
    """
    Extract tone information with explanations
    """
    tones = {}
    explanations = {}
    
    # Extract the tone analysis section
    tone_section = extract_section(text, "Tone Analysis")
    
    if tone_section:
        # Look for patterns like "formal: 70%" or "formal (7/10)" or "formal - 7/10"
        tone_matches = re.finditer(r'(\w+)(?:\s*[:(-]\s*)(\d+)(?:%|/10)', tone_section, re.IGNORECASE)
        
        for match in tone_matches:
            tone = match.group(1).lower()
            try:
                score = int(match.group(2))
                # If it's a percentage, convert to decimal
                if '%' in match.group(0):
                    tones[tone] = score / 100.0
                else:
                    tones[tone] = score / 10.0
                
                # Try to extract explanation for this tone
                tone_explanation_pattern = rf"{tone}.*?(\d+)(?:%|/10)(.*?)(?=\w+\s*[:(-]\s*\d+(?:%|/10)|$)"
                explanation_match = re.search(tone_explanation_pattern, tone_section, re.IGNORECASE | re.DOTALL)
                if explanation_match:
                    explanation = explanation_match.group(2).strip()
                    explanation = re.sub(r'^[-:•*]+\s*', '', explanation)
                    explanation = re.sub(r'\n[-:•*]+\s*', ' ', explanation)
                    explanations[tone] = explanation
                else:
                    explanations[tone] = f"No specific explanation provided for {tone} tone."
            except ValueError:
                continue
    
    # If no tones found, provide default analysis
    if not tones:
        # Add some default tones based on keywords in the section
        keywords = {
            "formal": ["formal", "professional", "business"],
            "friendly": ["friendly", "warm", "casual"],
            "urgent": ["urgent", "pressing", "immediate"],
            "frustrated": ["frustrated", "annoyed", "impatient"],
            "neutral": ["neutral", "balanced", "even"]
        }
        
        if tone_section:
            for tone, words in keywords.items():
                # Count occurrences of keywords
                count = sum(1 for word in words if word.lower() in tone_section.lower())
                if count > 0:
                    tones[tone] = min(count * 0.2, 1.0)  # Scale up to 100% max
                    explanations[tone] = f"Detected {tone} tone based on language patterns in the conversation."
    
    # If still no tones, add a default tone
    if not tones:
        tones = {"neutral": 0.7, "formal": 0.5}
        explanations["neutral"] = "Default neutral tone assigned in the absence of clear tone indicators."
        explanations["formal"] = "Default mild formal tone assigned in the absence of clear tone indicators."
    
    # Combine tones and explanations
    result = {
        "scores": tones,
        "explanations": explanations
    }
    
    return result
 
def extract_section(text: str, section_name: str) -> str:
    """
    Extract a specific section from the analysis text
    """
    pattern = rf"{section_name}.*?:(.*?)(?=\d+\.|$|\n\s*\n)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


