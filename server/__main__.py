import uvicorn

uvicorn.run(
    "last_translation_benchmark.__init__:app",
    host="127.0.0.1",
    port=8000,
    reload=True,
)

"""
alternatively run:

uvicorn server:app --reload
"""
