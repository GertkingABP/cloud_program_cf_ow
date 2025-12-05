from fastapi import FastAPI, APIRouter, Request, HTTPException, Query
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from statistics import mean
import requests, urllib3
from typing import Dict, Any

#API_KEY = "fa19350c60323740ea7a69a447f70186"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI(
    title="Combined API",
    description="API для работы с Codeforces и погодой",
    version="1.0.0"
)

# Настройки шаблонов и статических файлов
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

router = APIRouter()

#--------------------------------------FRONTEND--------------------------------------#

@router.get("/", summary="Главная страница")
def root_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/ui/codeforces", summary="Интерфейс Codeforces")
def ui_codeforces(request: Request):
    return templates.TemplateResponse("codeforces.html", {"request": request})

@router.get("/ui/weather", summary="Интерфейс погоды")
def ui_weather(request: Request):
    return templates.TemplateResponse("weather.html", {"request": request})

#----------------------------------CODEFORCES API----------------------------------#

BASE_CF_URL = "https://codeforces.com/api"

def fetch_cf_data(endpoint: str) -> Any:
    """Универсальный запрос к Codeforces API."""
    r = requests.get(f"{BASE_CF_URL}/{endpoint}", timeout=10, verify=False)
    if r.status_code == 200 and 'json' in r.headers.get('content-type', ''):
        data = r.json()
        if data.get("status") == "FAILED":
            raise HTTPException(status_code=404, detail=data.get("comment", "Ошибка API"))
        return data.get("result", [])
    raise HTTPException(status_code=400, detail=f"Ошибка API: {r.status_code}")

@router.get("/cf_rate/{cf_id}", summary="Средний ранг пользователя")
def get_user_average_rank(cf_id: str):
    try:
        result = fetch_cf_data(f"user.rating?handle={cf_id}")
        if not result:
            return {"handle": cf_id, "error": "У пользователя нет соревнований"}
        ranks = [c["rank"] for c in result if "rank" in c]
        return {"handle": cf_id, "contests": len(ranks), "average_rank": round(mean(ranks), 2)}
    except HTTPException as e:
        return {"handle": cf_id, "error": e.detail}

@router.get("/cf_top/{n}", summary="Топ-N пользователей")
def get_top_users(n: int = 30):
    result = fetch_cf_data("user.ratedList?activeOnly=true")
    users = result[:n]
    return {"top": n, "users": [
        {"rank": i + 1, "handle": u["handle"], "rating": u.get("rating"), "maxRating": u.get("maxRating")}
        for i, u in enumerate(users)
    ]}

@router.get("/cf_stats", summary="Статистика задач Codeforces")
def get_cf_statistics():
    data = requests.get(f"{BASE_CF_URL}/problemset.problems", timeout=10, verify=False).json()["result"]
    problems = data["problems"]

    rating_count, tags_count = {}, {}
    for p in problems:
        if (r := p.get("rating")):
            rating_count[r] = rating_count.get(r, 0) + 1
        for tag in p.get("tags", []):
            tags_count[tag] = tags_count.get(tag, 0) + 1

    return {
        "rating_statistics": dict(sorted(rating_count.items())),
        "tag_statistics": dict(sorted(tags_count.items(), key=lambda x: x[1], reverse=True))
    }

#--------------------------------------WEATHER API--------------------------------------#

@router.get("/simple_weather", summary="Простой запрос погоды")
def get_simple_weather(
    city: str = Query("Москва"),
    api_key: str = Query(...)
):
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric&lang=ru"
        resp = requests.get(url, timeout=20, verify=False)
        if resp.status_code == 200:
            d = resp.json()
            return {
                "city": d['name'],
                "weather": d['weather'][0]['description'],
                "temperature": d['main']['temp'],
                "humidity": d['main']['humidity'],
                "wind_speed": d['wind']['speed']
            }
        return {"error": f"Ошибка API: {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}

# маршруты
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")