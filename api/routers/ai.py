from fastapi import APIRouter, HTTPException, status
from fastapi import Request
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage # For potential direct history manipulation if needed
from typing import Optional
from langchain_community.chat_message_histories import RedisChatMessageHistory

from openai import APIError  # Assuming OpenRouter uses OpenAI-compatible errors

from api.utils.logger import logger
from api.utils.config import get_settings

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
    ("system", "You are a helpful conversational assistant. You are talking to Kristjan."), # Optional system message
    MessagesPlaceholder(variable_name="history"), # Where the conversation history will be injected
    ("human", "{input}"), # The user's current input
])

# 3. Runnable Chain
# Basic chain combining the prompt and the LLM
base_runnable = prompt | llm

# 4. Function to get Redis Chat History instance per session
# This function is crucial for RunnableWithMessageHistory
# It ensures each conversation uses its unique history store in Redis.
def get_redis_message_history(
    session_id: str,
) -> RedisChatMessageHistory:
    """Creates and returns a RedisChatMessageHistory instance for a given session.

    Args:
        session_id: The unique identifier for the chat session (e.g., user_id).
        redis_url: The connection URL for the Redis instance.
        ttl: Time-to-live in seconds for the chat history in Redis. If None, history persists indefinitely.

    Returns:
        An instance of RedisChatMessageHistory.
    """
    return RedisChatMessageHistory(session_id=session_id, url=settings.REDIS_URL, ttl=settings.CHAT_HISTORY_TTL_SECONDS)

# 5. Chain with Message History
# Wraps the base runnable and automatically manages history loading and saving.
# - runnable: The core logic (prompt | llm).
# - get_session_history: The factory function defined above.
# - input_messages_key: The key in the input dictionary for the user's message ("input").
# - history_messages_key: The key for the history messages ("history"), matching the MessagesPlaceholder.
chain_with_history = RunnableWithMessageHistory(
    runnable=base_runnable,
    get_session_history=get_redis_message_history,
    input_messages_key="input",
    history_messages_key="history",
)

# --- Main Function ---

def get_ai_response_with_history(user_message: str, session_id: str) -> str:
    """
    Processes a user message using the LLM with Redis-backed history.

    Args:
        user_message: The message input from the user.
        session_id: A unique identifier for the conversation session (e.g., user_id or chat_id).

    Returns:
        The AI's response message content as a string.
    """
    print(f"\n--- Processing for Session ID: {session_id} ---")
    print(f"User Message: {user_message}")

    # Configuration for the invocation, specifying the session_id
    # This tells RunnableWithMessageHistory which history store to use (via get_redis_message_history)
    config = {"configurable": {"session_id": session_id}}

    # Invoke the chain. LangChain handles:
    # 1. Calling get_redis_message_history(session_id) to get the history object.
    # 2. Loading past messages from Redis.
    # 3. Populating the 'history' variable in the prompt.
    # 4. Populating the 'input' variable with user_message.
    # 5. Calling the LLM.
    # 6. Getting the AIMessage response.
    # 7. Saving the new HumanMessage and AIMessage back to Redis via the history object.
    try:
        response = chain_with_history.invoke({"input": user_message}, config=config)
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
    request: Request
) -> AIChatResponse:
    """Handles chat requests, maintains conversation history via Redis, and interacts with OpenRouter AI."""
    params = dict(request.query_params)
    user_id = params.get('user_id')
    message = params.get('message', 'Hello')
    
    logger.info(f"Received chat request for user_id: {user_id}")

    try:
        response = get_ai_response_with_history(message, user_id)
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
