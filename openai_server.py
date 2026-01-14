"""
OpenAI Compatible API Server for Gemini
Mimics OpenAI's /v1/chat/completions endpoint using Gemini backend.

Features:
- Full Stream Support (SSE)
- Auto Account Rotation (via Supabase)
- System Prompt Support

Dependencies:
pip install fastapi uvicorn sse-starlette
"""

import sys
import time
import json
import uuid
import asyncio
import os
from pathlib import Path
from typing import List, Optional, Union, Dict, Any, Tuple

# Ensure we can import from src
PROJECT_ROOT = Path(__file__).parent
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
import uvicorn
import shutil

from gemini_webapi import GeminiClient, ImageMode
from gemini_webapi.account_manager import GeminiAccountManager
from gemini_webapi.constants import Model
# ================= Configuration =================
HOST = "0.0.0.0"
PORT = 8001
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://lvpbegckuzmppqcvbtkj.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "sb_secret_y9fn8HzVdDEmUqzttysMHQ_dEzWvD5R")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️ Warning: SUPABASE_URL or SUPABASE_KEY not found in environment.")
# ===============================================

app = FastAPI(title="Gemini OpenAI Proxy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from fastapi.staticfiles import StaticFiles

# --- Configuration for Cleanup ---
CLEANUP_INTERVAL = 3600  # Check every 1 hour
# Default 24 hours, can be set via env var
IMAGE_EXPIRY_HOURS = int(os.getenv("IMAGE_EXPIRY_HOURS", "24")) 
FILE_EXPIRY_SECONDS = IMAGE_EXPIRY_HOURS * 3600

# --- OpenAI Models ---
# ... imports ...

async def cleanup_old_files():
    """Background task to delete expired files."""
    while True:
        try:
            # print("🧹 Running image cleanup check...") 
            now = time.time()
            directory = "static/images"
            if os.path.exists(directory):
                count = 0
                for filename in os.listdir(directory):
                    file_path = os.path.join(directory, filename)
                    if os.path.isfile(file_path):
                        if (now - os.path.getmtime(file_path)) > FILE_EXPIRY_SECONDS:
                            try:
                                os.remove(file_path)
                                count += 1
                            except Exception as e:
                                print(f"❌ Failed to delete {filename}: {e}")
                if count > 0:
                    print(f"🧹 Cleaned up {count} expired images (> {IMAGE_EXPIRY_HOURS}h).")
        except Exception as e:
            print(f"❌ Cleanup task error: {e}")
        
        await asyncio.sleep(CLEANUP_INTERVAL)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(cleanup_old_files())

# Ensure static directory exists
os.makedirs("static/images", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")

def save_image_locally(image_data: bytes, filename: str) -> str:
    """Save image bytes to static dir and return relative URL."""
    file_path = f"static/images/{filename}"
    with open(file_path, "wb") as f:
        f.write(image_data)
    # Return full URL if possible, or relative. OpenAI clients usually expect full URL.
    # We will construct it in the route handler using request.base_url
    return f"static/images/{filename}"

import base64
import requests

class ChatMessage(BaseModel):
    role: str
    content: Union[str, List[Dict[str, Any]]]
    name: Optional[str] = None

class ChatCompletionRequest(BaseModel):
    model: str = "gpt-3.5-turbo"
    messages: List[ChatMessage]
    stream: bool = False
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    max_tokens: Optional[int] = None

class ImageGenerationRequest(BaseModel):
    prompt: str
    model: Optional[str] = "g3-img-pro"
    n: int = 1
    size: str = "1024x1024"
    response_format: Optional[str] = "url"
    user: Optional[str] = None

class ModelList(BaseModel):
    object: str = "list"
    data: List[Dict[str, Any]] = []

# --- Helper Functions ---

def get_gemini_client():
    """Get an initialized Gemini client using rotation."""
    manager = GeminiAccountManager(SUPABASE_URL, SUPABASE_KEY)
    try:
        account = manager.get_next_account()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"No available accounts: {e}")
    
    print(f"🔹 Using account: {account['alias']}")
    client = GeminiClient(
        secure_1psid=account["psid"],
        secure_1psidts=account["psidts"],
        proxy=account.get("proxy"),
        headers=account.get("headers")
    )
    return client

async def init_client(client: GeminiClient):
    try:
        await client.init()
    except Exception as e:
        print(f"❌ Init failed: {e}")
        await client.close()
        raise HTTPException(status_code=500, detail="Failed to initialize Gemini client")

def process_base64_image(base64_string: str) -> str:
    """Decode base64 image to temp file."""
    if "base64," in base64_string:
        base64_string = base64_string.split("base64,")[1]
    
    image_data = base64.b64decode(base64_string)
    file_path = f"temp_chat_img_{uuid.uuid4()}.png"
    
    with open(file_path, "wb") as f:
        f.write(image_data)
        
    return file_path

def process_url_image(url: str) -> str:
    """Download image from URL to temp file."""
    # Safety check/Size check omitted for brevity
    resp = requests.get(url, stream=True)
    if resp.status_code == 200:
        file_path = f"temp_chat_img_{uuid.uuid4()}.png"
        with open(file_path, "wb") as f:
            resp.raw.decode_content = True
            shutil.copyfileobj(resp.raw, f)
        return file_path
    raise Exception(f"Failed to download image: {url}")

def extract_content_and_files(messages: List[ChatMessage]) -> Tuple[str, List[str]]:
    """
    Parse OpenAI messages to get prompt text and file paths.
    Supports GPT-4V format.
    """
    full_prompt = ""
    files = []
    
    for msg in messages:
        role_label = msg.role.capitalize()
        content = msg.content
        
        if isinstance(content, str):
            full_prompt += f"{role_label}: {content}\n"
        elif isinstance(content, list):
            # Handle List[Dict] (GPT-4V)
            full_prompt += f"{role_label}: "
            for part in content:
                if part.get("type") == "text":
                    full_prompt += part.get("text", "") + "\n"
                elif part.get("type") == "image_url":
                    img_url = part.get("image_url", {}).get("url", "")
                    if img_url.startswith("data:"):
                        files.append(process_base64_image(img_url))
                    elif img_url.startswith("http"):
                        files.append(process_url_image(img_url))
                    else:
                        # Local path?
                        pass
                    full_prompt += "[Image]\n"
        
    return full_prompt, files

# --- Routes ---

@app.post("/v1/images/generations")
async def generate_images(request: ImageGenerationRequest, req: Request):
    """
    Handle Text-to-Image generation.
    Includes retry logic for rate limit errors.
    """
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # seconds
    
    print(f"🎨 Image Gen Prompt: {request.prompt} (Model: {request.model})")
    
    last_error = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        client = None
        try:
            client = get_gemini_client()
            await init_client(client)
            
            response = await client.generate_content(request.prompt, image_mode=ImageMode.PRO)
            
            data = []
            if response.images:
                for img in response.images:
                    filename = f"gen_{uuid.uuid4()}.png"
                    await img.save(path="static/images", filename=filename, skip_invalid_filename=True)
                    
                    local_url = f"{req.base_url}static/images/{filename}"
                    
                    data.append({
                        "url": local_url,
                        "revised_prompt": request.prompt
                    })
                    
                return {
                    "created": int(time.time()),
                    "data": data
                }
            else:
                error_text = response.text or "No image generated"
                if "ask me again later" in error_text.lower() or "more images than usual" in error_text.lower():
                    print(f"⚠️ Rate limited (attempt {attempt}/{MAX_RETRIES}), retrying in {RETRY_DELAY}s...")
                    last_error = error_text
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                else:
                    raise HTTPException(status_code=400, detail=error_text)
                
        except HTTPException:
            raise
        except Exception as e:
            error_str = str(e)
            if "ask me again later" in error_str.lower() or "more images than usual" in error_str.lower():
                print(f"⚠️ Rate limited (attempt {attempt}/{MAX_RETRIES}), retrying in {RETRY_DELAY}s...")
                last_error = error_str
                await asyncio.sleep(RETRY_DELAY)
                continue
            else:
                print(f"❌ Image Gen Error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        finally:
            if client:
                await client.close()
    
    print(f"❌ Image Gen Failed after {MAX_RETRIES} retries")
    raise HTTPException(status_code=500, detail=f"Rate limited after {MAX_RETRIES} retries: {last_error}")

@app.post("/v1/images/edits")
async def edit_image(
    image: UploadFile = File(...),
    mask: Optional[UploadFile] = File(None),
    prompt: str = Form(...),
    model: Optional[str] = Form("g3-img-pro"),
    n: int = Form(1),
    size: str = Form("1024x1024"),
    response_format: str = Form("url"),
    user: Optional[str] = Form(None),
    req: Request = None
):
    """
    Handle Image-to-Image (Edit).
    Maps to Gemini Chat with file upload.
    Includes retry logic for rate limit errors.
    """
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # seconds
    
    # Save uploaded file first (only once)
    temp_path = Path(f"static/images/upload_{uuid.uuid4()}.png")
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
        
    print(f"🎨 Image Edit Prompt: {prompt} (File: {temp_path}, Model: {model})")
    
    last_error = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        client = None
        try:
            client = get_gemini_client()
            await init_client(client)
            
            chat = client.start_chat()
            response = await chat.send_message(
                prompt,
                files=[str(temp_path)],
                image_mode=ImageMode.PRO
            )
            
            data = []
            if response.images:
                for img in response.images:
                    filename = f"edit_{uuid.uuid4()}.png"
                    await img.save(path="static/images", filename=filename, skip_invalid_filename=True)
                    
                    base_url = str(req.base_url) if req else f"http://{HOST}:{PORT}/"
                    local_url = f"{base_url}static/images/{filename}"

                    data.append({
                        "url": local_url,
                        "revised_prompt": prompt
                    })
                    
                return {
                    "created": int(time.time()),
                    "data": data
                }
            else:
                error_text = response.text or "No image generated"
                if "ask me again later" in error_text.lower() or "more images than usual" in error_text.lower():
                    print(f"⚠️ Rate limited (attempt {attempt}/{MAX_RETRIES}), retrying in {RETRY_DELAY}s...")
                    last_error = error_text
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                else:
                    raise HTTPException(status_code=400, detail=error_text)

        except HTTPException:
            raise
        except Exception as e:
            error_str = str(e)
            if "ask me again later" in error_str.lower() or "more images than usual" in error_str.lower():
                print(f"⚠️ Rate limited (attempt {attempt}/{MAX_RETRIES}), retrying in {RETRY_DELAY}s...")
                last_error = error_str
                await asyncio.sleep(RETRY_DELAY)
                continue
            else:
                print(f"❌ Image Edit Error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        finally:
            if client:
                await client.close()
    
    print(f"❌ Image Edit Failed after {MAX_RETRIES} retries")
    raise HTTPException(status_code=500, detail=f"Rate limited after {MAX_RETRIES} retries: {last_error}")

@app.post("/v1/images/edits/multi")
async def edit_image_multi(
    images: List[UploadFile] = File(...),
    prompt: str = Form(...),
    model: Optional[str] = Form("g3-img-pro"),
    n: int = Form(1),
    size: str = Form("1024x1024"),
    response_format: str = Form("url"),
    user: Optional[str] = Form(None),
    req: Request = None
):
    """
    Handle Image-to-Image with MULTIPLE reference images.
    Upload multiple images and generate a new one based on them.
    Includes retry logic for rate limit errors.
    """
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # seconds
    
    temp_paths = []
    
    # Save all uploaded files first (only once)
    for image in images:
        temp_path = Path(f"static/images/upload_{uuid.uuid4()}.png")
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        temp_paths.append(str(temp_path))
    
    print(f"🎨 Multi-Image Edit Prompt: {prompt} (Files: {len(temp_paths)}, Model: {model})")
    
    last_error = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        client = None
        try:
            client = get_gemini_client()
            await init_client(client)
            
            chat = client.start_chat()
            response = await chat.send_message(
                prompt,
                files=temp_paths,
                image_mode=ImageMode.PRO
            )
            
            data = []
            if response.images:
                for img in response.images:
                    # Save locally
                    filename = f"edit_{uuid.uuid4()}.png"
                    await img.save(path="static/images", filename=filename, skip_invalid_filename=True)
                    
                    # Construct local URL
                    base_url = str(req.base_url) if req else f"http://{HOST}:{PORT}/"
                    local_url = f"{base_url}static/images/{filename}"

                    data.append({
                        "url": local_url,
                        "revised_prompt": prompt
                    })
                    
                return {
                    "created": int(time.time()),
                    "data": data
                }
            else:
                # Check if it's a rate limit / overload error
                error_text = response.text or "No image generated"
                if "ask me again later" in error_text.lower() or "more images than usual" in error_text.lower():
                    print(f"⚠️ Rate limited (attempt {attempt}/{MAX_RETRIES}), retrying in {RETRY_DELAY}s...")
                    last_error = error_text
                    await asyncio.sleep(RETRY_DELAY)
                    continue
                else:
                    raise HTTPException(status_code=400, detail=error_text)

        except HTTPException:
            raise
        except Exception as e:
            error_str = str(e)
            # Check if retriable error
            if "ask me again later" in error_str.lower() or "more images than usual" in error_str.lower():
                print(f"⚠️ Rate limited (attempt {attempt}/{MAX_RETRIES}), retrying in {RETRY_DELAY}s...")
                last_error = error_str
                await asyncio.sleep(RETRY_DELAY)
                continue
            else:
                print(f"❌ Multi-Image Edit Error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        finally:
            if client:
                await client.close()
    
    # All retries exhausted
    print(f"❌ Multi-Image Edit Failed after {MAX_RETRIES} retries")
    raise HTTPException(status_code=500, detail=f"Rate limited after {MAX_RETRIES} retries: {last_error}")

@app.get("/v1/models")
async def list_models():
    """List available models."""
    # We map Gemini models to OpenAI names for compatibility, plus real names
    timestamp = int(time.time())
    models = [
        {"id": "gpt-3.5-turbo", "object": "model", "created": timestamp, "owned_by": "gemini-proxy"},
        {"id": "gpt-4", "object": "model", "created": timestamp, "owned_by": "gemini-proxy"},
        {"id": "gemini-2.5-flash", "object": "model", "created": timestamp, "owned_by": "google"},
        {"id": "gemini-2.5-pro", "object": "model", "created": timestamp, "owned_by": "google"},
        {"id": "g3-img-pro", "object": "model", "created": timestamp, "owned_by": "google"},
    ]
    return ModelList(data=models)

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """Handle chat completions (Text & Multimodal)."""
    
    # 1. Setup Client
    client = get_gemini_client()
    await init_client(client)
    
    temp_files = []
    
    try:
        # 2. Process Messages (Text + Images)
        full_prompt, temp_files = extract_content_and_files(request.messages)
        
        print(f"📝 Prompt length: {len(full_prompt)}, Files: {len(temp_files)}")
        
        chat = client.start_chat(model="gemini-3.0-pro")
        
        # 3. Generation
        if request.stream:
            # Note: files are not supported in stream_generator wrapper yet? 
            # We need to pass files to the generator logic or send message first then stream?
            # 'chat.send_message' supports stream=True internally in the lib?
            # Our stream_generator pseudo-implementation calls send_message.
            # We need to update stream_generator to accept files.
            
            async def cleanup_generator():
                gen = stream_generator(client, chat, full_prompt, request.model, files=temp_files)
                try:
                    async for item in gen:
                        yield item
                finally:
                    # Clean up temp files after stream
                    for f in temp_files:
                        if os.path.exists(f): os.remove(f)

            return EventSourceResponse(cleanup_generator())
        else:
            response = await chat.send_message(full_prompt, files=temp_files)
            
            # Cleanup immediately for non-stream
            for f in temp_files:
                if os.path.exists(f): os.remove(f)
                
            return format_response(response, request.model)

    except Exception as e:
        print(f"❌ Error: {e}")
        # Try cleanup
        for f in temp_files:
            if os.path.exists(f): os.remove(f)
        await client.close()
        raise HTTPException(status_code=500, detail=str(e))


async def stream_generator(client, chat, message, model, files=None):
    """
    Yields SSE events for streaming.
    """
    try:
        request_id = f"chatcmpl-{uuid.uuid4()}"
        created = int(time.time())
        
        # Pass files to Gemini
        response = await chat.send_message(message, files=files or [])
        text = response.text
        
        # Chunk logic
        chunk_size = 10
        for i in range(0, len(text), chunk_size):
            chunk = text[i:i+chunk_size]
            yield format_stream_chunk(request_id, created, model, chunk)
            await asyncio.sleep(0.01) 
            
        yield format_stream_chunk(request_id, created, model, "", finish_reason="stop")
        yield "[DONE]"
        
    finally:
        await client.close()




def format_stream_chunk(id, created, model, content, finish_reason=None):
    """Format data for SSE."""
    data = {
        "id": id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": content} if content else {},
                "finish_reason": finish_reason
            }
        ]
    }
    return json.dumps(data)

def format_response(gemini_resp, model):
    """Format full JSON response."""
    return {
        "id": f"chatcmpl-{uuid.uuid4()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": gemini_resp.text
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 0, # Not calculated
            "completion_tokens": len(gemini_resp.text) // 4,
            "total_tokens": len(gemini_resp.text) // 4
        }
    }


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
