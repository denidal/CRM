from fastapi import APIRouter

from system.api import (
    auth,
    btk,
    contracts,
    customers,
    files,
    finance,
    iss,
    pops,
    radius,
    services,
)


def build_api_router() -> APIRouter:
    router = APIRouter(prefix="/api")
    router.include_router(auth.router, tags=["auth"])
    router.include_router(customers.router, tags=["customers"])
    router.include_router(services.router, tags=["services"])
    router.include_router(pops.router, tags=["pops"])
    router.include_router(radius.router, tags=["radius"])
    router.include_router(iss.router, tags=["iss"])
    router.include_router(contracts.router, tags=["contracts"])
    router.include_router(finance.router, tags=["finance"])
    router.include_router(btk.router, tags=["btk"])
    router.include_router(files.router, tags=["files"])
    return router
