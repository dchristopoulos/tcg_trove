class DomainError(Exception):
    """Base exception for domain-level failures."""


class DuplicateEmailError(DomainError):
    """Raised when an email is already registered."""


class DuplicateUsernameError(DomainError):
    """Raised when a username is already registered."""


class UserNotFoundError(DomainError):
    """Raised when a user cannot be found."""


class SellerNotFoundError(DomainError):
    """Raised when a listing seller cannot be found."""


class ListingNotFoundError(DomainError):
    """Raised when a listing cannot be found."""


class PermissionDeniedError(DomainError):
    """Raised when the caller lacks permissions."""


class InvalidRoleError(DomainError):
    """Raised when role value is invalid."""


class InvalidFilterError(DomainError):
    """Raised when listing filter arguments are invalid."""


class FavoriteNotFoundError(DomainError):
    """Raised when a favorite record is missing."""


class InquiryNotFoundError(DomainError):
    """Raised when an inquiry cannot be found."""


class ViewingConflictError(DomainError):
    """Raised when a viewing time overlaps with an existing one."""


class ReservationConflictError(DomainError):
    """Raised when reservation dates overlap with an existing reservation."""


class ReservationNotFoundError(DomainError):
    """Raised when a reservation cannot be found."""


class InvalidDateRangeError(DomainError):
    """Raised when reservation date range is invalid."""


class InvalidPaymentMethodError(DomainError):
    """Raised when selected payment method is unsupported."""


class InvalidStatusTransitionError(DomainError):
    """Raised when an invalid status value or transition is requested."""


class TwoFactorRequiredError(DomainError):
    """Raised when 2FA verification is required before login finalization."""


class EmailNotVerifiedError(DomainError):
    """Raised when user email has not been verified."""


class InvalidVerificationTokenError(DomainError):
    """Raised when email verification token is invalid or expired."""


class InvalidPasswordError(DomainError):
    """Raised when password does not meet policy requirements."""
