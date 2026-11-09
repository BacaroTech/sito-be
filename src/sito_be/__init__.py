def main() -> None:
    import uvicorn

    uvicorn.run("sito_be.app:app", host="0.0.0.0", port=8000)
