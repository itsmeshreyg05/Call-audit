import json
import re
from zoneinfo import ZoneInfo
import ollama
from typing import Dict, List, Any
from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from src.utils.google_sheets_helper import append_dict_to_sheet
from src.database.database import get_db
from src.models.model import Audio, Analysis, Segment
from src.schemas.schema import CallAnalysisResult, DiarizationSegment
from src.routes.audio import diarize_audio
from src.models.model import RecordingDetail
from src.config.log_config import logger
 

router = APIRouter(
    prefix="/call-analysis",
    tags=["call analysis"],
    responses={404: {"description": "Not found"}},
)
 

MISTRAL_MODEL = "mistral"  


@router.post("/", response_model=CallAnalysisResult)
async def analyze_call(audio_id: str = Header(..., description="Audio ID to analyze"), db: Session = Depends(get_db)):
    """
    Analyze a transcribed call using Ollama's Mistral model.
    Pass the audio_id in the request header. The segments will be retrieved from the database.
    """
    db_audio = db.query(Audio).filter(Audio.id == audio_id).first()
    if not db_audio:
        raise HTTPException(status_code=404, detail="Audio ID not found")
   
     ##
    full_transcript = db_audio.full_transcript
    if not full_transcript:
        raise HTTPException(status_code=400, detail="No transcript available")

 
 

    recording_id = db_audio.recording_id
 

    recording_detail = db.query(RecordingDetail).filter(RecordingDetail.recording_id == recording_id).first()
 

    username = recording_detail.username if recording_detail else "Unknown"
    phone_number = recording_detail.phone_number if recording_detail else "Unknown"
    start_time = recording_detail.start_time if recording_detail else None
    duration = recording_detail.duration if recording_detail else None
    extension = recording_detail.extension_number if recording_detail else None  # Placeholder for extension, if needed
    transcription = db_audio.full_transcript if db_audio.full_transcript else "No transcription available"
    
    print(f"start time: {start_time}")
    if start_time:
        try:
            start_time_est = start_time.astimezone(ZoneInfo("America/New_York"))
            formatted_est = start_time_est.strftime("%m/%d/%Y %I:%M %p")
            
        except Exception as e:
            formatted_est = "Unknown"
    else:
        formatted_est = "Unknown"

    print(f"formatted time {formatted_est}")
    

    if not db_audio.processed:
        try:
            diarization_result = await diarize_audio(audio_id, db)
            if diarization_result.status.startswith("failed"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to diarize audio: {diarization_result.status}"
                )
        except Exception as e:  
                logger.error(f"Error during diarization for audio_id {audio_id}: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to process audio diarization")
    
    db_segments = db.query(Segment).filter(Segment.audio_id == audio_id).all()
    if not db_segments:
        raise HTTPException(
            status_code=400,
            detail="No transcribed segments found for this audio. Please diarize the audio first."
        )
 
    segments = [
        DiarizationSegment(
            speaker=segment.speaker,
            start=segment.start,
            end=segment.end,
            text=segment.text
        ) for segment in db_segments
    ]
 

    conversation_text = format_conversation(segments)
    prompt = create_mistral_prompt(conversation_text)
 
    try:
        analysis_result = query_ollama_mistral(prompt, MISTRAL_MODEL)
    except Exception as e:
        return CallAnalysisResult(
            audio_id=audio_id,
            analysis={"error": str(e)},
            status="failed"
        )
 
    parsed_analysis = parse_mistral_response(analysis_result)

 
    db_analysis = db.query(Analysis).filter(Analysis.audio_id == audio_id).first()
    if db_analysis:
        for key, value in parsed_analysis.items():
            setattr(db_analysis, key, value)
        db_analysis.status = "completed"
        db_analysis.outcome_category = parsed_analysis.get("call_outcome", {}).get("outcome_category", "Unknown")
        db_analysis.outcome_phrases = parsed_analysis.get("call_outcome", {}).get("supporting_phrases", [])
        db_analysis.outcome_explanation = parsed_analysis.get("call_outcome", {}).get("explanation", "")
    else:
        db_analysis = Analysis(
            audio_id=audio_id,
            professionalism_score=parsed_analysis.get("introduction_score", 0),
            tone_analysis=parsed_analysis.get("tone_analysis", {}),
            context_awareness_score=parsed_analysis.get("adherence_to_script_score", 0),
            response_time_analysis=parsed_analysis.get("actively_listening_score", {}),
            fluency_score=parsed_analysis.get("fluency_score", 0),
            probing_effectiveness=parsed_analysis.get("probing_score", 0),
            call_closing_quality=parsed_analysis.get("closing_score", 0),
            summary=parsed_analysis.get("summary", ""),
            outcome_category=parsed_analysis.get("call_outcome", {}).get("outcome_category", "Unknown"),
            outcome_phrases=parsed_analysis.get("call_outcome", {}).get("supporting_phrases", []),
            outcome_explanation=parsed_analysis.get("call_outcome", {}).get("explanation", ""),
            status="completed"
        )
        db.add(db_analysis)
 
    db.commit()
 
 
 
    introduction_score = apply_score_threshold(parsed_analysis.get('introduction_score', 0))
    adherence_score = apply_score_threshold(parsed_analysis.get('adherence_to_script_score', 0))
    listening_score = apply_score_threshold(parsed_analysis.get('actively_listening_score', 0))
    fumble_score = apply_score_threshold(parsed_analysis.get('fumble_score', 0))
    probing_score = apply_score_threshold(parsed_analysis.get('probing_score', 0))
    closing_score = apply_score_threshold(parsed_analysis.get('closing_score', 0))


    scores = [introduction_score, adherence_score, listening_score, fumble_score, probing_score, closing_score]
    scores = [float(score) for score in scores]
  

  
    average_score = round((sum(scores) / len(scores) ) , 2)

    reason = parsed_analysis.get("call_outcome", {}).get("outcome_category", "Unknown")
 
   
    if reason.lower() == "out of scope":
        logger.info(f"Recording {recording_id} skipped due to reason: {reason}")
    else:
        row_data = {
            "Date/Time": formatted_est,
            "Duration": duration,
            "Recording Id": recording_id,
            "Username": username,
            "Extension": extension,
            "PhoneNumber": phone_number,
            "Introduction/Hook": f"{introduction_score}%",
            "Adherence to script/Product Knowledge": f"{adherence_score}%",
            "Actively listening/ Responding Appropriately": f"{listening_score}%",
            "Fumble": f"{fumble_score}%",
            "Probing": f"{probing_score}%",
            "Closing": f"{closing_score}%",
            "Overall Score": f"{average_score}%",
            "Summary": parsed_analysis.get("summary", ""),
            "Transcript": transcription,
            "Remarks": parsed_analysis.get("call_outcome", {}).get("explanation", "Unknown"),
            "Reason": reason
        }
        try:
            append_dict_to_sheet(row_data, sheet_name="Sheet1")
        except Exception as e:
            logger.error(f"Error appending data to Google Sheet: {str(e)}")
            
 
 
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
        if text:  
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
   
    1. Introduction/Hook (Score 1-100):
 
        - Company Introduction: Did the representative clearly mention the company they represent?
 
        - Was it stated early in the call to establish identity?
 
        - Assess the effectiveness and engagement level of the conversation's opening
 
        - Was the introduction clear, confident, and engaging?
 
        - IMPORTANT: Provide a 1-2 sentence explanation for your score
 
    2. Adherence to Script/Product Knowledge (Score 1-100):
 
        - Evaluate how well the representative followed the expected conversation structure
 
        - Rate the representative's command of product/service details
 
        - Assess accuracy of information provided and ability to address questions
 
        - IMPORTANT: Provide a 1-2 sentence explanation for your score
 
    3. Actively Listening/Responding Appropriately (Score 1-100):
 
        - Evaluate if the representative listened actively and showed understanding of the conversation context.
 
        - Did the representative acknowledge and build on the client's statements?
 
        - Were responses tailored to the client's specific comments and needs?
 
        - Did the representative avoid interrupting the client while speaking?
 
        - IMPORTANT: Provide a 1-2 sentence explanation for your score.
 
    4. Fumble (Score 1-100):
 
        - Evaluate the representative's speech fluency. Was their speech smooth and free of excessive pauses?
 
        - Check for filler words like “um,” “uh,” or awkward pauses.
 
        - Did the representative maintain confidence throughout the conversation?
 
        - Was the tone clear and professional?
 
        - IMPORTANT: Provide a 1-2 sentence explanation for your score
 
    5. Probing (Score 1-100):
 
        - Assess the quality of the representative's questions. Were they insightful and relevant to uncover needs?
 
        - Evaluate whether follow-up questions were logical and connected to prior responses.
 
        - Check if the representative effectively used open-ended questions.
 
        - Did the probing help support or introduce the product/service pitch?
 
        - Was probing used to present persuasive or compelling solutions?
 
        - IMPORTANT: Provide a 1-2 sentence explanation for your score.
 
    6. Closing (Score 1-100):
 
        - Analyze how effectively the call was concluded
 
        - Evaluate clarity on next steps and any commitments secured
 
        - Was the call concluded confidently and with clarity?
 
        - IMPORTANT: Provide a 1-2 sentence explanation for your score
 
    7. Overall Score (Score 1-100):
 
        - Calculate a weighted average score based on all the dimensions above
 
        - IMPORTANT: Provide a 1-2 sentence explanation for your score
 
    8. Summary:
 
        - Provide a concise summary (3-5 sentences) of the overall conversation quality
 
        - Highlight key strengths and areas for improvement
 
        - Include observations on conversation flow and effectiveness
 
    9. Call Outcome Classification:
 
       - Classify the call outcome based on the final conversation exchanges and overall conversation context
 
       - Carefully analyze the prospect's final response and tone to determine the accurate outcome
 
       - Available outcome categories: "Prospect agreed for the meeting", "Prospect disconnected the call", "Prospect not interested", "Out of scope", "Prospect will reach out in future if required"
 
       
       Classification Guidelines:
       • "Call back requested" should ONLY be used when the prospect explicitly asks to be called back at a specific time or says they want the representative to call them again
       • "Prospect not interested" - when prospect explicitly states disinterest with phrases like "I'm not interested", "Not for me", "This doesn't work for us"
       • "Out of scope" - when prospect indicates they are not with the target organization or not the right person (e.g., "I'm not with that organization", "I don't work there anymore", "Wrong department")
       • "Prospect will reach out in future if required" - when prospect says they will contact the representative themselves, mentions connecting on LinkedIn, or will get back to them on their own
       • "Prospect agreed for the meeting" - when prospect confirms a meeting, agrees to next steps, or shows clear interest in proceeding
       • "Prospect disconnected the call" - when call ends abruptly without clear resolution
       
       - If disinterest was expressed, note the exact phrases used
       - IMPORTANT: Provide specific phrases that indicated the outcome and ensure the classification matches the actual conversation ending
   
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
       
    
        if response and "message" in response and "content" in response["message"]:
            return response["message"]["content"]
        else:
            raise Exception("No content in response from Ollama")
           
    except Exception as e:
        raise Exception(f"Error communicating with Ollama library: {str(e)}")

def apply_score_threshold(score: Any) -> int:
    """
    Applies threshold logic specifically for scoring:
    - If score is None or not a number, return 0
    - If score >= 75: return 100
    - If 50 <= score < 75: return 75
    - If 35 <= score < 50: return 50
    - If 0 <= score < 35: return 0
    """
    if score is None:
        return 0
    try:
        score = int(score)
        if score >= 75:
            return 100
        elif 50 <= score < 75:
            return 75
        elif 35 <= score < 50:
            return 50
        elif 0 <= score < 35:
            return 0
        else:
            return 0 
    except (ValueError, TypeError):
        return 0

    
def parse_mistral_response(response_text: str) -> Dict[str, Any]:
    """
    Parse the raw text response from Mistral into structured analysis with explanations
    based on the specified fields: Introduction/Hook, Adherence to Script/Product Knowledge,
    Actively Listening/Responding Appropriately, Fumble, Probing, Closing, Overall Score, Summary
    """
    try:

        json_match = re.search(r'\{[\s\S]*\}', response_text)
       
        if json_match:
            json_str = json_match.group(0)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass  
       
       
        introduction_score = extract_score(response_text, "Introduction/Hook")
        introduction_explanation = extract_explanation(response_text, "Introduction/Hook")
       
        adherence_product_score = extract_score(response_text, "Adherence to Script/Product Knowledge")
        adherence_product_explanation = extract_explanation(response_text, "Adherence to Script/Product Knowledge")
       
        actively_listening_score = extract_score(response_text, "Actively Listening/Responding Appropriately")
        actively_listening_explanation = extract_explanation(response_text, "Actively Listening/Responding Appropriately")
       
        fumble_score = extract_score(response_text, "Fumble")
        fumble_explanation = extract_explanation(response_text, "Fumble")
       
        probing_score = extract_score(response_text, "Probing")
        probing_explanation = extract_explanation(response_text, "Probing")
       
        closing_score = extract_score(response_text, "Closing")
        closing_explanation = extract_explanation(response_text, "Closing")
       
        overall_score = extract_score(response_text, "Overall Score")
        overall_explanation = extract_explanation(response_text, "Overall Score")
       

        outcome_category = "Unknown"
        supporting_phrases = []
        outcome_explanation = ""
       
        
        outcome_section = extract_section(response_text, "Call Outcome") or extract_section(response_text, "Outcome Classification")
        if outcome_section:
     
            category_match = re.search(r'category[\s:]+["\'"]?([^"\'"\n]+)["\'"]?', outcome_section, re.IGNORECASE)
            if category_match:
                outcome_category = category_match.group(1).strip()
           
           
            phrases_match = re.findall(r'["\'"]([^"\'"\n]{5,})["\'"]', outcome_section)
            if phrases_match:
                supporting_phrases = [phrase.strip() for phrase in phrases_match]
           
            outcome_explanation = re.sub(r'category[\s:]+["\'"]?[^"\'"\n]+["\'"]?', '', outcome_section)
            outcome_explanation = re.sub(r'phrases[\s:]+[\[\{].*?[\]\}]', '', outcome_explanation, flags=re.DOTALL)
            outcome_explanation = outcome_explanation.strip()
       
       
        summary = extract_section(response_text, "summary") or \
                 extract_section(response_text, "overall summary") or \
                 "Analysis complete but no summary provided"
       
        analysis = {
            "introduction_score": introduction_score,
            "introduction_explanation": introduction_explanation,
           
            "adherence_script_product_knowledge_score": adherence_product_score,
            "adherence_script_product_knowledge_explanation": adherence_product_explanation,
           
            "actively_listening_responding_score": actively_listening_score,
            "actively_listening_responding_explanation": actively_listening_explanation,
           
            "fumble_score": fumble_score,
            "fumble_explanation": fumble_explanation,
           
            "probing_score": probing_score,
            "probing_explanation": probing_explanation,
           
            "closing_score": closing_score,
            "closing_explanation": closing_explanation,
           
            "overall_score": overall_score,
            "overall_explanation": overall_explanation,
           
          
            "call_outcome": {
                "outcome_category": outcome_category,
                "supporting_phrases": supporting_phrases,
                "explanation": outcome_explanation
            } if outcome_section else None,
           
            "summary": summary
        }
       
        return analysis
   
    except Exception as e:
      
        return {
            "raw_analysis": response_text,
            "parsing_error": str(e),
            "summary": "Could not parse structured analysis from model output"
        }
 
def extract_explanation(text: str, category: str) -> str:
    """
    Extract explanation for a specific category
    """
 
    score_match = re.search(rf"{category}.*?(\d+)[\s/]100(.*?)(?=\d+\.|$|\n\s*\n)", text, re.IGNORECASE | re.DOTALL)
    if score_match:
        explanation = score_match.group(2).strip()
        explanation = re.sub(r'^[-:•*]+\s*', '', explanation)
        explanation = re.sub(r'\n[-:•*]+\s*', ' ', explanation)
        return explanation if explanation else f"No explanation provided for {category} score."
   

    section = extract_section(text, category)
    if section:

        section = re.sub(r'\d+[\s/]100', '', section).strip()
        return section
       
    return f"No explanation provided for {category} score."
 
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
 
def extract_section(text: str, section_name: str) -> str:
    """
    Extract a specific section from the analysis text
    """
    pattern = rf"{section_name}.*?:(.*?)(?=\d+\.|$|\n\s*\n)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return None
 
 
