from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import os
import traceback

load_dotenv()

from app.api.pages import router as pages_router

app = FastAPI(title="DrillDown API")

@app.exception_handler(Exception)
async def debug_exception_handler(request: Request, exc: Exception):
    print(f"ERROR: {exc}")
    traceback.print_exc()
    is_debug = os.getenv("ENV", "development").lower() != "production"
    response_data = {"error": str(exc)}
    if is_debug:
        response_data["traceback"] = traceback.format_exc()
    return response_data

# Enable CORS (secure dynamic localhost origins while maintaining credentials)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex="https?://localhost(:[0-9]+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(pages_router, prefix="/api")

# Ensure static directory exists
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return {"message": "DrillDown API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
