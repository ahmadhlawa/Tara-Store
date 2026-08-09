from fastapi import APIRouter

from app.api.deps import StorefrontOpen
from app.api.v1.endpoints import (
    admin_catalog,
    admin_commerce,
    admin_content,
    admin_invoices,
    admin_media,
    admin_users,
    auth,
    public_catalog,
    public_checkout,
    public_content,
)

api_router = APIRouter()

# Store identity — always reachable, including during maintenance, because the
# maintenance screen is built from it.
api_router.include_router(public_content.identity_router)

# The rest of the public storefront surface closes while maintenance mode is on.
_storefront = [StorefrontOpen]
api_router.include_router(public_content.router, dependencies=_storefront)
api_router.include_router(public_catalog.router, dependencies=_storefront)
api_router.include_router(public_checkout.router, dependencies=_storefront)

# Authenticated admin surface
api_router.include_router(auth.router)
api_router.include_router(admin_catalog.router)
api_router.include_router(admin_content.router)
api_router.include_router(admin_commerce.router)
api_router.include_router(admin_invoices.router)
api_router.include_router(admin_media.router)
api_router.include_router(admin_users.router)
