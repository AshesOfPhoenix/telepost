from fastapi import APIRouter, HTTPException, status, Form, File, UploadFile
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage # For potential direct history manipulation if needed
from typing import Optional
from langchain_community.chat_message_histories import RedisChatMessageHistory, UpstashRedisChatMessageHistory
from langchain_core.messages import ChatMessage
import io
from openai import APIError  # Assuming OpenRouter uses OpenAI-compatible errors
import base64
from api.utils.logger import logger
from api.utils.config import get_settings
from api.utils.prompts import system_prompt

settings = get_settings()

router = APIRouter(
    prefix="/ai",
    tags=["ai"],
)

# --- LangChain Components ---

# 1. Chat Model (LLM Interface)
# Pointing ChatGoogleGenerativeAI to the Google Generative AI endpoint
llm = ChatGoogleGenerativeAI(
    model=settings.AI_MODEL_NAME,
    api_key=settings.OPENROUTER_API_KEY
)

# 2. Prompt Template
# Defines the structure of the input to the LLM.
# Includes a placeholder for history and the user's input.
prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt), # Optional system message
    MessagesPlaceholder(variable_name="history"), # Where the conversation history will be injected
    ("human", "{input}"), # Revert back to standard tuple format
])

# 3. Runnable Chain
# Basic chain combining the prompt and the LLM
base_runnable = prompt | llm

# 4. Function to get Redis Chat History instance per session
# This function is crucial for RunnableWithMessageHistory
# It ensures each conversation uses its unique history store in Redis.
def get_redis_message_history(session_id: str) -> RedisChatMessageHistory:
    """Creates and returns a RedisChatMessageHistory instance for a given session.

    Args:
        session_id: The unique identifier for the chat session (e.g., user_id).
        # Removed redis_url and ttl from docstring args as they are fetched from settings

    Returns:
        An instance of RedisChatMessageHistory.
    """
    logger.debug(f"Attempting to create Redis history for session: {session_id} at URL: {settings.REDIS_URL}")
    try:
        history = UpstashRedisChatMessageHistory(
            url=settings.UPSTASH_REDIS_REST_URL,
            token=settings.UPSTASH_REDIS_REST_TOKEN,
            session_id=session_id,
            ttl=settings.CHAT_HISTORY_TTL_SECONDS
        )
        logger.debug(f"Successfully created Redis history object for session: {session_id} - Type: {type(history)}")
        return history
    except Exception as e:
        logger.error(f"FAILED to create Redis history for session {session_id}: {e}", exc_info=True)
        raise

# --- Main Function ---

def get_ai_response_with_history(
    user_message: str,
    session_id: str,
    image_base64: Optional[str] = None,  # Add image parameters
    image_mime_type: Optional[str] = None
) -> str:
    """
    Processes a user message (and optionally an image) using the LLM with Redis-backed history.

    Args:
        user_message: The message input from the user.
        session_id: A unique identifier for the conversation session (e.g., user_id or chat_id).
        image_base64: Optional Base64 encoded string of the image.
        image_mime_type: Optional MIME type of the image (e.g., 'image/jpeg').

    Returns:
        The AI's response message content as a string.
    """
    print(f"\n--- Processing for Session ID: {session_id} ---")
    print(f"User Message: {user_message}")
    print(f"Image provided: {image_base64 is not None}")

    # Configuration for the invocation, specifying the session_id
    config = {"configurable": {"session_id": session_id}}

    # Construct input based on whether an image is present
    if image_base64 and image_mime_type:
        # Explicitly create the HumanMessage content list dynamically
        human_input_content = []
        if user_message: # Only add text part if user_message is not empty
            human_input_content.append({"type": "text", "text": user_message})
        
        # Always add image part if image is present
        human_input_content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{image_mime_type};base64,{image_base64}"}
            }
        )

        if not human_input_content:
            # This case should ideally not happen if image_base64 and image_mime_type are present,
            # but as a safeguard, maybe return an error or default message?
            logger.error("Multimodal request attempted with no content generated.")
            return "Error processing multimodal request: No content."
            # Or revert to text-only if needed, though that defeats the purpose.
            # invoke_payload = {"input": "Received an image, but failed to process content."}

        invoke_payload = {"input": HumanMessage(content=human_input_content)}
    else:
        # For text-only, ensure user_message is not empty
        if not user_message:
             logger.warning("Received text-only request with empty message.")
             # Decide how to handle empty text-only messages (e.g., error, default response)
             # For now, let it pass to see if the chain handles it, but it might error.
             # return "Please provide a message."
        invoke_payload = {"input": user_message}

    # Chain with Message History setup (remains the same)
    chain_with_history = RunnableWithMessageHistory(
        runnable=base_runnable,
        get_session_history=get_redis_message_history,  # Pass the factory function itself
        input_messages_key="input",
        history_messages_key="history",
    )
    
    logger.debug(f"Chain with history: {chain_with_history}")
    # logger.debug(f"Invoke payload: {invoke_payload}")

    # Invoke the chain with the prepared input
    try:
        response = chain_with_history.invoke(invoke_payload, config=config) # Use dynamic invoke_payload
        ai_response_content = response.content
        print(f"AI Response: {ai_response_content}")

    except Exception as e:
        print(f"Error during AI processing: {e}")
        # Handle errors appropriately - maybe return a default error message
        ai_response_content = "There was an issue processing your request."

    print("--- Processing Complete ---")
    return ai_response_content

# --- Pydantic Models ---
class AIChatRequest(BaseModel):
    user_id: str
    message: str

class AIChatResponse(BaseModel):
    response: str

# --- Endpoint ---
@router.post("/chat", response_model=AIChatResponse)
async def chat_with_ai(
    user_id: str = Form(...),
    message: str = Form(...),
    media_file: Optional[UploadFile] = File(None)
) -> AIChatResponse:
    """Handles chat requests, maintains conversation history via Redis, and interacts with OpenRouter AI."""

    logger.info(f"Received chat request for user_id: {user_id}")

    base64_contents = None
    mime_type = None

    # Handle the media_file if provided
    if media_file:
        logger.info(f"Received media file for user {user_id}: {media_file.filename}, content type: {media_file.content_type}")
        if not media_file.content_type or not media_file.content_type.startswith("image/"):
            logger.warning(f"Received non-image file type: {media_file.content_type}. Ignoring file.")
            # Optionally raise HTTPException or return error to user
            # raise HTTPException(status_code=400, detail="Only image files are supported.")
        else:
            contents = await media_file.read()
            base64_contents = base64.b64encode(contents).decode('utf-8')
            mime_type = media_file.content_type
            logger.debug(f"Image {media_file.filename} encoded to base64, mime_type: {mime_type}")

    try:
        # Pass image data (if any) to the history function
        response = get_ai_response_with_history(
            user_message=message,
            session_id=user_id,
            image_base64=base64_contents,
            image_mime_type=mime_type
        )
        logger.info(f"Generated AI response for user {user_id}: {response}")

        if not response:
             logger.warning(f"Received empty response from AI for user {user_id}")
             response = "Sorry, I couldn't generate a response." # Provide a default

        logger.info(f"Successfully generated AI response for user {user_id}")
        return AIChatResponse(response=response)

    except APIError as e:
        logger.error(f"OpenRouter API error for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to communicate with the AI service. Please try again later."
        )
    except Exception as e:
        logger.exception(f"Unexpected error processing chat for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing your request."
        )
