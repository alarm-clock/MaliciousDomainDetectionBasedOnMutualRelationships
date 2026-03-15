from fastapi import FastAPI

app = FastAPI()

@app.post("/add")
async def add_req():
    pass

@app.post("/update")
async def update_req():
    pass

@app.delete("/delete")
async def delete_req():
    pass

@app.get("/query")
async def query_req():
    pass