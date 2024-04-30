import os
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile

from DB.db_article import (
    db_check_quantity_article,
    db_create_article,
    db_create_img_url,
    db_delete_article_by_id,
    db_get_all_article,
    db_get_art_img_url,
    db_get_article_by_id,
    db_update_article_by_id,
)
from DB.db_blacklist import db_blacklist_check
from DB.db_orders import db_create_order
from DB.db_visitor import db_add_article_visitor, db_check_visitor_ip
from schema.shcema import Article_schema, Order
from utils.img_upload import article_img_upload

route = APIRouter()


#! ------ GET ALL ARTICLE | WITH OFFSET AND LIMIT PARAMS -----------
@route.get("/")
async def all_article(
    req: Request, offset: int | None = None, limit: int | None = None
):
    try:
        data = await db_get_all_article(req.app.pool, offset, limit)
        return data
    except:
        raise HTTPException(status_code=400)


#! ------ GET ARTICLE BY ID --------------------------------------------
@route.get("/article/{id}")
async def get_article_by_id(id: int, req: Request):
    visited = await db_check_visitor_ip(req.app.pool, req.client.host)
    if not visited:
        try:
            await db_add_article_visitor(req.app.pool, req.client.host, id)
        except:
            raise HTTPException(status_code=400)
    data = await db_get_article_by_id(req.app.pool, id)

    if not data:
        raise HTTPException(status_code=404)
    return data


#! ------ ORDER ARTICLE --------------------------------------------
@route.post("/article/{article_id}", status_code=201)
async def order_article(req: Request, order_info: Order, article_id: int):

    inBlacklist = await db_blacklist_check(req.app.pool, order_info.phone_number)
    quantity_available = await db_check_quantity_article(req.app.pool, article_id)
    if inBlacklist or quantity_available == 0:

        raise HTTPException(status_code=400, detail="out of stock")

    await db_create_order(req.app.pool, order_info, article_id)


#! ------ DELETE ARTICLE BY ID ---------------------------------
@route.delete("/article/{id}")
async def delete_article_by_id(id: int, req: Request):
    if not req.auth:
        raise HTTPException(status_code=401)
    try:
        img_list = await db_get_art_img_url(req.app.pool, id)
        await db_delete_article_by_id(req.app.pool, id)
        path = Path() / "static"

        for img in img_list:
            path_to_delete = f"{path}/{img[0]}"
            os.remove(path_to_delete)
    except:
        raise HTTPException(status_code=400)


#! ------ UPDATE ARTICLE BY ID -----------------------------------------------
@route.put("/article/{id}")
async def update_article(id: int, req: Request, article_data: Article_schema):
    if not req.auth:
        raise HTTPException(status_code=401)
    try:
        data = await db_update_article_by_id(req.app.pool, id, article_data)
        return data
    except:
        raise HTTPException(status_code=404)


#! ------ CREATE ARTICLE AND IMAGE UPLOAD -----------
@route.post("/article", status_code=201)
async def create_article(
    req: Request,
    title: str = Form(),
    description: str | None = Form(),
    price: int = Form(),
    quantity: int = Form(),
    images: list[UploadFile] = Form(),
):
    if not req.auth:
        raise HTTPException(status_code=401)
    # check if images extensions are valid
    valid_extension = ["jpg", "jpeg", "png", "webp", "avif"]
    for image in images:
        imgFormat = image.content_type.split("/")
        if imgFormat[1] not in valid_extension:
            raise HTTPException(status_code=400, detail="not valid images")
    try:
        article_id = await db_create_article(
            req.app.pool, title, description, price, quantity
        )
        await db_create_img_url(req.app.pool, article_id, images)
        await article_img_upload(article_id, images)
    except:
        raise HTTPException(status_code=400, detail="not created")
