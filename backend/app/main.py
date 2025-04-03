# backend/app/main.py

from fastapi import FastAPI
import uvicorn # For running directly if needed

app = FastAPI(
    title="Pokedex API",
    description="API for fetching and caching Pokemon data from PokeAPI",
    version="1.0.0"
)

@app.get("/")
async def read_root():
    """ Basic root endpoint to check if the API is running. """
    return {"message": "Welcome to the Pokedex API!"}

# Example of how to run directly (though we'll use docker-compose)
# if __name__ == "__main__":
#    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
