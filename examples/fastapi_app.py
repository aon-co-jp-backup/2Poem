from fastapi import FastAPI

app = FastAPI()


@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"id": item_id}


@app.put("/users/{user}/score/{score}")
async def set_score(user: str, score: float):
    return {"user": user, "score": score}
