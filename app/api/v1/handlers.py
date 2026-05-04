from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import (
    DuplicateEmailError,
    DuplicateUsernameError,
    EmailNotVerifiedError,
    FavoriteNotFoundError,
    InquiryNotFoundError,
    InvalidDateRangeError,
    InvalidFilterError,
    InvalidPasswordError,
    InvalidPaymentMethodError,
    InvalidRoleError,
    InvalidStatusTransitionError,
    InvalidVerificationTokenError,
    ListingNotFoundError,
    SellerNotFoundError,
    PermissionDeniedError,
    ReservationConflictError,
    ReservationNotFoundError,
    TwoFactorRequiredError,
    UserNotFoundError,
    ViewingConflictError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DuplicateEmailError)
    async def duplicate_email_handler(_: Request, __: DuplicateEmailError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "Email already exists"})

    @app.exception_handler(DuplicateUsernameError)
    async def duplicate_username_handler(_: Request, __: DuplicateUsernameError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "Username already exists"})

    @app.exception_handler(SellerNotFoundError)
    async def seller_not_found_handler(_: Request, __: SellerNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "Seller not found"})

    @app.exception_handler(UserNotFoundError)
    async def user_not_found_handler(_: Request, __: UserNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "User not found"})

    @app.exception_handler(ListingNotFoundError)
    async def listing_not_found_handler(_: Request, __: ListingNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Listing not found"})

    @app.exception_handler(PermissionDeniedError)
    async def permission_denied_handler(_: Request, __: PermissionDeniedError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": "Permission denied"})

    @app.exception_handler(InvalidRoleError)
    async def invalid_role_handler(_: Request, __: InvalidRoleError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "Invalid role"})

    @app.exception_handler(InvalidFilterError)
    async def invalid_filter_handler(_: Request, __: InvalidFilterError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "Invalid search filters"})

    @app.exception_handler(FavoriteNotFoundError)
    async def favorite_not_found_handler(_: Request, __: FavoriteNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Favorite not found"})

    @app.exception_handler(InquiryNotFoundError)
    async def inquiry_not_found_handler(_: Request, __: InquiryNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Inquiry not found"})

    @app.exception_handler(ViewingConflictError)
    async def viewing_conflict_handler(_: Request, __: ViewingConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": "Viewing slot conflict"})

    @app.exception_handler(ReservationConflictError)
    async def reservation_conflict_handler(_: Request, __: ReservationConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": "Reservation date conflict"})

    @app.exception_handler(ReservationNotFoundError)
    async def reservation_not_found_handler(_: Request, __: ReservationNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": "Reservation not found"})

    @app.exception_handler(InvalidDateRangeError)
    async def invalid_date_range_handler(_: Request, __: InvalidDateRangeError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "Invalid date range"})

    @app.exception_handler(InvalidPaymentMethodError)
    async def invalid_payment_method_handler(_: Request, __: InvalidPaymentMethodError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "Invalid payment method"})

    @app.exception_handler(InvalidStatusTransitionError)
    async def invalid_status_transition_handler(_: Request, __: InvalidStatusTransitionError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "Invalid status transition"})

    @app.exception_handler(TwoFactorRequiredError)
    async def two_factor_required_handler(_: Request, __: TwoFactorRequiredError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": "Two-factor authentication required"})

    @app.exception_handler(EmailNotVerifiedError)
    async def email_not_verified_handler(_: Request, __: EmailNotVerifiedError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": "Email not verified"})

    @app.exception_handler(InvalidVerificationTokenError)
    async def invalid_verification_token_handler(_: Request, __: InvalidVerificationTokenError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "Invalid verification token"})

    @app.exception_handler(InvalidPasswordError)
    async def invalid_password_handler(_: Request, __: InvalidPasswordError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": "Password must be at least 8 characters and include letters and numbers"})

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Ensure all HTTP errors on /api/v1 routes return JSON, never HTML
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail or "An error occurred"})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

